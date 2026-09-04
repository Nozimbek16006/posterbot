# Dasturlash Postlari Boti (ko'p kanalli)

Telegram kanallariga dasturlash mavzusida postlarni avtomatik yoki buyruq bilan joylaydigan bot. Istalgan foydalanuvchi o'z kanalini botga qo'shib, mustaqil boshqarishi mumkin.

## 1-qadam: Bot yaratish

1. Telegram'da **@BotFather** ga yozing
2. `/newbot` buyrug'ini yuboring, nom va username bering
3. Sizga beriladigan **API token**ni saqlab qo'ying

## 2-qadam: Gemini API key olish (BEPUL)

1. https://aistudio.google.com/apikey ga kiring (Google hisobingiz bilan)
2. **Create API key** tugmasini bosing
3. Kredit karta so'ralmaydi. Bu kalitsiz bot faqat juda oddiy, bitta shablon postdan foydalanadi.

## 3-qadam: Botni Railway'ga joylash

1. https://railway.app ga kiring
2. **New Project** - loyihani joylang
3. **Variables** bo'limiga qo'shing:

   | Nomi | Qiymati |
   |------|---------|
   | `BOT_TOKEN` | BotFather'dan olgan token |
   | `GEMINI_API_KEY` | Gemini API key |
   | `DB_PATH` | `/data/bot_data.db` (Volume ulanganda) |

4. **MUHIM - Volume ulash** (ma'lumotlar yo'qolib ketmasligi uchun, pastdagi alohida bo'limga qarang)
5. Railway `nixpacks.toml` orqali FFmpeg va shriftlarni avtomatik o'rnatadi
6. Deploy tugagach, loglarda "Bot ishga tushdi (polling)" xabarini kuting

## 4-qadam (MUHIM): Railway Volume ulash

SQLite ma'lumotlar bazasi oddiy fayl sifatida ishlaydi, lekin Railway konteynerni qayta ishga tushirganda (har deploy, restart) fayl tizimi tozalanadi - Volume ulanmasa, barcha kanallar va mavzular yo'qolib ketadi.

1. Railway loyihangizda **+ New** - **Volume** tanlang
2. Volume'ni xizmatingizga ulang, **Mount Path**'ni `/data` deb belgilang
3. **Variables**'da `DB_PATH=/data/bot_data.db` qatorini qo'shing (yoki tekshiring)
4. Xizmatni qayta deploy qiling

Shundan keyin baza fayli Volume ichida saqlanadi va konteyner qayta ishga tushsa ham yo'qolmaydi.

## Botni qanday ishlatish (har bir foydalanuvchi uchun)

### Yangi kanal qo'shish

1. Botni o'z kanalingizga admin qiling ("Post Messages" huquqi bilan)
2. Botga shaxsiy chatda yozing: `/addchannel`
3. Bot sizdan ketma-ket so'raydi:
   - Kanal username yoki ID (masalan `@mykanalim`)
   - Mavzular ro'yxati (har birini alohida qatorda)
   - Kunlik post vaqti (HH:MM, UTC bo'yicha) yoki `/skip`

### Buyruqlar

- `/addchannel` - yangi kanal qo'shish (bosqichma-bosqich)
- `/mychannels` - sizning kanallaringiz ro'yxati va jadvali
- `/post [mavzu]` - hozir post joylash (mavzu ko'rsatilmasa, tasodifiy tanlanadi)
- `/schedule HH:MM` - kunlik avtomatik postni yoqish/o'zgartirish
- `/unschedule` - avtomatik postni o'chirish
- `/topics` - kanal mavzulari ro'yxati
- `/addtopic <mavzu>` - yangi mavzu qo'shish
- `/addadmin <user_id>` - kanalingizga qo'shimcha admin qo'shish (ID'ni @userinfobot orqali olish mumkin)

Eslatma: agar sizda bir nechta kanal bo'lsa, buyruq yuborganingizda bot qaysi kanal uchun ekanini so'raydi (tugmalar bilan). Bitta kanal bo'lsa, avtomatik o'shani ishlatadi.

Vaqt zonasi: barcha vaqtlar UTC bo'yicha. Toshkent vaqti UTC+5, ya'ni Toshkentda soat 18:00 da post chiqishi uchun `13:00` deb yozing.

## Lokal test qilish

```bash
pip install -r requirements.txt
export BOT_TOKEN="sizning_tokeningiz"
export GEMINI_API_KEY="sizning_gemini_keyingiz"
python bot.py
```

FFmpeg lokal kerak bo'ladi (video generatsiya uchun):

```bash
sudo apt install ffmpeg fonts-dejavu-core
```

Lokal ishga tushirganda baza `bot_data.db` fayli sifatida joriy papkada yaratiladi (alohida sozlash shart emas).