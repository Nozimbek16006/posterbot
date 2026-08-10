import logging
import os
import re
import json

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

SYSTEM_PROMPT = """Sen Telegram kanali uchun dasturlash mavzusida post yozuvchisan.
Har bir post 3 tilda bo'lishi kerak: avval o'zbek tilida (lotin alifbosida), keyin rus tilida, keyin ingliz tilida.
Har til bo'limi bayroq va til nomi bilan boshlanadi: 🇺🇿 O'ZBEKCHA, 🇷🇺 РУССКИЙ, 🇬🇧 ENGLISH.

Har bir til bo'limida:
- Qiziqtiruvchi sarlavha (bold, ** bilan)
- 60-100 so'z atrofida tushuntirish
- Amaliy misol yoki kod bo'lagi (agar mavzuga mos bo'lsa, kod uchtaga backtick ichida bo'lsin: ```kod```)
- Mavzuga mos 4-8 ta emoji tabiiy joylashtirilgan (sarlavhada, ro'yxat belgisi o'rnida, muhim so'zlar yonida)

Agar foydalanuvchi xabarida "Rasmiy havola:" ko'rsatilgan bo'lsa, o'sha havolani postning eng oxiriga, "🔗 Batafsil:" belgisi bilan bitta marta qo'sh (uch tilga alohida-alohida takrorlama, faqat oxirida bitta umumiy havola yetarli). Agar havola berilmagan bo'lsa, havola qo'shma.

Post oxirida (havoladan keyin, agar havola bo'lsa) shu formatda JSON metama'lumot bloki qo'sh, uch qo'shtirnoq bilan o'ralgan:
```json
{
  "media_type": "image" yoki "video" yoki "none",
  "media_prompt": "agar media_type image yoki video bo'lsa, shu mavzuni tasvirlaydigan vizual tavsif (ingliz tilida, rasm/video generatsiya modeliga so'rov sifatida ishlatiladi). Masalan: 'a clean minimal illustration of a Python decorator wrapping a function, flat design, code editor aesthetic, dark theme, blue and purple accents'"
}
```

media_type tanlash mezoni: agar mavzu vizual tushuncha bo'lsa (masalan arxitektura, oqim, diagramma, 3D effekt) - "image" tanla. Agar mavzu jarayon yoki animatsiya bilan yaxshi tushuntiriladigan bo'lsa (masalan animatsiya, o'zgarish, davr) - "video" tanla. Aksariyat postlar uchun "image" mos, "video" faqat aynan animatsiya/jarayon mavzulariga tanlansin - hammasi uchun emas.

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


def _generate_via_api(topic: str, official_link: str | None) -> tuple[str, dict]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    user_message = f"Mavzu: {topic}"
    if official_link:
        user_message += f"\nRasmiy havola: {official_link}"

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[user_message],
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    raw = (response.text or "").strip()
    return _extract_json_block(raw)


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
                return {
                    "text": _escape_markdown_v2(raw_text),
                    "media_type": metadata.get("media_type", "none"),
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
            model="gemini-2.5-flash-lite",
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
