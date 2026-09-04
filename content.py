import logging
import os
import re
import json
import random

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Har chaqiruvda tasodifiy tanlanadi, shunda postlar bir xil qolipga tushmaydi.
FORMAT_STYLES = [
    "Savol bilan boshla ('Nega X shunday ishlaydi?', 'X va Y orasida farq nima?' kabi), keyin javob ber.",
    "To'g'ridan-to'g'ri kod namunasidan boshla, keyin uni tushuntir.",
    "Keng tarqalgan xato yoki noto'g'ri tushunchani ko'rsatib boshla, keyin to'g'ri yondashuvni ber.",
    "Ikkita yondashuvni solishtirish (masalan 'A usuli vs B usuli') shaklida yoz.",
    "Qisqa voqea yoki analogiya bilan boshla (masalan real hayotdagi o'xshatish), keyin texnik tomoniga o't.",
    "Raqamlangan qadamlar yoki ro'yxat shaklida tushuntir.",
    "'Bilasizmi?' yoki qiziqarli fakt bilan boshla, keyin chuqurroq tushuntir.",
    "Muammo-yechim formatida: avval muammoni tasvirla, keyin yechimni ko'rsat.",
]

TONE_STYLES = [
    "engil va do'stona ohangda",
    "qisqa va lo'nda, ortiqcha so'zsiz",
    "bir oz hazil bilan, lekin professional",
    "amaliyotchi dasturchiga murojaat qilganday, texnik lekin tushunarli",
]

SYSTEM_PROMPT = """Sen Telegram kanali uchun dasturlash mavzusida post yozuvchisan.
Har bir post 3 tilda bo'lishi kerak: avval o'zbek tilida (lotin alifbosida), keyin rus tilida, keyin ingliz tilida.
Har til bo'limi bayroq va til nomi bilan boshlanadi: 🇺🇿 O'ZBEKCHA, 🇷🇺 РУССКИЙ, 🇬🇧 ENGLISH.

MUHIM: quyida berilgan FORMAT va OHANG ko'rsatmalariga qat'iy amal qil. Har safar boshqacha post kelishi kerak - bir xil "sarlavha+tushuntirish+savol" qolipini takrorlama. Uchala tilda ham bir xil format va tuzilishni saqla (faqat til farq qilsin), lekin bu safargi post o'zining o'ziga xos formatida bo'lsin.

ENG MUHIMI: post berilgan MAVZUGA XOS, KONKRET texnik ma'lumot berishi shart. "Bu muhim tushuncha", "buni o'rganish foydali" kabi umumiy, har qanday mavzuga mos keladigan gaplar YOZMA - bular hech narsa aytmaydi. Buning o'rniga:
- Mavzuning aynan qanday ishlashini tushuntir (masalan "dekorator" haqida bo'lsa - u funksiyani qanday o'rab oladi, nima uchun @ belgisi ishlatiladi)
- Real kod misoli bilan ko'rsat, kodni izohla
- Qachon va nima uchun bu narsa kerakligini aniq holat bilan tushuntir
- Agar boshqa narsa bilan solishtirish kerak bo'lsa (masalan "X vs Y"), ikkalasining ham aniq farqini, afzallik/kamchiligini yoz

Har bir gap o'sha mavzuning o'ziga xos xususiyatini aytishi kerak - agar gapni boshqa mavzuga almashtirib qo'ysang ham to'g'ri chiqsa (masalan "bu muhim tushuncha" - buni istalgan mavzuga qo'yish mumkin), demak bu gap yaroqsiz, uni olib tashla va o'rniga mavzuning o'ziga xos faktini yoz.

Har bir til bo'limida:
- 40-120 so'z (mavzu va formatga qarab uzunlik o'zgarishi normal - har doim bir xil uzunlikda bo'lish shart emas)
- Kerak bo'lsa kod bo'lagi (uchtaga backtick ichida: ```kod```) - lekin har bir postda kod bo'lishi shart emas, formatga qarab
- Mavzuga mos 3-7 ta emoji tabiiy joylashtirilgan
- Sarlavha bold (** bilan), lekin sarlavhaning o'zi ham har safar boshqacha uslubda bo'lsin (savol, da'vat, fakt va h.k. - berilgan formatga mos)

Har bir postni bir xil "Savollaringiz bo'lsa yozing" yoki shunga o'xshash umumiy jumla bilan yakunlama - buning o'rniga formatga mos tabiiy yakun toping (masalan taklif, qisqa xulosa, keyingi qadam, yoki hech narsa yozmasdan kod/misol bilan tugatish).

Agar foydalanuvchi xabarida "Rasmiy havola:" ko'rsatilgan bo'lsa, o'sha havolani postning eng oxiriga, "🔗 Batafsil:" belgisi bilan bitta marta qo'sh (uch tilga alohida-alohida takrorlama, faqat oxirida bitta umumiy havola yetarli). Agar havola berilmagan bo'lsa, havola qo'shma.

Post oxirida (havoladan keyin, agar havola bo'lsa) shu formatda JSON metama'lumot bloki qo'sh, uch qo'shtirnoq bilan o'ralgan:
```json
{
  "media_type": "video" yoki "none",
  "media_prompt": "agar media_type video bo'lsa, shu mavzuni tasvirlaydigan vizual tavsif (ingliz tilida, video generatsiya uchun ishlatiladi). Masalan: 'a clean minimal illustration of a Python decorator wrapping a function, flat design, code editor aesthetic, dark theme, blue and purple accents'"
}
```

media_type tanlash mezoni: agar mavzu jarayon yoki animatsiya bilan yaxshi tushuntiriladigan bo'lsa (masalan animatsiya, o'zgarish, davr, kod ishlash jarayoni) - "video" tanla. Aksariyat postlar uchun "none" mos - video faqat aynan animatsiya/jarayon mavzulariga tanlansin, hammasi uchun emas.

Faqat post matnini va oxiridagi JSON blokni qaytar, boshqa hech narsa yozma."""


