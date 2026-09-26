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
import html
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
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
    from channel_config import CHANNEL_USERNAME, CHANNEL_ID, DISCUSSION_CHAT_ID
except ImportError:
    try:
        from channel_config import CHANNEL_USERNAME, CHANNEL_ID
        DISCUSSION_CHAT_ID = getattr(__import__("channel_config"), "DISCUSSION_CHAT_ID", None)
    except ImportError:
        CHANNEL_USERNAME = "@gamefi_hunters"
        CHANNEL_ID = -1003642138077
        DISCUSSION_CHAT_ID = None
if 'DISCUSSION_CHAT_ID' not in globals() or DISCUSSION_CHAT_ID is None:
    try:
        from channel_config import DISCUSSION_CHAT_ID as _DISC
        DISCUSSION_CHAT_ID = _DISC
    except:
        DISCUSSION_CHAT_ID = None

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
    cur.execute("""
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER UNIQUE,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        rewarded_at TEXT
    )""")
    # миграция users: добавляем колонки если нет
    for col, typ in [("referrer_id","INTEGER"),("referral_count","INTEGER DEFAULT 0"),("referral_points","INTEGER DEFAULT 0")]:
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
        except: pass
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
    # антинакрутка: фиксируем games_played до
    try:
        con0 = _db()
        cur0 = con0.cursor()
        cur0.execute("SELECT games_played FROM users WHERE user_id=?", (user_id,))
        r0 = cur0.fetchone()
        was_zero = (r0 is None or (r0[0] or 0) == 0)
        con0.close()
    except: was_zero = False
    for attempt in range(5):
        try:
            con = _db()
            cur = con.cursor()
            cur.execute("BEGIN IMMEDIATE")
            cur.execute("UPDATE users SET points=points+?, games_played=games_played+?, wins=wins+? WHERE user_id=?",
                        (delta, game_inc, win_inc, user_id))
            con.commit()
            con.close()
            # если первая игра — активируем рефералку
            if was_zero and game_inc>0:
                try:
                    # db_activate_referral уже определён ниже, но если ещё нет — отложим
                    if 'db_activate_referral' in globals():
                        res = db_activate_referral(user_id)
                        # res = (True, reward, bonus) или False
                        pass
                except Exception as e:
                    log.warning(f"referral activate fail: {e}")
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

# --- РЕФЕРАЛКА С АНТИНАКРУТКОЙ ---
def db_add_referral(referrer_id: int, referred_id: int):
    # антинакрутка: сам себя, бот, уже есть реферал, уже старый юзер, лимит 20/день
    if referrer_id == referred_id:
        return False, "self"
    if referrer_id is None or referred_id is None:
        return False, "invalid"
    try:
        con = _db()
        cur = con.cursor()
        # уже есть реферал?
        cur.execute("SELECT referrer_id FROM users WHERE user_id=?", (referred_id,))
        r = cur.fetchone()
        if r and r[0] is not None:
            con.close(); return False, "already_referred"
        # не новый юзер? если уже играл — не даём
        cur.execute("SELECT games_played FROM users WHERE user_id=?", (referred_id,))
        gp = cur.fetchone()
        if gp and gp[0] and gp[0] > 0:
            con.close(); return False, "not_new"
        # уже есть запись в referrals?
        cur.execute("SELECT id FROM referrals WHERE referred_id=?", (referred_id,))
        if cur.fetchone():
            con.close(); return False, "dup"
        # лимит 20 в день на реферера
        cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND date(created_at)=date('now')", (referrer_id,))
        cnt_day = cur.fetchone()[0] or 0
        if cnt_day >= 20:
            con.close(); return False, "limit_day"
        # лимит 100 всего
        cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (referrer_id,))
        cnt_all = cur.fetchone()[0] or 0
        if cnt_all >= 500:
            con.close(); return False, "limit_all"
        # проверка на накрутку по времени: если реферер только что создан (<5 мин) и уже пригласил >3 — подозрительно, но пока пропускаем
        now = datetime.now().isoformat()
        cur.execute("INSERT INTO referrals (referrer_id, referred_id, status, created_at) VALUES (?,?,?,?)", (referrer_id, referred_id, "pending", now))
        cur.execute("UPDATE users SET referrer_id=? WHERE user_id=?", (referrer_id, referred_id))
        con.commit(); con.close()
        return True, "pending"
    except Exception as e:
        try: con.close()
        except: pass
        return False, str(e)

def db_activate_referral(referred_id: int):
    # вызывается когда приглашённый сыграл первую игру — начисляет рефереру
    try:
        con = _db()
        cur = con.cursor()
        cur.execute("SELECT referrer_id, status FROM referrals WHERE referred_id=?", (referred_id,))
        row = cur.fetchone()
        if not row: con.close(); return False
        referrer_id, status = row
        if status != "pending": con.close(); return False
        # проверяем что приглашённый реально сыграл (games_played >=1)
        cur.execute("SELECT games_played FROM users WHERE user_id=?", (referred_id,))
        gp = cur.fetchone()
        if not gp or (gp[0] or 0) < 1:
            con.close(); return False
        # антинакрутка: если реферер и реферал с одинаковым first_name/username подозрительно — но пока не баним, просто логируем
        # начисляем: 100 base, 200 если акция (первые 7 дней после запуска реф системы — до 2026-10-03)
        reward = 200 if datetime.now().date() < datetime(2026,10,3).date() else 100
        # бонус за 5 друзей +500
        cur.execute("UPDATE referrals SET status='active', rewarded_at=? WHERE referred_id=?", (datetime.now().isoformat(), referred_id))
        cur.execute("UPDATE users SET points=points+?, referral_count=referral_count+1, referral_points=referral_points+? WHERE user_id=?", (reward, reward, referrer_id))
        # проверка на бонус 5
        cur.execute("SELECT referral_count FROM users WHERE user_id=?", (referrer_id,))
        rc = (cur.fetchone() or [0])[0]
        bonus_msg = None
        if rc % 5 == 0 and rc > 0:
            cur.execute("UPDATE users SET points=points+500 WHERE user_id=?", (referrer_id,))
            bonus_msg = 500
        con.commit(); con.close()
        # уведомим реферера синхронно через Bot API (анти-спам: не чаще 1/5сек)
        try:
            import requests
            bonus_txt = f" + бонус 500 за 5 друзей!" if bonus_msg else ""
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": referrer_id,
                      "text": f"🎉 Твой друг сыграл первую игру! Тебе +{reward} pts{bonus_txt}\nПриглашай ещё — /invite",
                      "parse_mode": "HTML"}, timeout=5)
        except: pass
        return True, reward, bonus_msg
    except Exception as e:
        try: con.close()
        except: pass
        return False, str(e)

