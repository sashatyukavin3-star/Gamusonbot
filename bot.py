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
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

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
    con = sqlite3.connect(DB_PATH)
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
    con.commit()
    con.close()

def db_upsert_user(user):
    con = sqlite3.connect(DB_PATH)
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
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("UPDATE users SET points=points+?, games_played=games_played+?, wins=wins+? WHERE user_id=?",
                (delta, game_inc, win_inc, user_id))
    con.commit()
    con.close()

def db_get_user(user_id):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT user_id, username, first_name, points, games_played, wins, last_daily FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row

def db_top(limit=10):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT username, first_name, points, wins, games_played FROM users ORDER BY points DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    con.close()
    return rows

# --- КЛАВИАТУРЫ ---
def main_menu_kb():
    kb = [
        [KeyboardButton("🎮 Игры"), KeyboardButton("👤 Профиль")],
        [KeyboardButton("🏆 Топ"), KeyboardButton("🎁 Бонус")],
        [KeyboardButton("ℹ️ Помощь")]
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
        [InlineKeyboardButton("🏆 Рейтинг", callback_data="top"),
         InlineKeyboardButton("👤 Профиль", callback_data="profile")]
    ]
    return InlineKeyboardMarkup(kb)

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
        f"🎁 Не забудь забрать <b>ежедневный бонус</b>!\n\n"
        f"Жми кнопку ниже, чтобы начать:"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
                                    reply_markup=main_menu_kb())
    await update.message.reply_text("🎮 Выбери игру:", reply_markup=games_inline_kb())

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎮 Главное меню — выбирай игру:", reply_markup=games_inline_kb())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>ℹ️ Помощь по Gamebot</b>\n\n"
        "<b>Команды:</b>\n"
        "/start — приветствие и меню\n"
        "/menu — список игр\n"
        "/games — то же, что меню\n"
        "/profile — твой профиль и поинты\n"
        "/top — топ-10 игроков\n"
        "/bonus — ежедневный бонус +50\n"
        "/help — эта справка\n\n"
        "<b>Как играть:</b>\n"
        "• Просто жми кнопки. В «Угадай число» пиши число в чат.\n"
        "• В викторине выбирай вариант ответа.\n"
        "• Поинты начисляются автоматически и сохраняются.\n\n"
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
    con = sqlite3.connect(DB_PATH)
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

    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    app.add_error_handler(error_handler)

    log.info(f"Бот @Gamusonbot запущен. Polling...")
    log.info("Нажми Ctrl+C для остановки. Токен из .env")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
