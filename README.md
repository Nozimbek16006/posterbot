# Dasturlash Postlari Boti

Telegram kanaliga dasturlash mavzusida postlarni avtomatik yoki buyruq bilan joylaydigan bot.

## 1-qadam: Bot yaratish

1. Telegram'da **@BotFather** ga yozing
2. `/newbot` buyrug'ini yuboring, nom va username bering
3. Sizga beriladigan **API token**ni saqlab qo'ying (masalan: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`)

## 2-qadam: Botni kanalga admin qilish

1. Kanalingiz sozlamalariga kiring → **Administrators** → **Add Administrator**
2. Yaratgan botingizni toping va qo'shing
3. Kamida **"Post Messages"** huquqini yoqib qo'ying

## 3-qadam: Kanal ID'sini olish

- Agar kanal ochiq (public) bo'lsa: username'ini ishlating, masalan `@mykanalim`
- Agar yopiq (private) bo'lsa: kanal ID'si kerak (masalan `-1001234567890`). Buni olish uchun kanalga biror xabar yuboring, keyin uni **@userinfobot** ga forward qiling — u ID'ni ko'rsatadi.

## 4-qadam: O'zingizning Telegram User ID'ingizni olish (ixtiyoriy, lekin tavsiya etiladi)

Bu qadam faqat SIZ buyruq bera olishingiz uchun kerak (boshqalar emas).
**@userinfobot** ga yozing — u sizga ID raqamingizni beradi.

## 5-qadam: Gemini API key olish (BEPUL — matn, rasm va video uchun yagona kalit)

1. https://aistudio.google.com/apikey ga kiring (Google hisobingiz bilan kirasiz)
2. **Create API key** tugmasini bosing
3. Kredit karta so'ralmaydi, muddati tugamaydi — kuniga bir necha yuz so'rovgacha bepul limit bor, kunlik 1-2 post uchun bu chegaraga hech qachon yetmaysiz
4. **Muhim:** bu bitta kalit botning barcha AI funksiyalarini ta'minlaydi — 3 tilda post yozish, emoji, va rasm generatsiyasi. Bu kalitsiz bot faqat juda oddiy, bitta shablon postdan foydalanadi (matn, rasmsiz)

**Eslatma:** Video generatsiyasi uchun alohida to'lov yo'q — u serverning o'zida (FFmpeg bilan, butunlay bepul) ishlaydi, faqat kod namunasini olish uchun yuqoridagi Gemini kaliti ishlatiladi.

## 6-qadam: Railway'ga joylash

1. https://railway.app ga kiring (GitHub akkaunt bilan kirish qulay)
2. **New Project** → **Deploy from GitHub repo** (avval shu papkani GitHub'ga yuklashingiz kerak) yoki **Empty Project** yaratib, keyin fayllarni qo'lda yuklang
3. Loyiha ochilgach, **Variables** bo'limiga o'ting va quyidagilarni qo'shing:

   | Nomi | Qiymati |
   |------|---------|
   | `BOT_TOKEN` | BotFather'dan olgan token |
   | `CHANNEL_ID` | Kanal username yoki ID (masalan `@mykanalim`) |
   | `ADMIN_USER_ID` | Sizning Telegram user ID'ingiz (4-qadamdan) |
   | `GEMINI_API_KEY` | Gemini API key (5-qadamdan) |

4. Railway `nixpacks.toml` fayli orqali avtomatik FFmpeg va shriftlarni ham o'rnatadi (video generatsiya uchun kerak)
5. Railway `requirements.txt` va `Procfile`ni avtomatik aniqlab, botni ishga tushiradi
6. **Deployments** bo'limida loglarni kuzatib, "Bot ishga tushdi (polling)" degan xabarni ko'rishingiz kerak

## Foydalanish

Botga (yoki guruhga, agar admin cheklamasangiz) shu buyruqlarni yuboring:

- `/post` — tasodifiy mavzudan hozir post joylaydi
- `/post Python dekoratorlari` — aniq mavzu bilan post joylaydi
- `/schedule 18:00` — har kuni soat 18:00 (UTC) da avtomatik post yoqadi
- `/unschedule` — avtomatik postni o'chiradi
- `/topics` — mavjud mavzular ro'yxatini ko'rsatadi
- `/addtopic Yangi mavzu nomi` — ro'yxatga yangi mavzu qo'shadi

**Eslatma:** `/schedule` vaqti UTC bo'yicha. Toshkent vaqti UTC+5, ya'ni Toshkentda soat 18:00 da post chiqishi uchun `/schedule 13:00` deb yozing.

## Lokal test qilish (Railway'ga joylashdan oldin)

```bash
pip install -r requirements.txt
export BOT_TOKEN="sizning_tokeningiz"
export CHANNEL_ID="@mykanalim"
export ADMIN_USER_ID="sizning_id"
export GEMINI_API_KEY="sizning_gemini_keyingiz"
python bot.py
```

**Eslatma:** video generatsiya lokal kompyuteringizda ishlashi uchun FFmpeg o'rnatilgan bo'lishi kerak:

```bash
sudo apt install ffmpeg fonts-dejavu-core
```