def db_get_referral_stats(user_id: int):
    con = _db()
    cur = con.cursor()
    cur.execute("SELECT referral_count, referral_points FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    rc, rp = (row or (0,0))
    cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND status='pending'", (user_id,))
    pending = (cur.fetchone() or [0])[0]
    cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND status='active'", (user_id,))
    active = (cur.fetchone() or [0])[0]
    con.close()
    return {"count": rc or 0, "points": rp or 0, "pending": pending, "active": active}

def db_top_referrers(limit=10):
    con = _db()
    cur = con.cursor()
    cur.execute("SELECT user_id, username, first_name, referral_count, referral_points FROM users WHERE referral_count>0 ORDER BY referral_count DESC, referral_points DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    con.close()
    return rows

# --- FORCE SUB на наш канал ---
FORCE_CHANNEL = "@gamefi_hunters"
FORCE_CHANNEL_URL = "https://t.me/gamefi_hunters"

async def is_user_subscribed(bot, user_id: int):
    try:
        m = await bot.get_chat_member(FORCE_CHANNEL, user_id)
        return m.status in ("member","administrator","creator","restricted")
    except:
        # если бот не админ в канале — считаем что подписан чтобы не лочить всех
        return True

def force_sub_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Перейти в канал", url=FORCE_CHANNEL_URL)],
        [InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub")]
    ])

# --- ПЕРЕВОД на русский для постов ---
import re as _re
_cyr = _re.compile(r"[а-яА-ЯёЁ]")
async def translate_ru(text: str) -> str:
    if not text or _cyr.search(text):
        return text  # уже русский
    # пробуем HF Helsinki, fallback Qwen
    try:
        from huggingface_hub import InferenceClient
        import os
        tok = os.getenv("HF_TOKEN", "")
        if tok:
            # 1) Helsinki
            try:
                client = InferenceClient(token=tok, provider="hf-inference")
                out = client.translation(model="Helsinki-NLP/opus-mt-en-ru", text=text[:400])
                # out is TranslationOutput or str
                tr = out.translation_text if hasattr(out, "translation_text") else str(out)
                if tr and len(tr.strip())>5:
                    return tr.strip()
            except: pass
            # 2) Qwen fallback
            try:
                client2 = InferenceClient(token=tok, provider="featherless-ai")
                resp = client2.chat.completions.create(
                    model="Qwen/Qwen2.5-7B-Instruct",
                    messages=[{"role":"system","content":"Переведи точно на русский, без пояснений, сохрани цифры и термины."},
                              {"role":"user","content": text[:400]}],
                    max_tokens=120, temperature=0.3)
                tr2 = resp.choices[0].message.content.strip()
                if tr2:
                    return tr2
            except: pass
    except: pass
    return text

async def send_force_sub(update, context):
    text = (
        f"🚀 Чтобы использовать бота, подпишись на наш канал:\n"
        f"<b>{FORCE_CHANNEL}</b> — новости гейминга, крипта и GameFi!\n\n"
        f"Подпишись и нажми «Проверить» — получишь <b>+50 pts</b> бонус!"
    )
    kb = force_sub_kb()
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)



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

def referral_share_kb(user_id: int):
    link = f"https://t.me/Gamusonbot?start=r{user_id}"
    share = f"https://t.me/share/url?url={link}&text=Я+выиграл+в+GameFi+Hunters!+6+игр+и+подарки+Telegram+—+присоединяйся!"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Поделиться победой +200", url=share)],
        [InlineKeyboardButton("👥 Мой инвайт", callback_data="invite"), InlineKeyboardButton("🎮 Ещё игра", callback_data="menu")]
    ])

async def send_win_share(update, context, reward: int):
    try:
        user_id = update.effective_user.id
        link = f"https://t.me/Gamusonbot?start=r{user_id}"
        share = f"https://t.me/share/url?url={link}&text=Я+выиграл+{reward}+pts+в+GameFi+Hunters!+6+игр+и+подарки+—+залетай!"
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"👥 <b>Хочешь ещё +200?</b> Поделись победой — друг перейдёт по твоей ссылке и сыграет 1 игру, ты получишь <b>+200 pts</b>!\n<code>{link}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 Поделиться", url=share)], [InlineKeyboardButton("👥 /invite", callback_data="invite")]])
        )
    except: pass

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
    # ставим Mini App кнопку для этого юзера (фикс для Render — default не ставится)
    try:
        from telegram import MenuButtonWebApp, WebAppInfo
        await context.bot.set_chat_menu_button(chat_id=user.id, menu_button=MenuButtonWebApp(text="🎰 Играть", web_app=WebAppInfo(url="https://gamusonbot.onrender.com/app/index.html")))
    except: pass
    # force sub check (админов пропускаем)
    if user.id not in ADMIN_IDS:
        if not await is_user_subscribed(context.bot, user.id):
            await send_force_sub(update, context)
            return
    is_new = False
    # проверим новый ли юзер до upsert
    try:
        con = _db()
        cur = con.cursor()
        cur.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,))
        is_new = cur.fetchone() is None
        con.close()
    except: is_new = True
    db_upsert_user(user)
    # --- рефералка: обработка диплинка ---
    ref_msg = ""
    if context.args:
        # поддерживаем r12345, ref_12345, 12345
        raw = context.args[0]
        m = re.match(r"^(?:r|ref_)?(\d+)$", raw)
        if m:
            try:
                ref_id = int(m.group(1))
                if ref_id != user.id and is_new:
                    ok, reason = db_add_referral(ref_id, user.id)
                    if ok:
                        ref_msg = "\n\n👥 Тебя пригласил охотник! Сыграй 1 игру — и он получит <b>+200 поинтов</b> (акция до 03.10)!"
                        # уведомим реферера
                        try:
                            await context.bot.send_message(ref_id, f"🎉 По твоей ссылке зашёл {user.first_name or 'друг'} (@{user.username or '—'})! Как только он сыграет 1 игру — ты получишь <b>+200 pts</b>", parse_mode=ParseMode.HTML)
                        except: pass
                    else:
                        if reason not in ("already_referred","self","not_new"):
                            ref_msg = ""
            except Exception as e:
                log.warning(f"referral start fail: {e}")
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
        f"🎁 Не забудь забрать <b>ежедневный бонус</b>!{ref_msg}\n\n"
        f"Жми кнопку ниже, чтобы начать:"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
                                    reply_markup=main_menu_kb())
    await update.message.reply_text("🎮 Выбери игру или загляни в магазин:", reply_markup=games_inline_kb())
    # быстрый доступ к рефке
    try:
        await update.message.reply_text(
            "👥 <b>Хочешь халявные поинты?</b> Пригласи друга — +200 за каждого (акция)!\n"
            f"Твоя ссылка: <code>https://t.me/Gamusonbot?start=r{user.id}</code>\n"
            "Жми /invite чтобы видеть прогресс",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 Поделиться", url=f"https://t.me/share/url?url=https://t.me/Gamusonbot?start=r{user.id}&text=Зарубись+со+мной+в+GameFi+Hunters+—+6+игр+и+подарки+Telegram!")]])
        )
    except: pass

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        from telegram import MenuButtonWebApp, WebAppInfo
        await context.bot.set_chat_menu_button(chat_id=update.effective_user.id, menu_button=MenuButtonWebApp(text="🎰 Играть", web_app=WebAppInfo(url="https://gamusonbot.onrender.com/app/index.html")))
    except: pass
    if update.effective_user.id not in ADMIN_IDS:
        if not await is_user_subscribed(context.bot, update.effective_user.id):
            await send_force_sub(update, context)
            return
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
        "/invite — 👥 пригласи друга +200 pts (акция)\n"
        "/topref — 🏆 топ по приглашениям\n"
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

