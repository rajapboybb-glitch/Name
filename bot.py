import asyncio
import logging
import os
import random
import sqlite3
import threading
from flask import Flask

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==================== RENDER UCHUN WEB SERVER ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot muvaffaqiyatli ishlayapti!"

def run_flask():
    # Render beradigan PORT bo'yicha serverni yuritish
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "8825101379:AAFdj5_o4ewJfG6WANspgoGYGV8X70Fgtkg"
ADMIN_IDS = [8923173548]  # Admin Telegram ID si

# FSM (State) - Ommaviy xabar yuborish uchun
class BroadcastState(StatesGroup):
    waiting_for_message = State()

# ==================== MA'LUMOTLAR BAZASI ====================
def init_db():
    conn = sqlite3.connect("contest_bot.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            referrer_id INTEGER,
            points INTEGER DEFAULT 0,
            is_verified INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            title TEXT NOT NULL,
            invite_link TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()

def add_user(user_id, full_name, referrer_id=None):
    conn = sqlite3.connect("contest_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (user_id, full_name, referrer_id) VALUES (?, ?, ?)",
            (user_id, full_name, referrer_id)
        )
        conn.commit()
    conn.close()

def update_verification(user_id, status=1):
    conn = sqlite3.connect("contest_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_verified = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

def add_point(user_id):
    conn = sqlite3.connect("contest_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("contest_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    data = cursor.fetchone()
    conn.close()
    return data

def get_all_user_ids():
    conn = sqlite3.connect("contest_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    return [u[0] for u in users]

def get_verified_users():
    conn = sqlite3.connect("contest_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, full_name, points FROM users WHERE is_verified = 1")
    data = cursor.fetchall()
    conn.close()
    return data

def add_channel(channel_id, title, invite_link):
    conn = sqlite3.connect("contest_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO channels (channel_id, title, invite_link) VALUES (?, ?, ?)",
        (str(channel_id), title, invite_link)
    )
    conn.commit()
    conn.close()

def remove_channel(db_id):
    conn = sqlite3.connect("contest_bot.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE id = ?", (db_id,))
    conn.commit()
    conn.close()

def get_channels():
    conn = sqlite3.connect("contest_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, channel_id, title, invite_link FROM channels")
    channels = cursor.fetchall()
    conn.close()
    return channels

# ==================== BOT VA DISPATCHER ====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def check_all_subscriptions(user_id: int) -> tuple[bool, list]:
    channels = get_channels()
    unsubscribed = []
    
    for ch in channels:
        ch_db_id, ch_id, title, link = ch
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                unsubscribed.append((title, link))
        except Exception as e:
            logging.error(f"Kanalni tekshirishda xatolik ({ch_id}): {e}")
            unsubscribed.append((title, link))
            
    return len(unsubscribed) == 0, unsubscribed

def sub_keyboard(unsubscribed_channels):
    buttons = []
    for title, link in unsubscribed_channels:
        buttons.append([InlineKeyboardButton(text=f"📢 {title}", url=link)])
    
    buttons.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Referal havola", callback_data="get_link")],
        [InlineKeyboardButton(text="📊 Mening statistikam", callback_data="my_stats")]
    ])

# ==================== USER HANDLERLARI ====================

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        ref_candidate = int(args[1])
        if ref_candidate != user_id:
            referrer_id = ref_candidate

    add_user(user_id, full_name, referrer_id)

    is_subscribed, unsubscribed = await check_all_subscriptions(user_id)
    if is_subscribed:
        update_verification(user_id, 1)
        await message.answer(
            f"Salom {full_name}! Siz tanlovda muvaffaqiyatli ishtirok etyapsiz.",
            reply_markup=main_keyboard()
        )
    else:
        await message.answer(
            f"Salom {full_name}!\nTanlovda qatnashish uchun quyidagi barcha kanallarga obuna boʻling:",
            reply_markup=sub_keyboard(unsubscribed)
        )

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    is_subscribed, unsubscribed = await check_all_subscriptions(user_id)

    if is_subscribed:
        user_data = get_user(user_id)
        if user_data and user_data[4] == 0:
            update_verification(user_id, 1)
            referrer_id = user_data[2]
            if referrer_id:
                add_point(referrer_id)
                try:
                    await bot.send_message(
                        referrer_id, 
                        "🎉 Siz taklif qilgan doʻst barcha kanallarga obuna boʻldi! Sizga +1 ball berildi."
                    )
                except Exception:
                    pass

        await call.message.edit_text(
            "✅ Barcha obunalar tasdiqlandi! Siz tanlovdasiz.",
            reply_markup=main_keyboard()
        )
    else:
        await call.answer("❌ Siz hali barcha kanallarga obuna boʻlmadingiz!", show_alert=True)
        await call.message.edit_reply_markup(reply_markup=sub_keyboard(unsubscribed))

@dp.callback_query(F.data == "get_link")
async def get_link_callback(call: types.CallbackQuery):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"
    await call.message.answer(
        f"Sizning taklif havolangiz:\n`{ref_link}`\n\n"
        f"Ushbu havolani doʻstlaringizga yuboring. Barcha kanallarga obuna boʻlgan har bir doʻstingiz uchun +1 ochko olasiz!",
        parse_mode="Markdown"
    )
    await call.answer()

@dp.callback_query(F.data == "my_stats")
async def my_stats_callback(call: types.CallbackQuery):
    user_data = get_user(call.from_user.id)
    if user_data:
        points = user_data[3]
        await call.message.answer(f"📊 **Statistika:**\nSiz toʻplagan ballar: **{points}** ball")
    await call.answer()

# ==================== ADMIN PANEL HANDLERLARI ====================

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    users = get_all_user_ids()
    verified = get_verified_users()
    channels = get_channels()
    
    text = (
        f"👑 **Admin Panel**\n\n"
        f"👤 Jami foydalanuvchilar: **{len(users)}** ta\n"
        f"✅ Tasdiqlangan ishtirokchilar: **{len(verified)}** ta\n"
        f"📢 Majburiy kanallar soni: **{len(channels)}** ta\n\n"
        f"**Buyruqlar:**\n"
        f"📢 Ommaviy xabar yuborish: `/send`\n"
        f"➕ Kanal qoʻshish: `/add_channel <id> <nomi> <link>`\n"
        f"➖ Kanal oʻchirish: `/del_channel <db_id>`\n"
        f"📋 Kanallar roʻyxati: `/channels`\n"
        f"🏆 Gʻoliblarni aniqlash: `/winner <soni>`"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("send"))
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await state.set_state(BroadcastState.waiting_for_message)
    await message.answer(
        "📢 **Ommaviy xabar yuborish rejimi.**\n\n"
        "Barcha foydalanuvchilarga yubormoqchi boʻlgan xabaringizni kiriting.\n"
        "Jarayonni bekor qilish uchun: `/cancel` deb yuboring."
    )

@dp.message(Command("cancel"), BroadcastState.waiting_for_message)
async def broadcast_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Ommaviy xabar yuborish bekor qilindi.")

@dp.message(BroadcastState.waiting_for_message)
async def broadcast_process(message: types.Message, state: FSMContext):
    await state.clear()
    
    user_ids = get_all_user_ids()
    if not user_ids:
        await message.answer("Bazada foydalanuvchilar topilmadi.")
        return

    status_msg = await message.answer(f"🚀 Ommaviy xabar yuborish boshlandi...\nJami: {len(user_ids)} ta foydalanuvchi.")
    
    success = 0
    failed = 0

    for u_id in user_ids:
        try:
            await message.copy_to(chat_id=u_id)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ **Ommaviy xabar yuborildi!**\n\n"
        f"🟢 Yetkazildi: **{success}** ta\n"
        f"🔴 Yetkazilmadi: **{failed}** ta"
    )

@dp.message(Command("add_channel"))
async def add_channel_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer(
            "⚠️ Format: `/add_channel <kanal_id_yoki_username> <kanal_nomi> <kanal_linki>`\n"
            "Masalan: `/add_channel @mychannel Mening_Kanalim https://t.me/mychannel`",
            parse_mode="Markdown"
        )
        return

    ch_id = args[1]
    title = args[2].replace("_", " ")
    link = args[3]

    try:
        member = await bot.get_chat_member(chat_id=ch_id, user_id=(await bot.get_me()).id)
        if member.status not in ["administrator", "creator"]:
            await message.answer("❌ **Xatolik:** Bot bu kanalda **admin** emas!")
            return
    except Exception as e:
        await message.answer(f"❌ **Kanal topilmadi:** `{e}`", parse_mode="Markdown")
        return

    add_channel(ch_id, title, link)
    await message.answer(f"✅ **{title}** kanali qoʻshildi!")

@dp.message(Command("channels"))
async def list_channels_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    channels = get_channels()
    if not channels:
        await message.answer("📢 Hozircha majburiy kanal yoʻq.")
        return

    text = "📢 **Majburiy kanallar roʻyxati:**\n\n"
    for ch in channels:
        db_id, ch_id, title, link = ch
        text += f"ID: `{db_id}` | [{title}]({link}) (Chat ID: `{ch_id}`)\n"
    
    text += "\nOʻchirish uchun: `/del_channel <ID>`"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("del_channel"))