def _escape_markdown_v2(text: str) -> str:
    """Telegram MarkdownV2 uchun maxsus belgilarni escape qiladi, **bold** va ```kod``` dan tashqari."""
    parts = re.split(r"(```[\s\S]*?```|\*\*.+?\*\*)", text)
    escape_chars = r"_[]()~`>#+-=|{}.!"
    result = []
    for part in parts:
        if part.startswith("```") and part.endswith("```"):
            inner = part[3:-3]
            inner_escaped = inner.replace("\\", "\\\\").replace("`", "\\`")
            result.append(f"```{inner_escaped}```")
        elif part.startswith("**") and part.endswith("**"):
            inner = part[2:-2]
            inner_escaped = re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", inner)
            result.append(f"*{inner_escaped}*")
        else:
            result.append(re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", part))
    return "".join(result)


def _extract_json_block(raw: str) -> tuple[str, dict]:
    """Matn oxiridagi ```json {...} ``` blokni ajratib oladi. (post_matni, metadata_dict) qaytaradi."""
    match = re.search(r"```json\s*(\{.*?\})\s*```\s*$", raw, re.DOTALL)
    if not match:
        return raw.strip(), {"media_type": "none", "media_prompt": ""}
    post_text = raw[: match.start()].strip()
    try:
        metadata = json.loads(match.group(1))
    except json.JSONDecodeError:
        metadata = {"media_type": "none", "media_prompt": ""}
    return post_text, metadata


# Ketma-ket sinaladigan modellar. Biri 503 (yoki boshqa xato) bersa, keyingisiga o'tiladi -
# turli modellar odatda turli server klasterlarida joylashgan, shuning uchun bittasi band
# bo'lsa ham boshqasi ishlashi mumkin.
# Tartib real sinovlar asosida: 3.5-flash barqaror ishlagani uchun birinchi qo'yilgan.
# gemini-2.5-flash butunlay eskirgan (404, "Interactions API"ga o'tishni talab qiladi) - olib tashlandi.
MODEL_CHAIN = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.7-flash"]


def _generate_via_api(topic: str, official_link: str | None) -> tuple[str, dict]:
    import time
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors

    client = genai.Client(api_key=GEMINI_API_KEY)
    chosen_format = random.choice(FORMAT_STYLES)
    chosen_tone = random.choice(TONE_STYLES)

    user_message = f"Mavzu: {topic}\nFORMAT: {chosen_format}\nOHANG: {chosen_tone}"
    if official_link:
        user_message += f"\nRasmiy havola: {official_link}"

    last_error = None
    for model_name in MODEL_CHAIN:
        # Gemini 2.5 seriyasi thinking_level'ni tushunmaydi (u faqat 3.x da bor),
        # shuning uchun 2.5 modellar uchun bu parametrsiz config ishlatamiz.
        if model_name.startswith("gemini-2.5"):
            config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
        else:
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
            )

        # har bir model uchun 2 marta urinamiz (vaqtinchalik 503'ni hisobga olib),
        # keyin keyingi modelga o'tamiz
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[user_message],
                    config=config,
                )
                raw = (response.text or "").strip()
                if attempt > 0 or model_name != MODEL_CHAIN[0]:
                    logger.info("Muvaffaqiyatli: model=%s, urinish=%d", model_name, attempt + 1)
                return _extract_json_block(raw)
            except genai_errors.APIError as e:
                last_error = e
                logger.warning(
                    "Gemini xato (model=%s, urinish %d/2): %s", model_name, attempt + 1, e
                )
                if attempt == 0:
                    time.sleep(2)
        # ushbu model 2 urinishda ham ishlamadi - keyingi modelga o'tamiz
        logger.warning("Model %s ishlamadi, keyingi modelga o'tilmoqda", model_name)

    raise last_error


