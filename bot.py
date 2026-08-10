import logging
import os
import random
import tempfile
from datetime import time as dtime

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from topics import TOPICS
from content import generate_post, get_code_snippet
from images import generate_image
from video import generate_code_video

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

load_dotenv()  # shu papkadagi .env faylini o'qib, muhit o'zgaruvchilariga yuklaydi

try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    CHANNEL_ID = os.environ["CHANNEL_ID"]  # masalan: @mykanalim yoki -100123456789
except KeyError as e:
    raise SystemExit(
        f"Xato: {e.args[0]} muhit o'zgaruvchisi topilmadi.\n"
        f"Shu papkada .env fayl yarating (README.md'dagi namunaga qarang) "
        f"yoki 'export {e.args[0]}=...' orqali qo'lda o'rnating."
    )

ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", "0"))  # ixtiyoriy: faqat shu user buyruq bera oladi


def is_admin(update: Update) -> bool:
    if ADMIN_USER_ID == 0:
        return True  # cheklanmagan, ehtiyot bo'l
    return update.effective_user and update.effective_user.id == ADMIN_USER_ID


CAPTION_LIMIT = 1024  # Telegram rasm/video captioni uchun limit


async def post_now(context: ContextTypes.DEFAULT_TYPE, topic: str | None = None) -> str:
    """Bitta post generatsiya qilib kanalga joylaydi. Joylangan mavzuni qaytaradi."""
    if topic:
        chosen_topic, official_link = topic, None
    else:
        chosen_topic, official_link = random.choice(TOPICS)
    post = generate_post(chosen_topic, official_link)
    text = post["text"]
    media_type = post["media_type"]
    media_prompt = post["media_prompt"]

    media_path = None
    with tempfile.TemporaryDirectory() as tmpdir:
        if media_type == "image" and media_prompt:
            candidate_path = os.path.join(tmpdir, "post.png")
            if generate_image(media_prompt, candidate_path):
                media_path = candidate_path
            else:
                logger.warning("Rasm generatsiya qilinmadi, faqat matn yuboriladi")

        elif media_type == "video" and media_prompt:
            snippet = get_code_snippet(chosen_topic)
            if snippet:
                candidate_path = os.path.join(tmpdir, "post.mp4")
                if generate_code_video(snippet, chosen_topic, candidate_path):
                    media_path = candidate_path
                else:
                    logger.warning("Video generatsiya qilinmadi, faqat matn yuboriladi")

        if media_path and len(text) <= CAPTION_LIMIT:
            # media + matn bitta xabarda (caption sifatida) sig'adi
            if media_type == "image":
                with open(media_path, "rb") as f:
                    await context.bot.send_photo(
                        chat_id=CHANNEL_ID, photo=f, caption=text,
                        parse_mode=ParseMode.MARKDOWN_V2,
                    )
            else:
                with open(media_path, "rb") as f:
                    await context.bot.send_video(
                        chat_id=CHANNEL_ID, video=f, caption=text,
                        parse_mode=ParseMode.MARKDOWN_V2,
                    )
        elif media_path:
            # matn caption limitidan uzun - media captionsiz, matn alohida xabar sifatida
            if media_type == "image":
                with open(media_path, "rb") as f:
                    await context.bot.send_photo(chat_id=CHANNEL_ID, photo=f)
            else:
                with open(media_path, "rb") as f:
                    await context.bot.send_video(chat_id=CHANNEL_ID, video=f)
            await context.bot.send_message(
                chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.MARKDOWN_V2,
            )
        else:
            # media yo'q - faqat matn
            await context.bot.send_message(
                chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.MARKDOWN_V2,
            )

    return chosen_topic


async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return

    topic = " ".join(context.args) if context.args else None
    await update.message.reply_text("Post tayyorlanmoqda...")
    try:
        chosen = await post_now(context, topic)
        await update.message.reply_text(f"Kanalga joylandi: {chosen}")
    except Exception as e:
        logger.exception("Post joylashda xatolik")
        await update.message.reply_text(f"Xatolik: {e}")


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return

    if not context.args:
        jobs = context.job_queue.get_jobs_by_name("daily_post")
        if jobs:
            t = jobs[0].job.trigger.fields
            await update.message.reply_text("Kunlik avtomatik post yoqilgan. O'chirish uchun: /unschedule")
        else:
            await update.message.reply_text(
                "Foydalanish: /schedule HH:MM (masalan /schedule 18:00)\n"
                "Vaqt server vaqti (UTC) bo'yicha."
            )
        return

    try:
        hour, minute = map(int, context.args[0].split(":"))
    except ValueError:
        await update.message.reply_text("Noto'g'ri format. Masalan: /schedule 18:00")
        return

    # eski jobni o'chirib, yangisini qo'yamiz
    for job in context.job_queue.get_jobs_by_name("daily_post"):
        job.schedule_removal()

    context.job_queue.run_daily(
        daily_post_callback,
        time=dtime(hour=hour, minute=minute),
        name="daily_post",
    )
    await update.message.reply_text(
        f"Har kuni {hour:02d}:{minute:02d} (UTC) da avtomatik post yoqildi."
    )


async def cmd_unschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return
    removed = 0
    for job in context.job_queue.get_jobs_by_name("daily_post"):
        job.schedule_removal()
        removed += 1
    await update.message.reply_text(
        "Avtomatik post o'chirildi." if removed else "Yoqilgan reja topilmadi."
    )


async def cmd_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    listing = "\n".join(f"- {name}" for name, _ in TOPICS)
    await update.message.reply_text(f"Mavjud mavzular:\n{listing}\n\nQo'shish: /addtopic <mavzu>")


async def cmd_addtopic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: /addtopic <mavzu nomi>")
        return
    new_topic = " ".join(context.args)
    TOPICS.append((new_topic, None))
    with open(os.path.join(os.path.dirname(__file__), "topics.py"), "w", encoding="utf-8") as f:
        f.write("TOPICS = [\n")
        for name, link in TOPICS:
            f.write(f"    ({name!r}, {link!r}),\n")
        f.write("]\n")
    await update.message.reply_text(f"Qo'shildi: {new_topic}")


async def daily_post_callback(context: ContextTypes.DEFAULT_TYPE):
    try:
        chosen = await post_now(context)
        logger.info(f"Kunlik post joylandi: {chosen}")
    except Exception:
        logger.exception("Kunlik postda xatolik")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Dasturlash postlari boti ishga tushdi.\n\n"
        "Buyruqlar:\n"
        "/post [mavzu] - hozir post joylash\n"
        "/schedule HH:MM - kunlik avtomatik postni yoqish\n"
        "/unschedule - avtomatik postni o'chirish\n"
        "/topics - mavzular ro'yxati\n"
        "/addtopic <mavzu> - yangi mavzu qo'shish"
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("unschedule", cmd_unschedule))
    app.add_handler(CommandHandler("topics", cmd_topics))
    app.add_handler(CommandHandler("addtopic", cmd_addtopic))

    logger.info("Bot ishga tushdi (polling)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
