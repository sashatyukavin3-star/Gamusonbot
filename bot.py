#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gamebot @Gamusonbot - Игровой Telegram бот
6 игр + профиль + рейтинг + ежедневный бонус + админка

Запуск: pip install -r requirements.txt && python bot.py
"""

import asyncio
import logging
import random
import sqlite3
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, PreCheckoutQueryHandler
)
try:
    from shop_config import SHOP_GIFTS, POINTS_PACKAGES, ADMIN_IDS
except ImportError:
    SHOP_GIFTS = [
        {"gift_id": "5170145012310081615", "emoji": "💝", "name": "Сердечко", "stars": 15, "points": 500},
        {"gift_id": "5170250947678437525", "emoji": "🎁", "name": "Подарок", "stars": 25, "points": 900},
        {"gift_id": "5170144170496491616", "emoji": "🎂", "name": "Тортик", "stars": 50, "points": 1800},
        {"gift_id": "5168043875654172773", "emoji": "🏆", "name": "Кубок", "stars": 100, "points": 3800},
    ]
    POINTS_PACKAGES = [
        {"stars": 25, "points": 1000, "title": "1000 поинтов", "label": "⭐ 25 — 1000 points"},
        {"stars": 100, "points": 5000, "title": "5000 поинтов", "label": "⭐ 100 — 5000 points"},
    ]
    ADMIN_IDS = [8206258615]

try:
    from channel_config import CHANNEL_USERNAME, CHANNEL_ID
except ImportError:
    CHANNEL_USERNAME = "@gamefi_hunters"
    CHANNEL_ID = -1003642138077

# --- CONFIG ---
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "8652086324:AAEXTu3NS3Xl8G1NYrhYJmKF-bJnr-vtk8Q")
DB_PATH = Path(__file__).parent / "gamebot.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# для бесплатных хостингов Render/Fly/Railway - health-check сервер
# Render требует открытый порт, иначе будет считать что сервис упал
HEALTH_PORT = int(os.getenv("PORT", os.getenv("HEALTH_PORT", "10000")))

# --- ВОПРОСЫ ДЛЯ ВИКТОРИНЫ ---
QUIZ_QUESTIONS = [
    {"q": "Столица Японии?", "a": ["Сеул", "Пекин", "Токио", "Бангкок"], "c": 2},
    {"q": "Сколько планет в Солнечной системе?", "a": ["7", "8", "9", "10"], "c": 1},
    {"q": "Кто написал 'Война и мир'?", "a": ["Достоевский", "Толстой", "Пушкин", "Гоголь"], "c": 1},
    {"q": "Самый большой океан?", "a": ["Атлантический", "Индийский", "Северный Ледовитый", "Тихий"], "c": 3},
    {"q": "В каком году началась Вторая мировая?", "a": ["1938", "1939", "1940", "1941"], "c": 1},
    {"q": "Язык программирования этого бота?", "a": ["Java", "Python", "C++", "Go"], "c": 1},
    {"q": "Какая валюта в Швейцарии?", "a": ["Евро", "Франк", "Крона", "Фунт"], "c": 1},
    {"q": "Сколько сердец у осьминога?", "a": ["1", "2", "3", "4"], "c": 2},
    {"q": "Что такое 2 + 2 * 2 ?", "a": ["6", "8", "4", "12"], "c": 0},
    {"q": "Самый быстрый наземный зверь?", "a": ["Гепард", "Тигр", "Леопард", "Ягуар"], "c": 0},
    {"q": "Кто создал Telegram?", "a": ["Цукерберг", "Дуров", "Маск", "Безос"], "c": 1},
    {"q": "Сколько бит в байте?", "a": ["4", "8", "16", "32"], "c": 1},
    {"q": "Столица Казахстана?", "a": ["Алматы", "Астана", "Шымкент", "Караганда"], "c": 1},
    {"q": "Какой элемент обозначается как Au?", "a": ["Серебро", "Золото", "Алюминий", "Аргон"], "c": 1},
    {"q": "Сколько часов в сутках?", "a": ["12", "24", "48", "22"], "c": 1},
]

# --- БАЗА ---
def db_init():
    con = _db()
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        points INTEGER DEFAULT 0,
        games_played INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        last_daily TEXT,
        created_at TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS shop_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        gift_id TEXT,
        gift_name TEXT,
        stars INTEGER,
        cost_points INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS star_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        stars INTEGER,
        points INTEGER,
        payload TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )""")
    con.commit()
    con.close()

def _db():
    # WAL + большой timeout против database is locked
    con = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False, isolation_level=None)
    try:
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA busy_timeout=30000;")
        con.execute("PRAGMA synchronous=NORMAL;")
    except: pass
    return con

def db_upsert_user(user):
    con = _db()
    cur = con.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    now = datetime.now().isoformat()
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, username, first_name, created_at) VALUES (?,?,?,?)",
                    (user.id, user.username or "", user.first_name or "", now))
    else:
        cur.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?",
                    (user.username or "", user.first_name or "", user.id))
    con.commit()
    con.close()

def db_add_points(user_id, delta, game_inc=1, win_inc=0):
    for attempt in range(5):
        try:
            con = _db()
            cur = con.cursor()
            cur.execute("BEGIN IMMEDIATE")
            cur.execute("UPDATE users SET points=points+?, games_played=games_played+?, wins=wins+? WHERE user_id=?",
                        (delta, game_inc, win_inc, user_id))
            con.commit()
            con.close()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 4:
                import time; time.sleep(0.2*(attempt+1))
                continue
            raise
        finally:
            try: con.close()
            except: pass

