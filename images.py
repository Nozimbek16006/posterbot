import logging
import os

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


def generate_image(prompt: str, output_path: str) -> bool:
    """
    Berilgan tavsif bo'yicha rasm generatsiya qilib, output_path'ga saqlaydi.
    Muvaffaqiyatli bo'lsa True, aks holda False qaytaradi.
    """
    if not GEMINI_API_KEY:
        return False

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="16:9"),
            ),
        )
        for part in response.parts:
            if getattr(part, "inline_data", None) is not None:
                with open(output_path, "wb") as f:
                    f.write(part.inline_data.data)
                return True
        logger.warning("Gemini rasm qaytarmadi (bo'sh javob): %r", prompt[:80])
        return False
    except Exception:
        logger.exception("Rasm generatsiyasida xatolik")
        return False