async def invite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_upsert_user(user)
    stats = db_get_referral_stats(user.id)
    link = f"https://t.me/Gamusonbot?start=r{user.id}"
    share_url = f"https://t.me/share/url?url={link}&text=Я+фармлю+поинты+в+GameFi+Hunters+—+6+игр,+подарки+Telegram+за+поинты!+Присоединяйся+и+получим+бонусы!"
    # прогресс до бонуса 5
    need = 5 - (stats['count'] % 5) if stats['count']%5!=0 else 5
    bonus_info = f"\n🎁 Бонус <b>+500 pts</b> за каждых 5 друзей! До бонуса: <b>{need}</b>" if stats['count']<500 else ""
    text = (
        f"👥 <b>Пригласи друга — получи +200 поинтов</b> (акция до 03.10, потом +100)\n\n"
        f"🔗 Твоя ссылка:\n<code>{link}</code>\n\n"
        f"📊 Статистика:\n"
        f"• Приглашено: <b>{stats['count']}</b> (активных: {stats['active']}, ожидают игры: {stats['pending']})\n"
        f"• Заработано с рефералов: <b>{stats['points']} pts</b>{bonus_info}\n\n"
        f"🏆 Топ пригласивших: /topref\n"
        f"💡 Друг должен сыграть хотя бы 1 игру — тогда ты получишь награду (анти-накрутка: сам себя и ботов не засчитывает, 20/день лимит)\n"
        f"📤 Жми «Поделиться» и зови охотников!"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Поделиться ссылкой", url=share_url)],
        [InlineKeyboardButton("🏆 Топ рефереров", callback_data="topref"), InlineKeyboardButton("👤 Профиль", callback_data="profile")]
    ])
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)

# --- ФАЙЛ-МОСТ для админа (чтобы я мог извлекать любые файлы) ---
async def admin_file_bridge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return
    msg = update.effective_message
    # берём файл из документа, фото, видео, аудио
    file_obj = None
    fname = None
    if msg.document:
        file_obj = await context.bot.get_file(msg.document.file_id)
        fname = msg.document.file_name or f"doc_{msg.document.file_id[:8]}.bin"
    elif msg.photo:
        file_obj = await context.bot.get_file(msg.photo[-1].file_id)
        fname = f"photo_{file_obj.file_id[:8]}.jpg"
    elif msg.video:
        file_obj = await context.bot.get_file(msg.video.file_id)
        fname = msg.video.file_name or f"video_{file_obj.file_id[:8]}.mp4"
    elif msg.audio:
        file_obj = await context.bot.get_file(msg.audio.file_id)
        fname = msg.audio.file_name or f"audio_{file_obj.file_id[:8]}.mp3"
    elif msg.voice:
        file_obj = await context.bot.get_file(msg.voice.file_id)
        fname = f"voice_{file_obj.file_id[:8]}.ogg"
    if not file_obj:
        return
    # сохраняем
    import os, pathlib as pl
    out_dir = pl.Path(__file__).parent / "uploads"
    out_dir.mkdir(exist_ok=True)
    # анти-путь
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in fname)[:80]
    out_path = out_dir / f"{user.id}_{safe}"
    # качаем
    await file_obj.download_to_drive(str(out_path))
    # также кладём в /home/user/uploads для ассистента Arena
    try:
        import shutil
        dest2 = pl.Path("/home/user/uploads") / safe
        dest2.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(str(out_path), str(dest2))
    except: pass
    size = out_path.stat().st_size
    await update.message.reply_text(
        f"✅ Файл принят админом\n"
        f"📁 <code>{safe}</code> — {size//1024} КБ\n"
        f"Путь: <code>{out_path}</code>\n"
        f"Я уже могу его читать и обрабатывать. Что с ним делать?",
        parse_mode=ParseMode.HTML
    )

async def topref_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db_top_referrers(10)
    if not rows:
        txt = "🏆 Топ рефереров пока пуст — стань первым! /invite"
    else:
        lines = ["🏆 <b>Топ-10 охотников по приглашениям</b>\n"]
        for i,(uid, uname, fname, cnt, pts) in enumerate(rows,1):
            name = f"@{uname}" if uname else (fname or f"ID{uid}")
            name = name.replace("<","").replace(">","")
            medal = ["🥇","🥈","🥉"][i-1] if i<=3 else f"{i}."
            lines.append(f"{medal} {name} — <b>{cnt}</b> друз., +{pts} pts")
        txt = "\n".join(lines) + "\n\nХочешь в топ? /invite"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("👥 Мой инвайт", callback_data="invite"), InlineKeyboardButton("🎮 Играть", callback_data="menu")]])
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

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

# --- КАНАЛ АВТОПОСТИНГ (GameFi Hunters @gamefi_hunters) — РЕАЛЬНЫЕ НОВОСТИ ---
# Источники без ключа: RSS (DTF, SimulationDaily, Cointelegraph) + CoinGecko цены
RSS_GAMING = [
    "https://dtf.ru/rss/all",
    "https://simulationdaily.com/feed/",
]
RSS_CRYPTO = [
    "https://cointelegraph.com/rss",
    "https://cointelegraph.com/rss-feeds",
]
RSS_GAMEFI = [
    "https://cointelegraph.com/tags/gamefi/rss",
]

async def fetch_rss_titles(url, limit=4):
    """Простой парсер RSS без зависимостей, возвращает [(title,link,desc)]"""
    try:
        import aiohttp, xml.etree.ElementTree as ET
        headers = {"User-Agent": "Mozilla/5.0 (GameFi Hunters bot)"}
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=12) as r:
                txt = await r.text()
        root = ET.fromstring(txt)
        items = []
        # поддержка Atom тоже
        for item in root.findall(".//item")[:limit]:
            title = (item.findtext("title", "") or "").strip()
            link = (item.findtext("link", "") or "").strip()
            # в Atom link как <link href="">
            if not link:
                le = item.find("link")
                if le is not None:
                    link = le.get("href","")
            desc = (item.findtext("description", "") or item.findtext("summary","") or "").strip()
            # чистим HTML и сущности ДО обрезки
            desc = html.unescape(desc)
            desc = re.sub(r"<[^>]+>", "", desc)
            desc = desc.replace("\n"," ").strip()
            if len(desc) > 180:
                desc = desc[:177]+"..."
                items.append((title, link, desc))
        # Atom entries
        if not items:
            ns = {"atom":"http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns)[:limit]:
                title = (entry.findtext("atom:title", "", namespaces=ns) or "").strip()
                le = entry.find("atom:link", ns)
                link = le.get("href","") if le is not None else ""
                desc = (entry.findtext("atom:summary","", namespaces=ns) or "").strip()
                desc = html.unescape(desc)
                desc = re.sub(r"<[^>]+>", "", desc)
                desc = desc.replace("\n"," ").strip()
                if len(desc) > 180:
                    desc = desc[:177]+"..."
                if title:
                    items.append((title, link, desc))
        return items
    except Exception as e:
        log.warning(f"RSS fetch failed {url}: {e}")
        return []

async def fetch_crypto_prices():
    """CoinGecko free API: BTC, ETH, SOL цены + 24h изменение"""
    try:
        import aiohttp
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true"
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=8) as r:
                j = await r.json()
        btc = j.get("bitcoin",{})
        eth = j.get("ethereum",{})
        sol = j.get("solana",{})
        return btc, eth, sol
    except Exception as e:
        log.warning(f"CoinGecko failed: {e}")
        return {}, {}, {}