async def del_channel_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("⚠️ Format: `/del_channel <ID>`", parse_mode="Markdown")
        return

    db_id = int(args[1])
    remove_channel(db_id)
    await message.answer(f"🗑 ID `{db_id}` boʻlgan kanal oʻchirildi.")

@dp.message(Command("winner"))
async def pick_winner(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.text.split()
    count = 1
    if len(args) > 1 and args[1].isdigit():
        count = int(args[1])

    users = get_verified_users()
    if not users:
        await message.answer("Ishtirokchilar topilmadi.")
        return

    pool = []
    for u in users:
        u_id, name, pts = u
        pool.extend([(u_id, name)] * (1 + pts))

    winners = random.sample(pool, min(count, len(set(pool))))
unique_winners = list({w[0]: w[1] for w in winners}.items())
    text = "🏆 **GʻOLIBLAR:**\n\n"
    for idx, (w_id, name) in enumerate(unique_winners, 1):
        text += f"{idx}. [{name}](tg://user?id={w_id}) (ID: `{w_id}`)\n"

    await message.answer(text, parse_mode="Markdown")

# ==================== ISHGA TUSHIRISH ====================
async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    # 1. Flask serverini alohida oqimda (Thread) ishga tushirish (Render uchun)
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 2. Telegram botni polling rejimida ishga tushirish
    asyncio.run(main())
    