def db_get_user(user_id):
    con = _db()
    cur = con.cursor()
    cur.execute("SELECT user_id, username, first_name, points, games_played, wins, last_daily FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row

def db_top(limit=10):
    con = _db()
    cur = con.cursor()
    cur.execute("SELECT username, first_name, points, wins, games_played FROM users ORDER BY points DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    con.close()
    return rows

def db_get_points(user_id):
    con = _db()
    cur = con.cursor()
    cur.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else 0

def db_create_order(user_id, gift):
    for attempt in range(5):
        try:
            con = _db()
            cur = con.cursor()
            cur.execute("BEGIN IMMEDIATE")
            cur.execute("INSERT INTO shop_orders (user_id, gift_id, gift_name, stars, cost_points, status, created_at) VALUES (?,?,?,?,?,?,?)",
                        (user_id, gift["gift_id"], gift["name"], gift["stars"], gift["points"], "pending", datetime.now().isoformat()))
            oid = cur.lastrowid
            con.commit()
            con.close()
            return oid
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 4:
                import time; time.sleep(0.2*(attempt+1))
                continue
            raise

def db_get_orders(user_id=None, status=None, limit=20):
    con = _db()
    cur = con.cursor()
    q = "SELECT id, user_id, gift_name, stars, cost_points, status, created_at FROM shop_orders"
    params = []
    wh = []
    if user_id:
        wh.append("user_id=?"); params.append(user_id)
    if status:
        wh.append("status=?"); params.append(status)
    if wh:
        q += " WHERE " + " AND ".join(wh)
    q += " ORDER BY id DESC LIMIT ?"; params.append(limit)
    cur.execute(q, tuple(params))
    rows = cur.fetchall()
    con.close()
    return rows

def is_admin(user_id):
    return user_id in ADMIN_IDS

# --- Хелперы для Stars/Gifts (совместимость с PTB 21.6 — делаем raw API) ---
async def get_bot_stars(bot):
    # пробуем PTB метод, если есть, иначе raw
    try:
        if hasattr(bot, 'get_my_star_balance'):
            bal = await bot.get_my_star_balance()
            return getattr(bal, 'amount', 0)
        if hasattr(bot, 'getMyStarBalance'):
            bal = await bot.getMyStarBalance()
            return getattr(bal, 'amount', 0)
    except:
        pass
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.telegram.org/bot{TOKEN}/getMyStarBalance") as r:
                j = await r.json()
                if j.get("ok"):
                    return j["result"].get("amount", 0)
    except Exception as e:
        log.warning(f"getMyStarBalance failed: {e}")
    return 0

async def send_gift_raw(bot, chat_id, gift_id):
    # пробуем PTB метод
    try:
        if hasattr(bot, 'send_gift'):
            return await bot.send_gift(chat_id=chat_id, gift_id=gift_id)
        if hasattr(bot, 'sendGift'):
            return await bot.sendGift(chat_id=chat_id, gift_id=gift_id)
    except Exception as e:
        log.warning(f"PTB send_gift failed, fallback raw: {e}")
    # fallback raw
    import aiohttp
    async with aiohttp.ClientSession() as s:
        async with s.post(f"https://api.telegram.org/bot{TOKEN}/sendGift", data={"chat_id": str(chat_id), "gift_id": gift_id}) as r:
            j = await r.json()
            if not j.get("ok"):
                raise Exception(j.get("description", "sendGift failed"))
            return j["result"]

# --- КЛАВИАТУРЫ ---
def main_menu_kb():
    kb = [
        [KeyboardButton("🎮 Игры"), KeyboardButton("👤 Профиль")],
        [KeyboardButton("🏆 Топ"), KeyboardButton("🎁 Бонус")],
        [KeyboardButton("🎁 Магазин"), KeyboardButton("ℹ️ Помощь")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def games_inline_kb():
    kb = [
        [InlineKeyboardButton("🎲 Угадай число", callback_data="game_guess"),
         InlineKeyboardButton("✊ КНБ", callback_data="game_rps")],
        [InlineKeyboardButton("🧠 Викторина", callback_data="game_quiz"),
         InlineKeyboardButton("🪙 Орёл и Решка", callback_data="game_coin")],
        [InlineKeyboardButton("🎰 Слоты", callback_data="game_slots"),
         InlineKeyboardButton("🎯 Дартс / Кубик", callback_data="game_dice")],
        [InlineKeyboardButton("🎁 Магазин", callback_data="shop"),
         InlineKeyboardButton("🏆 Рейтинг", callback_data="top")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile"),
         InlineKeyboardButton("💎 Купить поинты", callback_data="buy_points")]
    ]
    return InlineKeyboardMarkup(kb)

def shop_kb():
    rows = []
    for g in SHOP_GIFTS:
        rows.append([InlineKeyboardButton(f"{g['emoji']} {g['name']} — {g['points']} pts ({g['stars']} ⭐)", callback_data=f"shop_buy_{g['gift_id']}")])
    rows.append([InlineKeyboardButton("💎 Купить поинты за ⭐", callback_data="buy_points")])
    rows.append([InlineKeyboardButton("👤 Мой баланс", callback_data="profile"), InlineKeyboardButton("⬅️ Меню", callback_data="menu")])
    return InlineKeyboardMarkup(rows)

def buy_points_kb():
    rows = []
    for p in POINTS_PACKAGES:
        rows.append([InlineKeyboardButton(p["label"], callback_data=f"buy_pack_{p['stars']}")])
    rows.append([InlineKeyboardButton("⬅️ В магазин", callback_data="shop")])
    return InlineKeyboardMarkup(rows)

def rps_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✊ Камень", callback_data="rps_rock"),
         InlineKeyboardButton("✋ Бумага", callback_data="rps_paper"),
         InlineKeyboardButton("✌️ Ножницы", callback_data="rps_scissors")],
        [InlineKeyboardButton("⬅️ В меню", callback_data="menu")]
    ])

def coin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🦅 Орёл", callback_data="coin_heads"),
         InlineKeyboardButton("🌙 Решка", callback_data="coin_tails")],
        [InlineKeyboardButton("⬅️ В меню", callback_data="menu")]
    ])

def dice_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Кубик", callback_data="dice_🎲"),
         InlineKeyboardButton("🎯 Дартс", callback_data="dice_🎯"),
         InlineKeyboardButton("🏀 Баскет", callback_data="dice_🏀")],
        [InlineKeyboardButton("⚽ Футбол", callback_data="dice_⚽"),
         InlineKeyboardButton("🎳 Боулинг", callback_data="dice_🎳"),
         InlineKeyboardButton("🎰 Слоты", callback_data="dice_🎰")],
        [InlineKeyboardButton("⬅️ В меню", callback_data="menu")]
    ])