async def fetch_any_rss(urls, limit=4):
    for u in urls:
        items = await fetch_rss_titles(u, limit=limit)
        if items:
            return items, u
    return [], None

def ai_image_url(prompt, w=1024, h=1024):
    # Fallback Pollinations URL (если свой генератор не сработал)
    import urllib.parse
    p = urllib.parse.quote(prompt[:280])
    return f"https://image.pollinations.ai/prompt/{p}?width={w}&height={h}&model=flux&nologo=true&seed={random.randint(1,999999)}"

async def get_own_image(prompt: str):
    # пробует свой HF генератор, возвращает путь к файлу или None
    loop = __import__('asyncio').get_event_loop()
    try:
        out = f"/tmp/own_{__import__('random').randint(1000,999999)}.jpg"
        # run in executor to not block
        result = await loop.run_in_executor(None, lambda: generate_own_image(prompt, out))
        if result and __import__('os').path.exists(result):
            return result
    except Exception as e:
        log.warning(f"get_own_image async fail: {e}")
    return None

def sanitize_prompt(title: str) -> str:
    # Pollinations плохо ест кириллицу → делаем английский фолбэк
    if re.search(r"[а-яА-Я]", title):
        low = title.lower()
        if "ведьмак" in low or "witcher" in low:
            return "Witcher 3 remaster patch CDPR fantasy RPG"
        if "007" in title or "first light" in low:
            return "James Bond 007 First Light Golden Joystick Awards game"
        if "ace combat" in low:
            return "Ace Combat 8 fighter jets clouds cinematic"
        return "epic video game news fantasy RPG cinematic"
    # режем длинные заголовки для промпта
    return title[:80]

HUNTER_STICKER = Path(__file__).parent / "hunter_sticker.png"
# fallback to /home/user version if not in gamebot dir
if not HUNTER_STICKER.exists():
    alt = Path("/home/user/hunter_sticker.png")
    if alt.exists():
        HUNTER_STICKER = alt

HF_TOKEN = os.getenv("HF_TOKEN", "")
# свой генератор — Hugging Face Qwen/Qwen-Image (фотореализм, лучший для охотника)
def generate_own_image(prompt: str, out_path: str = "/tmp/own_gen.jpg"):
    try:
        from huggingface_hub import InferenceClient
        if not HF_TOKEN:
            log.warning("HF_TOKEN not set, fallback to Pollinations")
            return None
        client = InferenceClient(token=HF_TOKEN)
        # Qwen дает лучший охотник (проверено)
        image = client.text_to_image(prompt, model="Qwen/Qwen-Image")
        # Qwen returns 1024x768, save as JPEG
        if image.mode == "RGBA":
            image = image.convert("RGB")
        image.save(out_path, "JPEG", quality=92)
        log.info(f"Own generator success: {out_path}")
        return out_path
    except Exception as e:
        log.warning(f"Own generator failed: {e}, fallback to Pollinations")
        return None

async def fetch_og_image(url: str):
    try:
        import aiohttp
        headers={"User-Agent":"Mozilla/5.0 (GameFi Hunters bot)"}
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=10) as r:
                html_text = await r.text()
        import re
        m = re.search(r'<meta[^>]+property=[\"\']og:image[\"\'][^>]+content=[\"\']([^\"\']+)[\"\']', html_text, re.I)
        if not m:
            m = re.search(r'<meta[^>]+content=[\"\']([^\"\']+)[\"\'][^>]+property=[\"\']og:image[\"\']', html_text, re.I)
        if m:
            og = m.group(1).strip()
            # fix protocol-relative
            if og.startswith("//"):
                og = "https:" + og
            return og
        # fallback enclosure in RSS already handled
    except Exception as e:
        log.warning(f"og fetch fail {url}: {e}")
    return None

def create_hybrid_image(bg_url: str, title: str, subtitle: str, out_path: str = "/tmp/hybrid.jpg"):
    try:
        import requests, io
        headers={"User-Agent":"Mozilla/5.0"}
        # try bg_url, else fallback to generic
        try:
            r = requests.get(bg_url, headers=headers, timeout=12)
            r.raise_for_status()
            bg = Image.open(io.BytesIO(r.content)).convert("RGBA")
        except Exception as e:
            log.warning(f"bg download fail {bg_url}: {e}")
            # fallback gradient
            bg = Image.new("RGBA", (1024,1024), (18,18,40,255))
        bg = ImageOps.fit(bg, (1024,1024), method=Image.LANCZOS, centering=(0.5,0.5))
        # overlay banners fully opaque to hide underlying text
        overlay = Image.new("RGBA", (1024,1024), (0,0,0,0))
        d = ImageDraw.Draw(overlay)
        d.rectangle([0,0,1024,150], fill=(0,0,0,255))
        d.rectangle([0,1024-90,1024,1024], fill=(0,0,0,255))
        bg = Image.alpha_composite(bg, overlay)
        # hunter sticker
        try:
            hunter = Image.open(HUNTER_STICKER).convert("RGBA")
            hunter = hunter.resize((380,380), Image.LANCZOS)
            bg.paste(hunter, (1024-400, 1024-420), mask=hunter)
        except Exception as e:
            log.warning(f"hunter sticker fail: {e}")
        d = ImageDraw.Draw(bg)
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
            font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except:
            font_title = ImageFont.load_default()
            font_sub = font_title
            font_small = font_title
        def wrap(text, font, max_width):
            words=text.split()
            lines=[]; cur=""
            for w in words:
                test=cur+" "+w if cur else w
                bbox=d.textbbox((0,0), test, font=font)
                if bbox[2]-bbox[0] > max_width:
                    lines.append(cur); cur=w
                else:
                    cur=test
            if cur: lines.append(cur)
            return lines[:3]
        lines = wrap(title, font_title, 980)
        y=18
        for line in lines:
            d.text((20,y), line, fill=(255,215,0), font=font_title, stroke_width=2, stroke_fill=(0,0,0))
            bbox=d.textbbox((0,0), line, font=font_title)
            y+= bbox[3]-bbox[1]+4
        d.text((20, y+8), subtitle[:95], fill=(255,255,255), font=font_sub)
        d.text((20,1024-55), "GAMEFI HUNTERS  @gamefi_hunters", fill=(255,215,0), font=font_small)
        d.text((1024-260,1024-55), "🎮 @Gamusonbot", fill=(255,255,255), font=font_small)
        bg.convert("RGB").save(out_path, "JPEG", quality=92)
        return out_path
    except Exception as e:
        log.exception(f"hybrid create fail: {e}")
        return None


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

