import logging
import os
import random
import tempfile
from datetime import time as dtime, timezone

from dotenv import load_dotenv

load_dotenv()  # shu papkadagi .env faylini o'qib, muhit o'zgaruvchilariga yuklaydi.
# MUHIM: bu quyidagi `from content import ...` va boshqa lokal modul
# importlaridan OLDIN chaqirilishi shart - aks holda content.py, images.py
# kabi modullar import qilinganda GEMINI_API_KEY hali .env'dan o'qilmagan
# bo'ladi (ular modul darajasida os.environ.get(...) chaqiradi).

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import db
from content import generate_post, get_code_snippet
from video import generate_code_video

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
except KeyError as e:
    raise SystemExit(
        f"Xato: {e.args[0]} muhit o'zgaruvchisi topilmadi.\n"
        f"Shu papkada .env fayl yarating (README.md'dagi namunaga qarang) "
        f"yoki 'export {e.args[0]}=...' orqali qo'lda o'rnating."
    )

db.init_db()

CAPTION_LIMIT = 1024  # Telegram rasm/video captioni uchun limit

# /addchannel suhbat bosqichlari
ASK_CHANNEL, ASK_TOPICS, ASK_TIME = range(3)


async def resolve_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Buyruq qaysi kanal uchun ekanini aniqlaydi.
    Agar foydalanuvchida bitta kanal bo'lsa - avtomatik o'shani qaytaradi.
    Bir nechta bo'lsa - tanlov tugmalarini ko'rsatadi va None qaytaradi.
    Hech qanday kanal bo'lmasa - xabar beradi va None qaytaradi."""
    user_id = update.effective_user.id
    channels = db.get_channels_for_user(user_id)

    if not channels:
        await update.message.reply_text(
            "Sizda hali ro'yxatdan o'tgan kanal yo'q. Avval /addchannel buyrug'i bilan kanal qo'shing."
        )
        return None

    if len(channels) == 1:
        return channels[0]["channel_id"]

    # bir nechta kanal - tanlov tugmalari
    keyboard = [
        [InlineKeyboardButton(ch["channel_id"], callback_data=f"selectch:{ch['channel_id']}")]
        for ch in channels
    ]
    await update.message.reply_text(
        "Sizda bir nechta kanal bor. Buyruqni qaysi kanal uchun bajarish kerak?\n"
        "(Tanlagandan so'ng buyruqni qayta yuboring)",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return None


async def cmd_select_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    channel_id = query.data.split(":", 1)[1]
    context.user_data["selected_channel"] = channel_id
    await query.edit_message_text(f"Tanlandi: {channel_id}\nEndi kerakli buyruqni qayta yuboring.")


async def post_now(context: ContextTypes.DEFAULT_TYPE, channel_id: str, topic: str | None = None) -> str:
    """Bitta post generatsiya qilib berilgan kanalga joylaydi. Joylangan mavzuni qaytaradi."""
    if topic:
        chosen_topic, official_link = topic, None
    else:
        channel_topics = db.get_topics(channel_id)
        if not channel_topics:
            raise ValueError(
                "Bu kanalda hali mavzular yo'q. /addtopic bilan mavzu qo'shing."
            )
        picked = random.choice(channel_topics)
        chosen_topic, official_link = picked["topic_name"], picked["official_link"]

    post = generate_post(chosen_topic, official_link)
    text = post["text"]
    media_type = post["media_type"]
    media_prompt = post["media_prompt"]

    media_path = None
    with tempfile.TemporaryDirectory() as tmpdir:
        if media_type == "video" and media_prompt:
            snippet = get_code_snippet(chosen_topic)
            if snippet:
                candidate_path = os.path.join(tmpdir, "post.mp4")
                if generate_code_video(snippet, chosen_topic, candidate_path):
                    media_path = candidate_path
                else:
                    logger.warning("Video generatsiya qilinmadi, faqat matn yuboriladi")

        if media_path and len(text) <= CAPTION_LIMIT:
            with open(media_path, "rb") as f:
                await context.bot.send_video(
                    chat_id=channel_id, video=f, caption=text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
        elif media_path:
            with open(media_path, "rb") as f:
                await context.bot.send_video(chat_id=channel_id, video=f)
            await context.bot.send_message(
                chat_id=channel_id, text=text, parse_mode=ParseMode.MARKDOWN_V2,
            )
        else:
            await context.bot.send_message(
                chat_id=channel_id, text=text, parse_mode=ParseMode.MARKDOWN_V2,
            )

    return chosen_topic


# ---------- /addchannel suhbat oqimi ----------

async def cmd_addchannel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("Bu buyruqni bot bilan shaxsiy chatda yuboring.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Yangi kanal qo'shamiz.\n\n"
        "1-qadam: Botni kanalingizga admin qiling (\"Post Messages\" huquqi bilan), "
        "keyin kanal username'ini yuboring (masalan @mykanalim) yoki kanal ID'sini "
        "(masalan -1001234567890).\n\n"
        "Bekor qilish uchun /cancel yozing."
    )
    return ASK_CHANNEL


async def addchannel_got_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = update.message.text.strip()
    if not (channel_id.startswith("@") or channel_id.startswith("-")):
        await update.message.reply_text(
            "Noto'g'ri format. Kanal @username yoki -100... ko'rinishida bo'lishi kerak. Qayta urinib ko'ring."
        )
        return ASK_CHANNEL

    if db.channel_exists(channel_id):
        await update.message.reply_text(
            "Bu kanal allaqachon ro'yxatdan o'tgan. Agar o'zingizni admin sifatida "
            "qo'shishni xohlasangiz, kanal egasidan /addadmin buyrug'ini so'rang."
        )
        return ConversationHandler.END

    # botning kanalga admin ekanligini tekshiramiz
    try:
        member = await context.bot.get_chat_member(channel_id, context.bot.id)
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text(
                "Bot bu kanalda admin emas. Avval botni kanalga admin qilib, keyin qayta urinib ko'ring."
            )
            return ASK_CHANNEL
    except Exception as e:
        await update.message.reply_text(
            f"Kanalni tekshirib bo'lmadi: {e}\n"
            "Kanal ID/username to'g'ri ekanini va bot admin qilinganini tekshiring. Qayta urinib ko'ring."
        )
        return ASK_CHANNEL

    context.user_data["new_channel_id"] = channel_id
    await update.message.reply_text(
        "Kanal tasdiqlandi \u2705\n\n"
        "2-qadam: Mavzularni yuboring, har birini alohida qatorda "
        "(masalan:\nPython dekoratorlari\nDocker asoslari\nSQL indekslar)"
    )
    return ASK_TOPICS


async def addchannel_got_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [line.strip() for line in update.message.text.split("\n") if line.strip()]
    if not lines:
        await update.message.reply_text("Kamida bitta mavzu yuboring.")
        return ASK_TOPICS
    context.user_data["new_channel_topics"] = lines
    await update.message.reply_text(
        f"{len(lines)} ta mavzu qabul qilindi \u2705\n\n"
        "3-qadam: Kunlik avtomatik post qaysi vaqtda joylansin? "
        "HH:MM formatida yuboring (UTC bo'yicha, masalan 13:00).\n"
        "Agar avtomatik post kerak bo'lmasa, /skip yozing."
    )
    return ASK_TIME


async def addchannel_got_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    hour = minute = None
    if text != "/skip":
        try:
            hour, minute = map(int, text.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "Noto'g'ri format. Masalan: 13:00, yoki /skip yozing."
            )
            return ASK_TIME

    channel_id = context.user_data["new_channel_id"]
    topics = context.user_data["new_channel_topics"]
    user_id = update.effective_user.id

    db.add_channel(channel_id, user_id)
    for t in topics:
        db.add_topic(channel_id, t)
    if hour is not None:
        db.set_schedule(channel_id, hour, minute)
        _schedule_channel_job(context.application, channel_id, hour, minute)

    summary = f"Kanal qo'shildi: {channel_id}\nMavzular: {len(topics)} ta"
    if hour is not None:
        summary += f"\nAvtomatik post: har kuni {hour:02d}:{minute:02d} (UTC)"
    else:
        summary += "\nAvtomatik post: o'chirilgan (keyin /schedule bilan yoqishingiz mumkin)"
    await update.message.reply_text(summary)

    context.user_data.pop("new_channel_id", None)
    context.user_data.pop("new_channel_topics", None)
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Bekor qilindi.")
    return ConversationHandler.END


# ---------- Oddiy buyruqlar ----------

async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = context.user_data.pop("selected_channel", None)
    if not channel_id:
        channel_id = await resolve_channel(update, context)
        if not channel_id:
            return
    if not db.is_channel_admin(channel_id, update.effective_user.id):
        await update.message.reply_text("Siz bu kanal uchun admin emassiz.")
        return

    topic = " ".join(context.args) if context.args else None
    await update.message.reply_text(f"Post tayyorlanmoqda ({channel_id})...")
    try:
        chosen = await post_now(context, channel_id, topic)
        await update.message.reply_text(f"{channel_id} kanaliga joylandi: {chosen}")
    except Exception as e:
        logger.exception("Post joylashda xatolik")
        await update.message.reply_text(f"Xatolik: {e}")


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = context.user_data.pop("selected_channel", None)
    if not channel_id:
        channel_id = await resolve_channel(update, context)
        if not channel_id:
            return
    if not db.is_channel_admin(channel_id, update.effective_user.id):
        await update.message.reply_text("Siz bu kanal uchun admin emassiz.")
        return

    if not context.args:
        channels = db.get_channels_for_user(update.effective_user.id)
        current = next((c for c in channels if c["channel_id"] == channel_id), None)
        if current and current["schedule_hour"] is not None:
            await update.message.reply_text(
                f"Joriy jadval: har kuni {current['schedule_hour']:02d}:{current['schedule_minute']:02d} (UTC).\n"
                f"O'chirish uchun: /unschedule"
            )
        else:
            await update.message.reply_text(
                "Foydalanish: /schedule HH:MM (masalan /schedule 18:00)\n"
                "Vaqt server vaqti (UTC) bo'yicha."
            )
        return

    try:
        hour, minute = map(int, context.args[0].split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Noto'g'ri format. Masalan: /schedule 18:00")
        return

    db.set_schedule(channel_id, hour, minute)
    _schedule_channel_job(context.application, channel_id, hour, minute)
    await update.message.reply_text(
        f"{channel_id}: har kuni {hour:02d}:{minute:02d} (UTC) da avtomatik post yoqildi."
    )


async def cmd_unschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = context.user_data.pop("selected_channel", None)
    if not channel_id:
        channel_id = await resolve_channel(update, context)
        if not channel_id:
            return
    if not db.is_channel_admin(channel_id, update.effective_user.id):
        await update.message.reply_text("Siz bu kanal uchun admin emassiz.")
        return

    db.clear_schedule(channel_id)
    _unschedule_channel_job(context.application, channel_id)
    await update.message.reply_text(f"{channel_id}: avtomatik post o'chirildi.")


async def cmd_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = context.user_data.pop("selected_channel", None)
    if not channel_id:
        channel_id = await resolve_channel(update, context)
        if not channel_id:
            return

    topics = db.get_topics(channel_id)
    if not topics:
        await update.message.reply_text(f"{channel_id} uchun hali mavzular yo'q. /addtopic bilan qo'shing.")
        return
    listing = "\n".join(f"- {t['topic_name']}" for t in topics)
    await update.message.reply_text(f"{channel_id} mavzulari:\n{listing}\n\nQo'shish: /addtopic <mavzu>")


async def cmd_addtopic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = context.user_data.pop("selected_channel", None)
    if not channel_id:
        channel_id = await resolve_channel(update, context)
        if not channel_id:
            return
    if not db.is_channel_admin(channel_id, update.effective_user.id):
        await update.message.reply_text("Siz bu kanal uchun admin emassiz.")
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: /addtopic <mavzu nomi>")
        return
    new_topic = " ".join(context.args)
    db.add_topic(channel_id, new_topic)
    await update.message.reply_text(f"{channel_id} ga qo'shildi: {new_topic}")


async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = context.user_data.pop("selected_channel", None)
    if not channel_id:
        channel_id = await resolve_channel(update, context)
        if not channel_id:
            return
    if not db.is_channel_admin(channel_id, update.effective_user.id):
        await update.message.reply_text("Siz bu kanal uchun admin emassiz.")
        return
    if not context.args:
        await update.message.reply_text(
            "Foydalanish: /addadmin <telegram_user_id>\n"
            "Yangi adminning ID'sini @userinfobot orqali olish mumkin."
        )
        return
    try:
        new_admin_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("User ID raqam bo'lishi kerak.")
        return
    added = db.add_channel_admin(channel_id, new_admin_id)
    if added:
        await update.message.reply_text(f"{new_admin_id} endi {channel_id} kanali uchun admin.")
    else:
        await update.message.reply_text("Bu foydalanuvchi allaqachon admin.")


async def cmd_mychannels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = db.get_channels_for_user(update.effective_user.id)
    if not channels:
        await update.message.reply_text("Sizda hali kanal yo'q. /addchannel bilan qo'shing.")
        return
    lines = []
    for ch in channels:
        sched = f"{ch['schedule_hour']:02d}:{ch['schedule_minute']:02d} UTC" if ch["schedule_hour"] is not None else "yoqilmagan"
        lines.append(f"- {ch['channel_id']} (jadval: {sched})")
    await update.message.reply_text("Sizning kanallaringiz:\n" + "\n".join(lines))


# ---------- Kunlik avtomatik post - har kanal uchun alohida job ----------

def _job_name(channel_id: str) -> str:
    return f"daily_post:{channel_id}"


def _schedule_channel_job(application, channel_id: str, hour: int, minute: int):
    for job in application.job_queue.get_jobs_by_name(_job_name(channel_id)):
        job.schedule_removal()
    application.job_queue.run_daily(
        daily_post_callback,
        time=dtime(hour=hour, minute=minute, tzinfo=timezone.utc),
        name=_job_name(channel_id),
        data={"channel_id": channel_id},
    )


def _unschedule_channel_job(application, channel_id: str):
    for job in application.job_queue.get_jobs_by_name(_job_name(channel_id)):
        job.schedule_removal()


async def daily_post_callback(context: ContextTypes.DEFAULT_TYPE):
    channel_id = context.job.data["channel_id"]
    try:
        chosen = await post_now(context, channel_id)
        logger.info(f"Kunlik post joylandi ({channel_id}): {chosen}")
    except Exception:
        logger.exception(f"Kunlik postda xatolik ({channel_id})")


def _restore_all_schedules(application):
    """Bot qayta ishga tushganda, bazadagi barcha jadvallarni JobQueue'ga tiklaydi."""
    channels = db.get_all_scheduled_channels()
    for ch in channels:
        _schedule_channel_job(application, ch["channel_id"], ch["schedule_hour"], ch["schedule_minute"])
    logger.info(f"{len(channels)} ta kanal uchun jadval tiklandi")


# ---------- Umumiy buyruqlar ----------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Dasturlash postlari boti.\n\n"
        "Buyruqlar:\n"
        "/addchannel - yangi kanal qo'shish (bosqichma-bosqich)\n"
        "/mychannels - kanallaringiz ro'yxati\n"
        "/post [mavzu] - hozir post joylash\n"
        "/schedule HH:MM - kunlik avtomatik postni yoqish\n"
        "/unschedule - avtomatik postni o'chirish\n"
        "/topics - mavzular ro'yxati\n"
        "/addtopic <mavzu> - yangi mavzu qo'shish\n"
        "/addadmin <user_id> - kanalga admin qo'shish"
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    addchannel_conv = ConversationHandler(
        entry_points=[CommandHandler("addchannel", cmd_addchannel_start)],
        states={
            ASK_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, addchannel_got_channel)],
            ASK_TOPICS: [MessageHandler(filters.TEXT & ~filters.COMMAND, addchannel_got_topics)],
            ASK_TIME: [MessageHandler(filters.TEXT, addchannel_got_time)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    app.add_handler(addchannel_conv)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("mychannels", cmd_mychannels))
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("unschedule", cmd_unschedule))
    app.add_handler(CommandHandler("topics", cmd_topics))
    app.add_handler(CommandHandler("addtopic", cmd_addtopic))
    app.add_handler(CommandHandler("addadmin", cmd_addadmin))
    app.add_handler(CallbackQueryHandler(cmd_select_channel_callback, pattern=r"^selectch:"))

    _restore_all_schedules(app)

    logger.info("Bot ishga tushdi (polling)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()