# --- ХЭНДЛЕРЫ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_upsert_user(user)
    name = user.first_name or "друг"
    text = (
        f"Привет, {name}! 👋\n\n"
        f"Я — <b>Gamebot @Gamusonbot</b> — игровой бот с 6 играми:\n\n"
        f"🎲 <b>Угадай число</b> — угадаешь за 7 попыток?\n"
        f"✊ <b>Камень-Ножницы-Бумага</b> — классика\n"
        f"🧠 <b>Викторина</b> — 15 вопросов на эрудицию\n"
        f"🪙 <b>Орёл и Решка</b> — испытай удачу\n"
        f"🎰 <b>Слоты</b> — крути барабан\n"
        f"🎯 <b>Кубик / Дартс / Баскет</b> — Telegram Dice\n\n"
        f"💰 За победы даю <b>поинты</b> — они идут в рейтинг.\n"
        f"🎁 Магазин: меняй поинты на <b>Stars и подарки Telegram</b> в /shop!\n"
        f"💎 Не хватает? Купи поинты за ⭐ в /buy\n"
        f"🎁 Не забудь забрать <b>ежедневный бонус</b>!\n\n"
        f"Жми кнопку ниже, чтобы начать:"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
                                    reply_markup=main_menu_kb())
    await update.message.reply_text("🎮 Выбери игру или загляни в магазин:", reply_markup=games_inline_kb())

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎮 Главное меню — выбирай игру:", reply_markup=games_inline_kb())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>ℹ️ Помощь по Gamebot</b>\n\n"
        "<b>Команды:</b>\n"
        "/start — приветствие и меню\n"
        "/menu — список игр\n"
        "/shop — 🎁 магазин подарков за поинты\n"
        "/buy — 💎 купить поинты за Stars\n"
        "/profile — твой профиль и поинты\n"
        "/top — топ-10 игроков\n"
        "/bonus — ежедневный бонус +50\n"
        "/help — эта справка\n"
        "/admin — 👑 админка (только для админа)\n\n"
        "<b>Как играть:</b>\n"
        "• Просто жми кнопки. В «Угадай число» пиши число в чат.\n"
        "• В викторине выбирай вариант ответа.\n"
        "• Поинты начисляются автоматически и сохраняются.\n\n"
        "<b>Монетизация:</b>\n"
        "• Выигрывай поинты в играх → меняй в /shop на подарки Telegram (15-100 ⭐)\n"
        "• Не хватает поинтов? Купи в /buy за Stars — Stars идут админу\n\n"
        "<b>Админка BotFather:</b>\n"
        "Не забудь настроить описание, аватар и команды в @BotFather.\n"
        "Если токен утек — /revoke там же.\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # поддерживает и message и callback
    user = update.effective_user
    db_upsert_user(user)
    row = db_get_user(user.id)
    if not row:
        await (update.message or update.callback_query.message).reply_text("Профиль не найден. Нажми /start")
        return
    _, username, first_name, points, games, wins, last_daily = row
    uname = f"@{username}" if username else first_name
    wr = f"{wins}/{games}" if games else "0/0"
    winrate = f"{wins*100//games}%" if games else "—"
    text = (
        f"👤 <b>Профиль</b> {uname}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💰 Поинты: <b>{points}</b>\n"
        f"🎮 Игр сыграно: <b>{games}</b>\n"
        f"🏆 Побед: <b>{wins}</b> ({wr}, {winrate})\n"
        f"🎁 Бонус: {'доступен /bonus' if can_claim_bonus(last_daily) else 'уже получен сегодня'}\n"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏆 Топ", callback_data="top"),
                                InlineKeyboardButton("🎮 Игры", callback_data="menu")]])
    target = update.message or (update.callback_query.message if update.callback_query else None)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await target.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db_top(10)
    if not rows:
        text = "🏆 Топ пока пуст — стань первым! Сыграй любую игру."
    else:
        lines = ["🏆 <b>Топ-10 игроков</b>\n"]
        medals = ["🥇","🥈","🥉"] + ["\n4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        # simpler
        for i, (uname, fname, pts, wins, games) in enumerate(rows, 1):
            name = f"@{uname}" if uname else (fname or f"Игрок {i}")
            # escape
            name = name.replace("<","").replace(">","")
            medal = ["🥇","🥈","🥉"][i-1] if i<=3 else f"{i}."
            lines.append(f"{medal} {name} — <b>{pts}</b> pts ({wins} побед)")
        text = "\n".join(lines)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("👤 Мой профиль", callback_data="profile"),
                                InlineKeyboardButton("🎮 Играть", callback_data="menu")]])
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

def can_claim_bonus(last_daily):
    if not last_daily:
        return True
    try:
        dt = datetime.fromisoformat(last_daily)
        return datetime.now().date() > dt.date()
    except:
        return True

async def bonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_upsert_user(user)
    row = db_get_user(user.id)
    last_daily = row[6] if row else None
    if not can_claim_bonus(last_daily):
        text = "🎁 Ты уже забирал бонус сегодня! Возвращайся завтра — +50 поинтов ждут."
        if update.callback_query:
            await update.callback_query.answer("Уже получено сегодня 😉", show_alert=False)
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Играть", callback_data="menu")]]))
        else:
            await update.message.reply_text(text)
        return
    con = _db()
    cur = con.cursor()
    cur.execute("UPDATE users SET points=points+50, last_daily=? WHERE user_id=?", (datetime.now().isoformat(), user.id))
    con.commit()
    con.close()
    text = "🎁 <b>Бонус получен! +50 поинтов</b> 💰\nПриходи завтра за новым бонусом!"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("👤 Профиль", callback_data="profile"),
                                InlineKeyboardButton("🎮 Игры", callback_data="menu")]])
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

# --- МАГАЗИН И МОНЕТИЗАЦИЯ ---
async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_upsert_user(user)
    pts = db_get_points(user.id)
    # баланс звезд бота
    bot_stars = await get_bot_stars(context.bot)
    text = (
        f"🎁 <b>Магазин подарков</b> — меняй поинты на Stars и подарки!\n"
        f"💰 Твои поинты: <b>{pts}</b>\n"
        f"🤖 Баланс бота: {bot_stars} ⭐ (для отправки подарков)\n\n"
        f"Выбирай подарок — я отправлю его тебе прямо в Telegram!\n"
        f"<i>Подарки стоят Stars, но ты платишь поинтами. Я покрываю Stars из баланса (пополняется когда игроки покупают поинты).</i>\n"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=shop_kb())
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=shop_kb())

