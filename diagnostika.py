import logging
import os
from dotenv import load_dotenv

# content.py ichidagi logger.warning/info xabarlarini ham terminalda ko'rish uchun
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

load_dotenv()
key = os.environ.get("GEMINI_API_KEY")

print("=" * 60)
print("GEMINI_API_KEY:", "topildi" if key else "TOPILMADI")
print("=" * 60)
print()

import content

print("=" * 60)
print("MODEL_CHAIN (haqiqiy tartib):", content.MODEL_CHAIN)
print("=" * 60)
print()

print("=" * 60)
print("Har bir modelni ALOHIDA, to'g'ridan-to'g'ri sinaymiz")
print("(zanjir mantig'idan tashqarida, har birining aniq holatini ko'rish uchun)")
print("=" * 60)

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

client = genai.Client(api_key=key)

for model_name in content.MODEL_CHAIN:
    print()
    print(f"--- {model_name} ---")
    try:
        if model_name.startswith("gemini-2.5"):
            config = types.GenerateContentConfig(system_instruction="Sen yordamchisan.")
        else:
            config = types.GenerateContentConfig(
                system_instruction="Sen yordamchisan.",
                thinking_config=types.ThinkingConfig(thinking_level="low"),
            )
        response = client.models.generate_content(
            model=model_name,
            contents=["Faqat 'OK' deb javob ber."],
            config=config,
        )
        print(f"✅ {model_name}: MUVAFFAQIYATLI -> {response.text!r}")
    except genai_errors.APIError as e:
        print(f"❌ {model_name}: API XATO -> {type(e).__name__}: {e}")
    except Exception as e:
        print(f"❌ {model_name}: BOSHQA XATO -> {type(e).__name__}: {e}")

print()
print("=" * 60)
print("Endi to'liq zanjir mexanizmini (content._generate_via_api) sinaymiz")
print("=" * 60)
try:
    raw_text, metadata = content._generate_via_api("Python dekoratorlari", None)
    print("✅ ZANJIR MUVAFFAQIYATLI!")
    print()
    print("Qaytgan matn (birinchi 300 belgi):")
    print(raw_text[:300])
except Exception as e:
    print(f"❌ ZANJIR HAM ISHLAMADI: {type(e).__name__}: {e}")