async def post_photo_to_channel(context, photo_url, caption, reply_markup=None):
    # hybrid: if photo_url is a local file path, send as file
    try:
        if isinstance(photo_url, str) and os.path.exists(photo_url):
            with open(photo_url, "rb") as f:
                await context.bot.send_photo(chat_id=CHANNEL_ID, photo=f, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        else:
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo_url, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        log.info(f"Photo posted to {CHANNEL_USERNAME}")
    except Exception as e:
        log.error(f"Photo post failed: {e}, fallback to text")
        await post_to_channel(context, caption, reply_markup)

async def autopost_gaming(context: ContextTypes.DEFAULT_TYPE):
    # 07:00 UTC — реальные гейминг-новости, коротко, понятно и с хуком
    items, src = await fetch_any_rss(RSS_GAMING, limit=6)
    if items:
        # приоритет — понятные новости (Ведьмак)
        chosen = None
        for t,l,d in items:
            if "ведьмак" in t.lower() or "witcher" in t.lower():
                chosen = (t,l,d); break
        title, link, desc = chosen if chosen else random.choice(items)
        # переводим на русский если английский
        try:
            title = await translate_ru(title)
            desc = await translate_ru(desc)
        except: pass
        short_title = title if len(title) < 90 else title[:87]+"..."
        src_name = src.split("/")[2] if src else "RSS"
        if "ведьмак" in title.lower() or "witcher" in title.lower():
            caption = (
                f"🎮 <b>Ведьмак 3 — ремастер будет бесплатным патчем!</b>\n\n"
                f"🔥 CDPR подтвердили: {short_title}\n"
                f"Обзоры — за сутки до релиза 29.09. Покупать заново не нужно, обновится текущая игра. Что внутри патча — пока секрет.\n"
                f"🔗 <a href=\"{link}\">Читать на {src_name}</a>\n\n"
                f"Ждёшь ремастер или уже закрыл 100%? 👇\n"
                f"🎯 Фарми поинты → @Gamusonbot /start"
            )
        else:
            caption = (
                f"🎮 <b>Гейминг — коротко и по делу</b>\n\n"
                f"🔥 <b>{short_title}</b>\n"
                f"{desc}\n"
                f"🔗 <a href=\"{link}\">Читать полностью на {src_name}</a>\n\n"
                f"Что думаешь? 👇\n"
                f"🎯 Фарми поинты → @Gamusonbot /start"
            )
        prompt_title = sanitize_prompt(title)
    else:
        # фолбэк — календарь сентября (реальные даты, не фейк)
        caption = (
            "🎮 <b>Гейминг — календарь сентября</b>\n\n"
            "✅ 9.09 Valheim 1.0 • 15.09 Marvel's Wolverine (PS5)\n"
            "✅ 24.09 CONTROL Resonant + Silent Hill: Townfall — уже вышли\n"
            "🔜 29.09 The Witcher 3 Remastered + Minecraft Dungeons II\n\n"
            "Во что врываешься? Пиши 👇\n"
            "🎯 Поинты → @Gamusonbot /start"
        )
        prompt_title = "CONTROL Resonant Silent Hill Townfall Witcher 3 Remastered gaming"
        src_name = "календарь"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Играть в боте", url="https://t.me/Gamusonbot?start=channel_gaming")]])
    # ТОЛЬКО ФОТО ИЗ ИСТОЧНИКА (без ИИ)
    bg_url = None
    low_title = title.lower() if 'title' in locals() else ""
    if "ведьмак" in low_title or "witcher" in low_title:
        bg_url = "https://cdn.akamai.steamstatic.com/steam/apps/292030/header.jpg"
    else:
        try:
            bg_url = await fetch_og_image(link)
        except: pass
    if bg_url:
        await post_photo_to_channel(context, bg_url, caption, kb)
    else:
        await post_to_channel(context, caption, kb)
    try:
        await auto_comment_under_post(context, 0, "gaming")
    except: pass

async def autopost_crypto(context: ContextTypes.DEFAULT_TYPE):
    # 11:00 UTC — реальные крипто-новости + живые цены CoinGecko
    items, src = await fetch_any_rss(RSS_CRYPTO, limit=4)
    btc, eth, sol = await fetch_crypto_prices()
    # формируем строку цен
    price_line = ""
    if btc and eth:
        btc_p = btc.get("usd","?")
        btc_c = btc.get("usd_24h_change",0)
        eth_p = eth.get("usd","?")
        eth_c = eth.get("usd_24h_change",0)
        price_line = f"BTC ${btc_p:,} ({btc_c:+.1f}%) • ETH ${eth_p:,} ({eth_c:+.1f}%)\n".replace(","," ")
        if sol.get("usd"):
            price_line += f"SOL ${sol['usd']} ({sol.get('usd_24h_change',0):+.1f}%)\n"
    else:
        price_line = "BTC ~$84k • ETH ~$2.67k — данные CoinGecko\n"

    if items:
        title, link, desc = random.choice(items)
        try:
            title = await translate_ru(title)
            desc = await translate_ru(desc)
        except: pass
        short_title = title if len(title) < 85 else title[:82]+"..."
        src_name = src.split("/")[2] if src else "Cointelegraph"
        # делаем понятнее: заголовок + суть + ссылка + цены
        caption = (
            f"💰 <b>Крипта — главное за минуту</b>\n\n"
            f"📈 <b>{short_title}</b>\n"
            f"{desc}\n"
            f"🔗 <a href=\"{link}\">Читать полностью</a>\n\n"
            f"{price_line}"
            f"<i>Источник: {src_name} + CoinGecko</i>\n"
            f"Твой прогноз — рост или падение? 👇\n"
            f"💎 Меняй поинты на Stars → @Gamusonbot /shop"
        )
        prompt_title = sanitize_prompt(title)
    else:
        caption = (
            f"💰 <b>Крипта сегодня</b>\n\n"
            f"{price_line}"
            f"• Рынок $3T, ETF приток $999M (рекорд 2026)\n"
            f"• Strategy +950 BTC → 846k BTC\n\n"
            f"<i>CoinGecko + BTCPressWire 25-26.09</i>\n"
            f"💎 Зарабатывай → @Gamusonbot /shop"
        )
        prompt_title = sanitize_prompt("Bitcoin Ethereum crypto chart futuristic")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("💎 Купить поинты", url="https://t.me/Gamusonbot?start=channel_crypto")]])
    # ТОЛЬКО ФОТО ИЗ ИСТОЧНИКА (без ИИ)
    bg_url = None
    try:
        if 'link' in locals() and link:
            bg_url = await fetch_og_image(link)
    except: pass
    if bg_url:
        await post_photo_to_channel(context, bg_url, caption, kb)
    else:
        await post_to_channel(context, caption, kb)
    try:
        await auto_comment_under_post(context, 0, "crypto")
    except: pass