async def buy_points_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💎 <b>Купить поинты за Stars</b>\n"
        "Не хватает поинтов на подарок? Купи их за Telegram Stars!\n"
        "Stars спишутся с твоего баланса, а поинты придут мгновенно.\n\n"
        "Выбери пакет:"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=buy_points_kb())
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=buy_points_kb())

async def handle_shop_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, gift_id: str):
    user = update.effective_user
    gift = next((g for g in SHOP_GIFTS if g["gift_id"] == gift_id), None)
    if not gift:
        await update.callback_query.answer("Подарок не найден", show_alert=True)
        return
    pts = db_get_points(user.id)
    if pts < gift["points"]:
        await update.callback_query.answer(f"Не хватает поинтов! Нужно {gift['points']}, у тебя {pts}", show_alert=True)
        return
    # списываем поинты + создаем заказ атомарно в одной транзакции (фикс database is locked)
    oid = None
    for attempt in range(5):
        try:
            con = _db()
            cur = con.cursor()
            cur.execute("BEGIN IMMEDIATE")
            # повторная проверка баланса внутри транзакции
            cur.execute("SELECT points FROM users WHERE user_id=?", (user.id,))
            row = cur.fetchone()
            cur_pts = row[0] if row else 0
            if cur_pts < gift["points"]:
                con.rollback()
                con.close()
                await update.callback_query.answer(f"Не хватает поинтов! Нужно {gift['points']}, у тебя {cur_pts}", show_alert=True)
                return
            cur.execute("UPDATE users SET points=points-? WHERE user_id=?", (gift["points"], user.id))
            cur.execute("INSERT INTO shop_orders (user_id, gift_id, gift_name, stars, cost_points, status, created_at) VALUES (?,?,?,?,?,?,?)",
                        (user.id, gift["gift_id"], gift["name"], gift["stars"], gift["points"], "pending", datetime.now().isoformat()))
            oid = cur.lastrowid
            con.commit()
            con.close()
            break
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 4:
                import time; time.sleep(0.2*(attempt+1))
                continue
            raise
        finally:
            try: con.close()
            except: pass
    if oid is None:
        await update.callback_query.answer("Ошибка базы, попробуй еще раз", show_alert=True)
        return
    # пробуем отправить подарок
    try:
        bot_stars = await get_bot_stars(context.bot)
        if bot_stars < gift["stars"]:
            # не хватает звезд у бота - ставим в ожидание админа
            con = _db()
            cur = con.cursor()
            cur.execute("UPDATE shop_orders SET status='waiting_refill' WHERE id=?", (oid,))
            con.commit()
            con.close()
            await update.callback_query.edit_message_text(
                f"⏳ <b>Заказ принят!</b> {gift['emoji']} {gift['name']} ({gift['stars']} ⭐) за <b>{gift['points']} pts</b>\n\n"
                f"У бота пока не хватает Stars ({bot_stars}/{gift['stars']}) — админ пополнит баланс и твой подарок улетит! 🎁\n"
                f"Заказ #{oid} — статус: ожидание.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 В магазин", callback_data="shop"), InlineKeyboardButton("👤 Профиль", callback_data="profile")]])
            )
            # уведомляем админа
            for aid in ADMIN_IDS:
                try:
                    await context.bot.send_message(aid, f"⚠️ Новый заказ #{oid}: @{user.username or user.first_name} хочет {gift['emoji']} {gift['name']} за {gift['points']} pts. Баланс бота {bot_stars} ⭐, нужно {gift['stars']} ⭐. Пополни /admin")
                except: pass
            return
        # отправляем подарок
        await send_gift_raw(context.bot, chat_id=user.id, gift_id=gift["gift_id"])
        con = _db()
        cur = con.cursor()
        cur.execute("UPDATE shop_orders SET status='sent' WHERE id=?", (oid,))
        con.commit()
        con.close()
        await update.callback_query.edit_message_text(
            f"🎉 <b>Подарок отправлен!</b> {gift['emoji']} {gift['name']} ({gift['stars']} ⭐) уже у тебя в Telegram!\n"
            f"Списано <b>{gift['points']} поинтов</b>. Заказ #{oid}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Еще подарок", callback_data="shop"), InlineKeyboardButton("🏆 Топ", callback_data="top")]])
        )
    except Exception as e:
        log.exception(f"Gift send failed: {e}")
        # возвращаем поинты если ошибка
        con = _db()
        cur = con.cursor()
        cur.execute("UPDATE users SET points=points+? WHERE user_id=?", (gift["points"], user.id))
        cur.execute("UPDATE shop_orders SET status='failed' WHERE id=?", (oid,))
        con.commit()
        con.close()
        await update.callback_query.edit_message_text(
            f"❌ Не удалось отправить подарок: {e}\nПоинты возвращены. Попробуй позже или напиши админу.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Магазин", callback_data="shop")]])
        )