FALLBACK_TEXT = """🇺🇿 O'ZBEKCHA
*{topic}* 💻

Bu dasturlashda muhim tushuncha 🚀. Uni chuqurroq o'rganish uchun rasmiy hujjatlarni o'qib chiqishni tavsiya qilamiz 📚.

Savollaringiz bo'lsa, izohda yozing! 💬

🇷🇺 РУССКИЙ
*{topic}* 💻

Это важная концепция в программировании 🚀. Рекомендуем изучить официальную документацию 📚.

Пишите вопросы в комментариях! 💬

🇬🇧 ENGLISH
*{topic}* 💻

This is an important concept in programming 🚀. We recommend checking the official documentation 📚.

Ask your questions in the comments! 💬"""


def generate_post(topic: str, official_link: str | None = None) -> dict:
    """
    Post generatsiya qiladi. Qaytaradi:
    {
        "text": "MarkdownV2 formatidagi tayyor post matni",
        "media_type": "image" | "video" | "none",
        "media_prompt": "media generatsiya uchun ingliz tilidagi tavsif"
    }
    """
    if GEMINI_API_KEY:
        try:
            raw_text, metadata = _generate_via_api(topic, official_link)
            if raw_text:
                media_type = metadata.get("media_type", "none")
                # Rasm generatsiyasi vaqtincha o'chirilgan (Gemini bepul tarifda
                # rasm uchun kvota bermayapti). Model xato qilib "image" qaytarsa
                # ham, buni "none"ga aylantiramiz - shunday qilib images.py
                # hech qachon chaqirilmaydi, keraksiz 429 xatosi bo'lmaydi.
                if media_type == "image":
                    media_type = "none"
                return {
                    "text": _escape_markdown_v2(raw_text),
                    "media_type": media_type,
                    "media_prompt": metadata.get("media_prompt", ""),
                }
        except Exception:
            logger.exception("Gemini orqali post generatsiyasida xatolik, fallback ishlatiladi")

    raw_text = FALLBACK_TEXT.format(topic=topic)
    return {
        "text": _escape_markdown_v2(raw_text),
        "media_type": "none",
        "media_prompt": "",
    }


CODE_SNIPPET_SYSTEM_PROMPT = """Berilgan dasturlash mavzusi bo'yicha qisqa, aniq kod namunasi yoz.
Qoidalar:
- 5-10 qator kod
- Faqat kodning o'zi, hech qanday izoh, tushuntirish, markdown belgilari (```) yozma
- Har qator 55 belgidan oshmasin
- Amaliy, ishlaydigan kod bo'lsin"""


def get_code_snippet(topic: str) -> str:
    """Video animatsiyasi uchun qisqa, sof kod namunasi qaytaradi. Muvaffaqiyatsiz bo'lsa bo'sh satr."""
    if not GEMINI_API_KEY:
        return ""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[f"Mavzu: {topic}"],
            config=types.GenerateContentConfig(system_instruction=CODE_SNIPPET_SYSTEM_PROMPT),
        )
        raw = (response.text or "").strip()
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        return raw.strip()
    except Exception:
        logger.exception("Kod namunasi olishda xatolik")
        return ""