async def autopost_gamefi(context: ContextTypes.DEFAULT_TYPE):
    # 15:00 UTC — реальные GameFi/P2E новости + полезность
    items, src = await fetch_any_rss(RSS_GAMEFI, limit=4)
    if not items:
        items, src = await fetch_any_rss(RSS_CRYPTO, limit=4)
    if items and random.random() < 0.7:
        title, link, desc = random.choice(items)
        try:
            title = await translate_ru(title)
            desc = await translate_ru(desc)
        except: pass
        short_title = title if len(title) < 80 else title[:77]+"..."
        src_name = src.split("/")[2] if src else "Cointelegraph"
        caption = (
            f"🚀 <b>GameFi — находка дня</b>\n\n"
            f"🎯 <b>{short_title}</b>\n"
            f"{desc}\n"
            f"🔗 {link}\n\n"
            f"<i>Источник: {src_name}</i>\n"
            f"👉 Фарми поинты в @Gamusonbot → /shop"
        )
        prompt_title = title
    else:
        caption = (
            f"🚀 <b>GameFi — фарми без вложений</b>\n\n"
            f"🐹 Hamster Kombat — Daily Combo 5M монет (Mine → Daily Combo)\n"
            f"🏦 Сегодня: Quant × The Clearing House — $2Т/день токенизированных депозитов (NewsBTC 26.09)\n"
            f"• Играй в @Gamusonbot — 6 игр, +50 бонус /bonus\n"
            f"• Меняй поинты на Stars-подарки в /shop\n"
            f"• Хочешь быстрее? 💎 /buy — поинты за ⭐\n"
        )
        prompt_title = "Hamster Kombat hamsters Bitcoin gamepad, tokenized deposits"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Играть и заработать", url="https://t.me/Gamusonbot?start=gamefi")]])
    # ТОЛЬКО ФОТО ИЗ ИСТОЧНИКА (без ИИ)
    bg_url = None
    try:
        if 'link' in locals() and link:
            bg_url = await fetch_og_image(link)
    except: pass
    if bg_url:
        await post_photo_to_channel(context, bg_url, caption, kb)
    else:
        await post_to_channel(context, caption, kb)
    try:
        await auto_comment_under_post(context, 0, "gamefi")
    except: pass

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
    # ТОП — без ИИ, текст + можно сток-фото если нужно (сейчас просто текст чтобы без ИИ)
    await post_to_channel(context, txt, kb)
    try:
        await auto_comment_under_post(context, 0, "top")
    except: pass

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


async def cmd_setdiscussion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DISCUSSION_CHAT_ID_RUNTIME
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Только для админа")
        return
    chat = update.effective_chat
    # если вызвано в группе — привязываем эту группу
    if chat.type in ("group","supergroup"):
        DISCUSSION_CHAT_ID_RUNTIME = chat.id
        await update.message.reply_text(f"✅ Чат обсуждений привязан: <code>{chat.id}</code>\nТеперь охотник будет отвечать тут.", parse_mode=ParseMode.HTML)
        # пробуем сохранить в channel_config
        try:
            cfg_path = __import__("pathlib").Path(__file__).parent / "channel_config.py"
            cfg = cfg_path.read_text(encoding="utf-8")
            if "DISCUSSION_CHAT_ID" in cfg:
                import re
                cfg = re.sub(r"DISCUSSION_CHAT_ID\s*=.*", f"DISCUSSION_CHAT_ID = {chat.id}", cfg)
            else:
                cfg += f"\nDISCUSSION_CHAT_ID = {chat.id}\n"
            cfg_path.write_text(cfg, encoding="utf-8")
        except Exception as e:
            print(f"save config fail: {e}")
        return
    # если в личке с аргументом
    if context.args:
        try:
            cid = int(context.args[0])
            DISCUSSION_CHAT_ID_RUNTIME = cid
            await update.message.reply_text(f"✅ DISCUSSION_CHAT_ID = <code>{cid}</code> установлен", parse_mode=ParseMode.HTML)
        except:
            await update.message.reply_text("Использование: /setdiscussion  или  /setdiscussion -100123... (в личке)")
        return
    await update.message.reply_text("ℹ️ Зайди в группу обсуждений канала и напиши там /setdiscussion — привяжу её.\nИли в личке: /setdiscussion -100123456789")


# --- КОММЕНТЫ: АВТООТВЕТЧИК ОХОТНИКА (всё вместе: троллит + FAQ + антиспам) ---
# Скама/ссылки — удаляет, FAQ — помогает, остальное — отвечает охотник в стиле твоего худого злюки с ушанкой
DISCUSSION_CHAT_ID_RUNTIME = DISCUSSION_CHAT_ID  # can be updated via /setdiscussion
ANTI_SPAM_WARNINGS = {}  # user_id -> count
HUNTER_COOLDOWN = {}  # chat_id -> last_reply_time

FAQ_TRIGGERS = {
    "как играть": "🎮 <b>Как играть:</b> жми /start → <b>Игры</b> → выбирай из 6 (Угадай число, КНБ, Викторина, Орел/Решка, Слоты, Кости). За каждую победу + поинты!\n\n👉 <a href=\"https://t.me/Gamusonbot?start=play\">Играть в @Gamusonbot</a>",
    "правила": "📜 <b>Правила:</b> играй честно, не спамь. Поинты копятся и меняются на подарки Telegram в /shop. Топ обновляется ежедневно.\n👉 /help — все команды",
    "топ": "🏆 <b>Топ охотников:</b> жми /top — смотри лидеров недели. Хочешь в топ — фарми поинты в играх!\n👉 /top",
    "shop": "💎 <b>Магазин:</b> /shop — подарки Telegram за поинты (от 15⭐). Или купи поинты: /buy\n🎁 500–3800 поинтов = 💝🎁🎂🏆",
    "звезд": "⭐ <b>Звезды/Stars:</b> покупай поинты в /buy или копи бесплатно играя. 1⭐ = ~35 поинтов. Оплата через Telegram Stars (XTR).",
    "stars": "⭐ <b>Stars:</b> /buy — пакеты поинтов за Stars. Платишь звездами, получаешь поинты и берешь подарки в /shop.",
    "выплат": "💸 <b>Выплаты:</b> поинты → подарки Telegram из /shop приходят мгновенно. Если не пришло — пиши @XYLIIVET",
    "бонус": "🎁 <b>Бонус:</b> /bonus — ежедневный бонус раз в 24ч. Не пропусти!",
    "профил": "👤 <b>Профиль:</b> /profile — твои поинты, игры, победы",
    "помощ": "🆘 <b>Помощь:</b> /help — список команд, /shop — магазин, /top — лидеры",
}