async def handle_buy_pack(update: Update, context: ContextTypes.DEFAULT_TYPE, stars: int):
    pack = next((p for p in POINTS_PACKAGES if p["stars"] == stars), None)
    if not pack:
        await update.callback_query.answer("Пакет не найден")
        return
    # создаем инвойс на Stars
    try:
        title = pack["title"]
        desc = f"Покупка {pack['points']} поинтов для Gamebot @Gamusonbot. Поинты можно обменять на подарки в /shop"
        payload = f"buy_{pack['stars']}_{pack['points']}_{update.effective_user.id}_{int(datetime.now().timestamp())}"
        prices = [LabeledPrice(label=title, amount=pack["stars"])]
        # сохраняем покупку в pending
        con = _db()
        cur = con.cursor()
        cur.execute("INSERT INTO star_purchases (user_id, stars, points, payload, status, created_at) VALUES (?,?,?,?,?,?)",
                    (update.effective_user.id, pack["stars"], pack["points"], payload, "pending", datetime.now().isoformat()))
        con.commit()
        con.close()
        # для Stars provider_token не нужен (пустая строка)
        invoice_link = await context.bot.create_invoice_link(
            title=title,
            description=desc,
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices
        )
        await update.callback_query.edit_message_text(
            f"💎 <b>{title}</b> за <b>{pack['stars']} ⭐</b>\n"
            f"Получишь <b>{pack['points']} поинтов</b> мгновенно после оплаты!\n\n"
            f"Нажми кнопку ниже чтобы оплатить:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"💳 Оплатить {pack['stars']} ⭐", url=invoice_link)], [InlineKeyboardButton("⬅️ Назад", callback_data="buy_points")]])
        )
    except Exception as e:
        log.exception(f"Invoice failed: {e}")
        await update.callback_query.answer(f"Ошибка создания счета: {e}", show_alert=True)

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.pre_checkout_query
    # всегда подтверждаем для Stars
    await q.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pay = update.message.successful_payment
    payload = pay.invoice_payload
    stars = pay.total_amount  # для XTR это кол-во звезд
    user = update.effective_user
    # парсим payload: buy_25_1000_userid_ts
    try:
        parts = payload.split("_")
        if parts[0] == "buy":
            points = int(parts[2])
            # для безопасности берем stars из платежа
            # начисляем поинты
            db_add_points(user.id, points, game_inc=0, win_inc=0)
            # обновляем покупку
            con = _db()
            cur = con.cursor()
            cur.execute("UPDATE star_purchases SET status='paid' WHERE payload=?", (payload,))
            con.commit()
            con.close()
            await update.message.reply_text(
                f"✅ <b>Оплата прошла!</b> Зачислено <b>{points} поинтов</b> за {stars} ⭐\n"
                f"Теперь можешь обменять их на подарки в /shop 🎁",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 В магазин", callback_data="shop"), InlineKeyboardButton("👤 Профиль", callback_data="profile")]])
            )
            # уведомляем админа о доходе
            for aid in ADMIN_IDS:
                try:
                    await context.bot.send_message(aid, f"💰 Продажа: @{user.username or user.first_name} купил {points} pts за {stars} ⭐ (payload {payload})")
                except: pass
            return
    except Exception as e:
        log.exception(f"Payment handling failed: {e}")
    # fallback
    await update.message.reply_text(f"✅ Платеж получен: {pay.total_amount} {pay.currency}. Спасибо!")

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Только для админа")
        return
    # статистика
    con = _db()
    cur = con.cursor()
    cur.execute("SELECT count(*), sum(points) FROM users")
    u_cnt, tot_pts = cur.fetchone()
    cur.execute("SELECT count(*) FROM shop_orders WHERE status='pending' OR status='waiting_refill'")
    pending = cur.fetchone()[0]
    cur.execute("SELECT count(*), sum(stars) FROM star_purchases WHERE status='paid'")
    sales_cnt, sales_stars = cur.fetchone()
    con.close()
    bot_stars = await get_bot_stars(context.bot)
    if bot_stars == 0:
        # попробуем еще раз, если 0 — может реально 0
        pass
    text = (
        f"👑 <b>Админка</b>\n"
        f"👥 Пользователей: {u_cnt}, всего поинтов: {tot_pts}\n"
        f"🎁 Ожидают подарков: {pending}\n"
        f"💎 Продано пакетов: {sales_cnt or 0}, доход Stars: {sales_stars or 0} ⭐\n"
        f"🤖 Баланс бота: {bot_stars} ⭐\n\n"
        f"Команды:\n"
        f"/admin - эта панель\n"
        f"/shop - магазин\n"
        f"Также для теста: <code>/give 12345 100</code> - выдать поинты\n"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Ожидающие заказы", callback_data="admin_pending")],
        [InlineKeyboardButton("📊 Топ", callback_data="top"), InlineKeyboardButton("🎁 Магазин", callback_data="shop")]
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def admin_give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Только для админа")
        return
    # формат: /give user_id points
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /give <user_id> <points>")
        return
    try:
        uid = int(args[0]); pts = int(args[1])
        db_add_points(uid, pts, game_inc=0, win_inc=0)
        await update.message.reply_text(f"✅ Выдал {pts} поинтов юзеру {uid}")
        try:
            await context.bot.send_message(uid, f"🎁 Админ начислил тебе <b>{pts} поинтов</b>!", parse_mode=ParseMode.HTML)
        except: pass
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

# --- КАНАЛ АВТОПОСТИНГ (GameFi Hunters @gamefi_hunters) ---
async def fetch_rss_titles(url, limit=3):
    """Простой парсер RSS без зависимостей"""
    try:
        import aiohttp, xml.etree.ElementTree as ET
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=10) as r:
                txt = await r.text()
        root = ET.fromstring(txt)
        items = []
        for item in root.findall(".//item")[:limit]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            if title:
                items.append((title, link))
        return items
    except Exception as e:
        log.warning(f"RSS fetch failed {url}: {e}")
        return []

async def post_to_channel(context: ContextTypes.DEFAULT_TYPE, text, reply_markup=None):
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup, disable_web_page_preview=True)
        log.info(f"Posted to {CHANNEL_USERNAME}")
    except Exception as e:
        log.error(f"Channel post failed: {e}")
        # fallback на username
        try:
            await context.bot.send_message(chat_id=CHANNEL_USERNAME, text=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception as e2:
            log.error(f"Channel fallback failed: {e2}")

async def autopost_gaming(context: ContextTypes.DEFAULT_TYPE):
    # 09:00 Frankfurt — гейминг новости
    titles = await fetch_rss_titles("https://dtf.ru/rss/all", limit=3)
    if not titles:
        titles = [("GTA 6 перенесли, но фанаты в ожидании", ""), ("Steam установил рекорд онлайна", ""), ("Новый трейлер Hollow Knight", "")]
    t = random.choice(titles)
    text = (
        f"🎮 <b>Новости гейминга</b>\n\n"
        f"🔥 <b>{t[0]}</b>\n"
        f"{t[1]}\n\n"
        f"Как тебе новость? Пиши в комменты 👇\n\n"
        f"🎯 Хочешь поинты? Играй в @Gamusonbot → /start и забирай подарки в /shop!"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Играть в боте", url="https://t.me/Gamusonbot?start=channel_gaming")]])
    await post_to_channel(context, text, kb)

async def autopost_crypto(context: ContextTypes.DEFAULT_TYPE):
    titles = await fetch_rss_titles("https://cointelegraph.com/rss", limit=3)
    if not titles:
        titles = [("BTC держит $68k — быки в деле", ""), ("ETH обновил максимум по TVL", ""), ("Новый дроп от LayerZero", "")]
    t = random.choice(titles)
    text = (
        f"💰 <b>Крипта сегодня</b>\n\n"
        f"📈 <b>{t[0]}</b>\n"
        f"{t[1]}\n\n"
        f"Что думаешь — лонг или шорт? 👇\n\n"
        f"💎 Зарабатывай Stars в @Gamusonbot → /shop меняй поинты на подарки!"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("💎 Купить поинты", url="https://t.me/Gamusonbot?start=channel_crypto")]])
    await post_to_channel(context, text, kb)

async def autopost_gamefi(context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"🚀 <b>GameFi находка дня</b>\n\n"
        f"🎯 <b>Новая P2E игра</b> — играй и зарабатывай прямо в Telegram!\n"
        f"• Без вложений, выплаты в Stars/крипте\n"
        f"• Уже 10k игроков в @Gamusonbot\n\n"
        f"👉 Заходи в бота, набивай поинты и меняй на подарки:\n"
        f"🎁 /shop — магазин за поинты • 💎 /buy — купить поинты за Stars"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Играть и заработать", url="https://t.me/Gamusonbot?start=gamefi")]])
    await post_to_channel(context, text, kb)

async def autopost_top(context: ContextTypes.DEFAULT_TYPE):
    rows = db_top(3)
    if not rows:
        txt = "🏆 <b>Топ пока пуст</b> — стань первым в @Gamusonbot! /start"
    else:
        txt = "🏆 <b>Топ-3 игроков дня в @Gamusonbot</b>\n\n"
        medals = ["🥇","🥈","🥉"]
        for i, (uname, fname, pts, wins, games) in enumerate(rows, 1):
            name = f"@{uname}" if uname else (fname or f"Игрок {i}")
            txt += f"{medals[i-1]} {name} — <b>{pts} pts</b>\n"
        txt += "\nХочешь в топ? Играй → @Gamusonbot /start и забирай +50 в /bonus каждый день!"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Ворваться в топ", url="https://t.me/Gamusonbot?start=top")]])
    await post_to_channel(context, txt, kb)

async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Только для админа")
        return
    # /post gaming|crypto|gamefi|top
    arg = context.args[0] if context.args else "gaming"
    m = {"gaming": autopost_gaming, "crypto": autopost_crypto, "gamefi": autopost_gamefi, "top": autopost_top}
    func = m.get(arg.lower(), autopost_gaming)
    await func(context)
    await update.message.reply_text(f"✅ Пост {arg} отправлен в {CHANNEL_USERNAME}")

# --- ИГРЫ: УГАДАЙ ЧИСЛО ---
async def start_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_num = random.randint(1, 100)
    context.user_data["guess_num"] = target_num
    context.user_data["guess_tries"] = 7
    context.user_data["guess_active"] = True
    text = (
        "🎲 <b>Угадай число от 1 до 100</b>\n"
        "У тебя <b>7 попыток</b>! Просто напиши число в чат.\n"
        "Подскажу «больше» или «меньше».\n\n"
        "Напиши число — например <code>42</code>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Заново", callback_data="game_guess"),
                                InlineKeyboardButton("⬅️ Меню", callback_data="menu")]])
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def handle_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("guess_active"):
        return
    txt = update.message.text.strip()
    if not re.fullmatch(r"-?\d+", txt):
        return
    try:
        guess = int(txt)
    except:
        return
    if not (1 <= guess <= 100):
        await update.message.reply_text("Число должно быть от 1 до 100 😉")
        return
    target = context.user_data["guess_num"]
    tries = context.user_data["guess_tries"] - 1
    context.user_data["guess_tries"] = tries

    if guess == target:
        context.user_data["guess_active"] = False
        # награда зависит от оставшихся попыток
        reward = 10 + tries*2
        db_add_points(update.effective_user.id, reward, game_inc=1, win_inc=1)
        await update.message.reply_text(
            f"🎉 <b>Верно! Это {target}</b>!\n"
            f"💰 +{reward} поинтов! Осталось попыток: {tries}\n"
            f"Сыграем ещё?",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Ещё раз", callback_data="game_guess"),
                 InlineKeyboardButton("🎮 Меню", callback_data="menu")]
            ])
        )
        return
    if tries <= 0:
        context.user_data["guess_active"] = False
        db_add_points(update.effective_user.id, 0, game_inc=1, win_inc=0)
        await update.message.reply_text(
            f"😢 Попытки кончились! Я загадал <b>{target}</b>\n"
            f"Попробуешь ещё?",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Ещё раз", callback_data="game_guess"),
                 InlineKeyboardButton("🎮 Меню", callback_data="menu")]
            ])
        )
        return
    hint = "Больше! ⬆️" if guess < target else "Меньше! ⬇️"
    await update.message.reply_text(f"{hint} Осталось попыток: <b>{tries}</b>", parse_mode=ParseMode.HTML)

# --- КНБ ---
async def start_rps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "✊ <b>Камень-Ножницы-Бумага</b>\nВыбирай — я уже готов!"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=rps_kb())
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=rps_kb())

async def handle_rps(update: Update, context: ContextTypes.DEFAULT_TYPE, choice: str):
    bot_choice = random.choice(["rock","paper","scissors"])
    em = {"rock":"✊ Камень","paper":"✋ Бумага","scissors":"✌️ Ножницы"}
    # rock > scissors > paper > rock
    win_map = {"rock":"scissors","scissors":"paper","paper":"rock"}
    user = update.effective_user
    if choice == bot_choice:
        res = "🤝 Ничья!"
        db_add_points(user.id, 1, game_inc=1, win_inc=0)
        pts = "+1 за участие"
    elif win_map[choice] == bot_choice:
        res = "🎉 Ты победил!"
        db_add_points(user.id, 5, game_inc=1, win_inc=1)
        pts = "+5 поинтов"
    else:
        res = "😢 Ты проиграл..."
        db_add_points(user.id, 0, game_inc=1, win_inc=0)
        pts = "0 поинтов"

    text = (
        f"Ты: <b>{em[choice]}</b>\n"
        f"Я: <b>{em[bot_choice]}</b>\n\n"
        f"{res} <i>{pts}</i>\n\n"
        f"Ещё раунд?"
    )
    await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=rps_kb())