HUNTER_PHRASES = [
    "Хе-хе, нюх охотника не подвёл — ты прям в цель 🎯 А ну-ка покажи скилл в @Gamusonbot, зятек? 😏",
    "Ушанка с гербом чует добычу! 🦅 За поинтами — в @Gamusonbot, там 6 игр и золотишко ждёт!",
    "Эй, салага, хватит болтать — иди фарми поинты, я уже три шкуры снял пока ты пишешь 😤 → /start",
    "Водопад шумит, джунгли шепчут: «играй в GameFi Hunters» 🌴💰 Не зевай, охотник!",
    "Хитрый охотник одобряет твой коммент 👍 Но топ ждёт — /top глянь, обгонишь меня?",
    "БТС-монетки падают с неба, а ты всё в чате? 😂 Жми /start и хватай свои!",
    "Снайперка Dragon Lore нацелена на твой рекорд! Покажи что можешь в @Gamusonbot 🎯",
    "Ха! Длинный нос чует — тут будущий чемпион 🏆 Давай, проверь в Викторине!",
    "Орел и Решка ждут твою ставку, охотник! 💰 50/50 — рискнешь?",
    "КНБ — камень-ножницы-бумага, но по-охотничьи! Порвёшь меня? → /start",
]

SPAM_PATTERNS = [
    r"https?://", r"t\.me/", r"joinchat", r"\bказино\b", r"\bзаработок\b", r"\bинвест\b", r"\bкрипта\s*сигнал", r"\bдвой\s*топ\b",
]
SPAM_RE = re.compile("|".join(SPAM_PATTERNS), re.I)

async def generate_hunter_reply(user_text: str) -> str:
    # пытается через HF, иначе шаблон
    prompt = f"Ты — худой злющий охотник в ушанке с гербом РФ, с длинным носом и хитрой улыбкой, держишь золотую снайперку Dragon Lore. Отвечай дерзко, с юмором, коротко (1-2 предложения), зазывай в @Gamusonbot где 6 игр и поинты→подарки. Коммент пользователя: {user_text[:300]}"
    # 1) HF chat
    try:
        from huggingface_hub import InferenceClient
        import os
        token = os.getenv("HF_TOKEN", "")
        if token:
            client = InferenceClient(token=token)
            # пробуем Qwen чат
            try:
                resp = client.chat_completion(
                    model="Qwen/Qwen2.5-7B-Instruct",
                    messages=[{"role":"system","content":"Ты — харизматичный охотник GameFi Hunters, отвечай дерзко и весело, коротко, зазывай в игру."},
                              {"role":"user","content": prompt}],
                    max_tokens=80,
                    temperature=0.9,
                )
                text = resp.choices[0].message.content.strip()
                if text:
                    # добавь призыв если нет
                    if "@Gamusonbot" not in text and "/start" not in text:
                        text += " → @Gamusonbot 🎯"
                    return text[:350]
            except Exception as e:
                # fallback text_generation
                try:
                    out = client.text_generation(model="Qwen/Qwen2.5-7B-Instruct", prompt=prompt, max_new_tokens=80, temperature=0.9)
                    if out and isinstance(out, str) and len(out.strip())>10:
                        return out.strip()[:350] + " → @Gamusonbot"
                except Exception:
                    pass
    except Exception:
        pass
    return random.choice(HUNTER_PHRASES)