# --- МОНЕТКА ---
async def start_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🪙 <b>Орёл и Решка</b>\nУгадай, что выпадет!"
    kb = coin_kb()
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def handle_coin(update: Update, context: ContextTypes.DEFAULT_TYPE, choice: str):
    result = random.choice(["heads","tails"])
    em = {"heads":"🦅 Орёл","tails":"🌙 Решка"}
    win = choice == result
    if win:
        db_add_points(update.effective_user.id, 5, game_inc=1, win_inc=1)
        res = f"🎉 Выпал <b>{em[result]}</b> — ты угадал! +5 поинтов"
    else:
        db_add_points(update.effective_user.id, 0, game_inc=1, win_inc=0)
        res = f"😢 Выпал <b>{em[result]}</b> — не угадал..."
    text = res + "\n\nСыграем ещё?"
    await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=coin_kb())

# --- ВИКТОРИНА ---
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = random.choice(QUIZ_QUESTIONS)
    context.user_data["quiz_current"] = q
    kb_rows = []
    for i, ans in enumerate(q["a"]):
        kb_rows.append([InlineKeyboardButton(ans, callback_data=f"quiz_{i}")])
    kb_rows.append([InlineKeyboardButton("⬅️ Меню", callback_data="menu")])
    text = f"🧠 <b>Викторина</b>\n\n{q['q']}"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb_rows))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb_rows))

async def handle_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, idx: int):
    q = context.user_data.get("quiz_current")
    if not q:
        await start_quiz(update, context)
        return
    correct = q["c"]
    user = update.effective_user
    if idx == correct:
        db_add_points(user.id, 7, game_inc=1, win_inc=1)
        res = f"✅ Верно! Правильный ответ: <b>{q['a'][correct]}</b>\n💰 +7 поинтов"
    else:
        db_add_points(user.id, 0, game_inc=1, win_inc=0)
        res = f"❌ Неверно. Правильный ответ: <b>{q['a'][correct]}</b>\nТы выбрал: {q['a'][idx]}"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➡️ Следующий вопрос", callback_data="game_quiz"),
         InlineKeyboardButton("🎮 Меню", callback_data="menu")]
    ])
    await update.callback_query.edit_message_text(
        f"🧠 {q['q']}\n\n{res}",
        parse_mode=ParseMode.HTML, reply_markup=kb
    )

# --- СЛОТЫ / DICE ---
async def start_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # используем Telegram Dice слотами
    chat_id = update.effective_chat.id
    # сначала сообщение
    if update.callback_query:
        await update.callback_query.answer()
        await context.bot.send_message(chat_id, "🎰 Кручу слоты... (ждём результат от Telegram)")
    else:
        await update.message.reply_text("🎰 Кручу слоты...")
    # dice
    msg = await context.bot.send_dice(chat_id, emoji="🎰")
    # value 1-64, выигрышные комбинации: 1,22,43,64 - джекпот и т.д.
    # подождём 3 сек пока анимация
    await asyncio.sleep(3.5)
    val = msg.dice.value
    # интерпретация
    # для слота: 64 = 777, 43= ???, но сделаем просто
    if val == 64:
        reward, res = 20, "💎 ДЖЕКПОТ 777! +20 поинтов!"
    elif val in [1,22,43]:
        reward, res = 10, "🎉 Выигрыш! +10 поинтов"
    elif val in [16,32,48]:
        reward, res = 5, "🍀 Маленький выигрыш +5"
    else:
        reward, res = 0, "😢 Повезёт в следующий раз..."
    db_add_points(update.effective_user.id, reward, game_inc=1, win_inc=1 if reward>0 else 0)
    await context.bot.send_message(
        chat_id,
        f"🎰 Результат: <b>{val}</b>\n{res}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Ещё раз", callback_data="game_slots"),
             InlineKeyboardButton("🎮 Меню", callback_data="menu")]
        ])
    )

async def handle_dice_picker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🎲 <b>Выбери кубик для броска</b>\nTelegram сам генерирует рандом — честно и красиво!"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=dice_kb())
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=dice_kb())

async def handle_dice_throw(update: Update, context: ContextTypes.DEFAULT_TYPE, emoji: str):
    chat_id = update.effective_chat.id
    try:
        await update.callback_query.answer()
    except: pass
    msg = await context.bot.send_dice(chat_id, emoji=emoji)
    await asyncio.sleep(3.2)
    val = msg.dice.value
    # для 🎲 кубик 1-6, 🎯 1-6 (1 промах, 6 в яблочко), 🏀 1-5 и т.д.
    # наградим за максимум
    max_map = {"🎲":6,"🎯":6,"🏀":5,"⚽":5,"🎳":6,"🎰":64}
    mx = max_map.get(emoji, 6)
    if val == mx:
        reward = 10
        res = f"🔥 Идеально! Выпало <b>{val}</b> — максимум! +10 поинтов"
        win = 1
    elif val >= mx-1:
        reward = 3
        res = f"👍 Почти максимум! Выпало <b>{val}</b> — +3 поинта"
        win = 1
    else:
        reward = 0
        res = f"Выпало <b>{val}</b>. Попробуй ещё!"
        win = 0
    db_add_points(update.effective_user.id, reward, game_inc=1, win_inc=win)
    await context.bot.send_message(
        chat_id, res, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 Ещё бросок", callback_data=f"dice_{emoji}"),
             InlineKeyboardButton("🎮 Меню", callback_data="menu")]
        ])
    )

# --- CALLBACK ROUTER ---
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data

    if data == "menu":
        await q.edit_message_text("🎮 <b>Меню игр</b>\nВыбирай игру ниже:", parse_mode=ParseMode.HTML, reply_markup=games_inline_kb())
    elif data == "profile":
        await profile_cmd(update, context)
    elif data == "top":
        await top_cmd(update, context)
    elif data == "bonus":
        await bonus_cmd(update, context)
    elif data == "shop":
        await shop_cmd(update, context)
    elif data == "buy_points":
        await buy_points_cmd(update, context)
    elif data.startswith("shop_buy_"):
        gift_id = data.replace("shop_buy_", "")
        await handle_shop_buy(update, context, gift_id)
    elif data.startswith("buy_pack_"):
        stars = int(data.replace("buy_pack_", ""))
        await handle_buy_pack(update, context, stars)
    elif data == "admin_pending":
        if not is_admin(update.effective_user.id):
            await q.answer("⛔ Только для админа", show_alert=True)
            return
        rows = db_get_orders(status="waiting_refill", limit=10)
        if not rows:
            rows = db_get_orders(status="pending", limit=10)
        if not rows:
            await q.edit_message_text("📦 Нет ожидающих заказов", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Админка", callback_data="admin_back")]]))
        else:
            txt = "📦 <b>Ожидающие заказы:</b>\n"
            for oid, uid, gname, stars, pts, st, created in rows:
                txt += f"#{oid} uid:{uid} {gname} {stars}⭐ за {pts}pts — {st}\n"
            await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Админка", callback_data="admin_back")]]))
    elif data == "admin_back":
        # вернуть админку через сообщение
        await q.answer()
        # отправим новую админку как сообщение
        try:
            await admin_cmd(update, context)
        except:
            await q.edit_message_text("👑 Админка", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📦 Заказы", callback_data="admin_pending")]]))
    elif data == "game_guess":
        await start_guess(update, context)
    elif data == "game_rps":
        await start_rps(update, context)
    elif data.startswith("rps_"):
        choice = data.split("_")[1]  # rock paper scissors
        await handle_rps(update, context, choice)
    elif data == "game_coin":
        await start_coin(update, context)
    elif data.startswith("coin_"):
        choice = data.split("_")[1]  # heads tails
        await handle_coin(update, context, choice)
    elif data == "game_quiz":
        await start_quiz(update, context)
    elif data.startswith("quiz_"):
        idx = int(data.split("_")[1])
        await handle_quiz(update, context, idx)
    elif data == "game_slots":
        await start_slots(update, context)
    elif data == "game_dice":
        await handle_dice_picker(update, context)
    elif data.startswith("dice_"):
        emoji = data.split("_")[1]
        await handle_dice_throw(update, context, emoji)
    else:
        await q.answer("Неизвестная команда")

# --- TEXT HANDLER (кнопки + числа) ---
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    # если активна игра угадай число — пробуем обработать как число сначала
    if context.user_data.get("guess_active") and re.fullmatch(r"-?\d+", txt):
        await handle_number(update, context)
        return

    if txt == "🎮 Игры":
        await update.message.reply_text("🎮 Выбери игру:", reply_markup=games_inline_kb())
    elif txt == "👤 Профиль":
        await profile_cmd(update, context)
    elif txt == "🏆 Топ":
        await top_cmd(update, context)
    elif txt == "🎁 Бонус":
        await bonus_cmd(update, context)
    elif txt == "🎁 Магазин":
        await shop_cmd(update, context)
    elif txt == "ℹ️ Помощь":
        await help_cmd(update, context)
    elif re.fullmatch(r"-?\d+", txt) and not context.user_data.get("guess_active"):
        await update.message.reply_text("Чтобы угадывать числа — сначала нажми 🎲 «Угадай число» в меню /menu")
    else:
        # фолбэк
        await update.message.reply_text("Не понял 🤔 Используй меню ниже или /menu для списка игр.", reply_markup=main_menu_kb())

# --- ERROR ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Update %s caused error %s", update, context.error)

# --- HEALTH SERVER для бесплатных хостингов ---
async def health_server():
    """Мини HTTP сервер для Render/Fly health-check. Не мешает polling-боту."""
    try:
        from aiohttp import web
        async def handle(request):
            return web.Response(text="OK - Gamebot @Gamusonbot is running 🎮")
        async def health(request):
            return web.Response(text="ok")
        app = web.Application()
        app.router.add_get("/", handle)
        app.router.add_get("/health", health)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", HEALTH_PORT)
        await site.start()
        log.info(f"Health server запущен на порту {HEALTH_PORT} для Render/Fly")
        # держим живым
        while True:
            await asyncio.sleep(3600)
    except ImportError:
        log.info("aiohttp не установлен — health server пропущен (не нужен для локального запуска)")
        while True:
            await asyncio.sleep(3600)
    except OSError as e:
        log.warning(f"Health server не смог стартовать на порту {HEALTH_PORT}: {e}")
        while True:
            await asyncio.sleep(3600)

# --- MAIN ---
def main():
    db_init()
    if not TOKEN or ":" not in TOKEN:
        log.error("BOT_TOKEN не найден! Проверь .env")
        return

    # запускаем health server в фоне если указан PORT (Render/Fly)
    if os.getenv("PORT") or os.getenv("HEALTH_PORT"):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        # запустим после создания Application через job_queue? Проще в отдельном потоке
        import threading
        def run_health():
            try:
                asyncio.run(health_server())
            except Exception as e:
                log.warning(f"Health server error: {e}")
        threading.Thread(target=run_health, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("games", menu_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("bonus", bonus_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("buy", buy_points_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("give", admin_give_cmd))
    app.add_handler(CommandHandler("post", cmd_post))

    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))

    # --- Автопостинг в канал ---
    try:
        import datetime as dt
        jq = app.job_queue
        # 07:00 UTC = 09:00 Frankfurt, 11:00 UTC=13:00, 15:00=17:00, 18:00=20:00
        jq.run_daily(autopost_gaming, time=dt.time(7,0), name="gaming")
        jq.run_daily(autopost_crypto, time=dt.time(11,0), name="crypto")
        jq.run_daily(autopost_gamefi, time=dt.time(15,0), name="gamefi")
        jq.run_daily(autopost_top, time=dt.time(18,0), name="top")
        log.info("Автопостинг в канал @gamefi_hunters запланирован 4 поста/день")
    except Exception as e:
        log.warning(f"JobQueue не запущен (нужен APScheduler): {e} — автопостинг через /post вручную")

    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    app.add_error_handler(error_handler)

    log.info(f"Бот @Gamusonbot запущен. Polling...")
    log.info("Нажми Ctrl+C для остановки. Токен из .env")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