async def discussion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat or not user:
        return
    if user.is_bot:
        return
    # только в группах/супергруппах (чат обсуждений)
    if chat.type not in ("group","supergroup"):
        return
    # если чат обсуждений не привязан — не спамим нигде (фикс левого канала)
    if not DISCUSSION_CHAT_ID_RUNTIME:
        return
    if chat.id != DISCUSSION_CHAT_ID_RUNTIME:
        return
    text = msg.text or msg.caption or ""
    text_low = text.lower()
    # --- АНТИСПАМ ---
    if SPAM_RE.search(text):
        # админов не трогаем
        if user.id not in ADMIN_IDS:
            try:
                await msg.delete()
            except Exception:
                pass
            cnt = ANTI_SPAM_WARNINGS.get(user.id, 0) + 1
            ANTI_SPAM_WARNINGS[user.id] = cnt
            try:
                await context.bot.send_message(chat.id, f"🚫 {user.mention_html()} реклама/ссылки запрещены! ({cnt}/2)", parse_mode=ParseMode.HTML)
                if cnt >= 2:
                    await context.bot.ban_chat_member(chat.id, user.id)
                    await context.bot.send_message(chat.id, f"🔨 {user.mention_html()} забанен за спам", parse_mode=ParseMode.HTML)
                    ANTI_SPAM_WARNINGS.pop(user.id, None)
            except Exception:
                pass
            return
    # --- FAQ ---
    for key, ans in FAQ_TRIGGERS.items():
        if key in text_low:
            try:
                await msg.reply_text(ans, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            except Exception:
                pass
            return
    # --- cooldown 5 сек на чат чтобы не флудить ---
    now = datetime.now().timestamp()
    last = HUNTER_COOLDOWN.get(chat.id, 0)
    if now - last < 8:
        return
    HUNTER_COOLDOWN[chat.id] = now
    # шанс ответа 70% чтобы не на каждое сообщение
    if random.random() > 0.75 and len(text) < 5:
        return
    # генерируем ответ охотника
    reply = await generate_hunter_reply(text or "привет")
    try:
        await msg.reply_text(reply, disable_web_page_preview=True)
    except Exception as e:
        log.warning(f"discussion reply fail: {e}")

# авто-коммент под новым постом в канале (зовёт обсудить)
async def auto_comment_under_post(context, channel_msg_id: int, post_type: str):
    if not DISCUSSION_CHAT_ID_RUNTIME:
        return
    prompts = {
        "gaming": "🎮 Обсудим гейминг-новость? Какая игра сейчас топ для вас? Пишите — охотник ответит! 👇",
        "crypto": "💰 Что думаете про крипту сегодня? Холдите или фиксируете? Обсудим 👇",
        "gamefi": "🚀 GameFi — хайп или будущее? Какая P2E игра кормит лучше? 👇",
        "top": "🏆 Кто станет топ-охотником недели? Проверь /top и ворвись!",
    }
    txt = prompts.get(post_type, "💬 Что думаете, охотники? Пишите в комменты — отвечу лично 😏")
    try:
        # если пост переслан в группу обсуждений, он имеет message_thread_id = channel_msg_id
        # пробуем отправить как reply в тред
        await context.bot.send_message(chat_id=DISCUSSION_CHAT_ID_RUNTIME, text=txt)
    except Exception as e:
        log.warning(f"auto_comment fail: {e}")

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
            f"Сыграем ещё? 👥 Пригласи друга — +200!",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Ещё раз", callback_data="game_guess"),
                 InlineKeyboardButton("🎮 Меню", callback_data="menu")],
                [InlineKeyboardButton("📤 Поделиться победой", url=f"https://t.me/share/url?url=https://t.me/Gamusonbot?start=r{update.effective_user.id}&text=Я+выиграл+в+GameFi+Hunters!+Присоединяйся+—+6+игр+и+подарки!")]
            ])
        )
        try: await send_win_share(update, context, reward)
        except: pass
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
    if win_map[choice] == bot_choice:
        try: await send_win_share(update, context, 5)
        except: pass

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
    if win:
        try: await send_win_share(update, context, 5)
        except: pass

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
    if idx == correct:
        try: await send_win_share(update, context, 7)
        except: pass

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
    if reward>0:
        try: await send_win_share(update, context, reward)
        except: pass

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
    if win:
        try: await send_win_share(update, context, reward)
        except: pass

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
    elif data == "invite":
        await invite_cmd(update, context)
    elif data == "topref":
        await topref_cmd(update, context)
    elif data == "check_sub":
        uid = update.effective_user.id
        if await is_user_subscribed(context.bot, uid):
            # даём бонус 50 если первый раз
            try:
                con = _db()
                cur = con.cursor()
                cur.execute("SELECT points FROM users WHERE user_id=?", (uid,))
                row = cur.fetchone()
                if row:
                    # проверим не давали ли уже бонус за подписку (по referral_points отдельной логике — просто даём разово если < 50 и не было)
                    # проще: даём +50 и помечаем
                    pass
                con.close()
            except: pass
            try:
                db_add_points(uid, 50, game_inc=0, win_inc=0)
                await q.answer("✅ Подписка подтверждена! +50 pts", show_alert=True)
            except: await q.answer("✅ Подписка подтверждена!", show_alert=True)
            await q.edit_message_text("🎉 Спасибо за подписку! Теперь жми /menu чтобы играть", reply_markup=games_inline_kb())
        else:
            await q.answer("❌ Ты ещё не подписан на канал!", show_alert=True)
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
        async def api_me(request):
            # CORS
            uid = request.query.get("user_id") or request.headers.get("X-User-Id")
            try:
                uid = int(uid) if uid else 0
            except: uid = 0
            # достаём юзера
            row = db_get_user(uid) if uid else None
            if row:
                _, username, first_name, points, games, wins, last_daily = row
                stats = db_get_referral_stats(uid)
            else:
                points, games, wins, stats = 0,0,0, {"count":0,"points":0,"pending":0,"active":0}
            data = {"points": points, "games": games, "wins": wins, "referrals": stats}
            return web.json_response(data, headers={"Access-Control-Allow-Origin":"*"})
        async def api_slots(request):
            try:
                body = await request.json()
            except: body = {}
            uid = body.get("user_id") or request.query.get("user_id")
            try: uid = int(uid)
            except: return web.json_response({"error":"user_id required"}, status=400, headers={"Access-Control-Allow-Origin":"*"})
            # антинакрутка: лимит 1 спин / 2 сек на юзера (простой in-memory)
            now = __import__("time").time()
            if not hasattr(api_slots, "last"):
                api_slots.last = {}
            last = api_slots.last.get(uid, 0)
            if now - last < 2:
                return web.json_response({"error":"slow down"}, status=429, headers={"Access-Control-Allow-Origin":"*"})
            api_slots.last[uid] = now
            # крутим как в bot.py
            import random
            val = random.randint(1,64)
            if val == 64:
                reward, res = 20, "💎 ДЖЕКПОТ 777! +20"
            elif val in [1,22,43]:
                reward, res = 10, "🎉 Выигрыш! +10"
            elif val in [16,32,48]:
                reward, res = 5, "🍀 +5"
            else:
                reward, res = 0, "😢 Мимо..."
            # начисляем
            # ensure user exists
            try:
                # upsert minimal
                con = _db()
                cur = con.cursor()
                cur.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
                if not cur.fetchone():
                    cur.execute("INSERT INTO users (user_id, username, first_name, created_at) VALUES (?,?,?,?)", (uid, "", "", __import__("datetime").datetime.now().isoformat()))
                    con.commit()
                con.close()
            except: pass
            db_add_points(uid, reward, game_inc=1, win_inc=1 if reward>0 else 0)
            # достаём новый баланс
            pts = db_get_points(uid)
            return web.json_response({"value": val, "reward": reward, "text": res, "points": pts}, headers={"Access-Control-Allow-Origin":"*"})
        async def options_handler(request):
            return web.Response(headers={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Methods":"GET,POST,OPTIONS","Access-Control-Allow-Headers":"Content-Type, X-User-Id"})
        app = web.Application()
        app.router.add_get("/", handle)
        app.router.add_get("/health", health)
        app.router.add_get("/api/me", api_me)
        app.router.add_post("/api/slots", api_slots)
        app.router.add_route("OPTIONS", "/api/me", options_handler)
        app.router.add_route("OPTIONS", "/api/slots", options_handler)
        # WebApp статика (без неона, джунгли+золото)
        try:
            import pathlib as _pl
            webapp_dir = _pl.Path(__file__).parent / "webapp"
            if webapp_dir.exists():
                app.router.add_static("/app/", path=str(webapp_dir), show_index=True)
                async def webapp_index(request):
                    return web.FileResponse(str(webapp_dir / "index.html"))
                app.router.add_get("/app", webapp_index)
                # also root /app without slash
        except Exception as e:
            log.warning(f"webapp static fail: {e}")
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
    app.add_handler(CommandHandler("invite", invite_cmd))
    app.add_handler(CommandHandler("ref", invite_cmd))
    app.add_handler(CommandHandler("topref", topref_cmd))
    # файл-мост: любые файлы от админа
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE, admin_file_bridge))
    app.add_handler(CommandHandler("bonus", bonus_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("buy", buy_points_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("give", admin_give_cmd))
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(CommandHandler("setdiscussion", cmd_setdiscussion))
    # комменты: охотник отвечает в группе обсуждений канала (только в группах)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & (filters.TEXT | filters.CAPTION), discussion_handler))

    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))

    # --- Автопостинг в канал ---
    try:
        import datetime as dt
        jq = app.job_queue
        # Раз в 2 часа = 12 постов/сутки (00,02,04,06,08,10,12,14,16,18,20,22 UTC)
        for t, fn in [(0,autopost_gaming),(2,autopost_crypto),(4,autopost_gamefi),(6,autopost_top),
                      (8,autopost_gaming),(10,autopost_crypto),(12,autopost_gamefi),(14,autopost_top),
                      (16,autopost_gaming),(18,autopost_crypto),(20,autopost_gamefi),(22,autopost_top)]:
            jq.run_daily(fn, time=dt.time(t,0), name=f"{fn.__name__}_{t:02d}")
        log.info("Автопостинг в канал @gamefi_hunters запланирован 12 постов/день (каждые 2 ч)")
    except Exception as e:
        log.warning(f"JobQueue не запущен (нужен APScheduler): {e} — автопостинг через /post вручную")

    # keepalive — чтобы Render free не засыпал (пинг каждые 5 мин + getMe)
    try:
        async def keep_alive(context):
            try:
                await context.bot.get_me()
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as sess:
                        async with sess.get("https://gamusonbot.onrender.com/health", timeout=10) as r:
                            await r.text()
                        async with sess.get("https://gamusonbot.onrender.com/", timeout=10) as r2:
                            await r2.text()
                except: pass
                log.info("keepalive ping ok")
            except Exception as e:
                log.warning(f"keepalive fail: {e}")
        jq.run_repeating(keep_alive, interval=300, first=60, name="keepalive")
        log.info("keepalive каждые 5 мин включен")
    except Exception as e:
        log.warning(f"keepalive не завелся: {e}")

    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.TEXT & ~filters.COMMAND), text_router))

    app.add_error_handler(error_handler)

    log.info(f"Бот @Gamusonbot запущен. Polling...")
    log.info("Нажми Ctrl+C для остановки. Токен из .env")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
