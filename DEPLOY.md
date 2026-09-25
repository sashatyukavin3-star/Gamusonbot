# 🚀 Бесплатный деплой Gamebot @Gamusonbot

Бот уже настроен для 3 бесплатных хостингов. Выбирай любой — везде бесплатно.

---

## Вариант 1: Render.com (самый простой, 2 минуты) ⭐️ РЕКОМЕНДУЮ

**Плюсы:** Бесплатно, без карты, кнопка Deploy, авто-сборка из GitHub

1. Залей папку `gamebot` на GitHub:
   - Создай репозиторий `gamusonbot` на github.com (public/private)
   - Залей файлы: `bot.py`, `requirements.txt`, `Dockerfile`, `render.yaml`, `.env.example`
   - **НЕ** заливай `.env` с токеном!

2. Зайди на https://dashboard.render.com → `New` → `Blueprint` → подключи репозиторий
   - Render сам найдет `render.yaml` и предложит создать Web Service
   - Вставь в переменную `BOT_TOKEN` = `8652086324:AAEXTu3NS3Xl8G1NYrhYJmKF-bJnr-vtk8Q`
   - `PORT` = `10000` уже стоит
   - Нажми `Apply`

3. Готово! Через 2-3 минуты бот будет онлайн 24/7.
   - Логи смотри в Render Dashboard
   - Бесплатный тариф спит только если 15 мин нет HTTP запросов — но теперь у нас health-server на `/health`, Render не усыпит пока есть трафик, а Telegram polling держит бота живым.

**One-click кнопка (для README):**
```
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=ТВОЙ_GITHUB_URL)
```

---

## Вариант 2: Fly.io (не засыпает, самый надежный для ботов)

**Плюсы:** Не спит, бесплатный лимит 3 микро-VM, регион `fra` (Франкфурт — рядом с тобой)

```bash
# 1. Установи flyctl
curl -L https://fly.io/install.sh | sh

# 2. Залогинься
fly auth login

# 3. Деплой
cd gamebot
fly launch --no-deploy  # если впервые, выбери fra, app name gamusonbot
fly secrets set BOT_TOKEN=8652086324:AAEXTu3NS3Xl8G1NYrhYJmKF-bJnr-vtk8Q
fly deploy
fly logs  # смотреть логи
```

`fly.toml` уже настроен: `fra`, 256MB, `auto_stop_machines=false` чтобы не засыпал.

Бесплатно: ~1600 часов/месяц на shared-cpu — хватает на бота 24/7.

---

## Вариант 3: Railway.app (1 клик)

**Плюсы:** Самый быстрый деплой, 5$ бесплатных кредитов/месяц (~500 часов)

1. Зайди на https://railway.app → `New Project` → `Deploy from GitHub repo`
2. Выбери репозиторий `gamusonbot`
3. В `Variables` добавь `BOT_TOKEN`
4. Deploy → бот онлайн

`railway.toml` и `Procfile` уже готовы. Railway сам найдет `Dockerfile`.

**Кнопка:**
```
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/XXXX)
```

---

## Вариант 4: Replit (без GitHub, прямо в браузере)

1. https://replit.com → `Create Repl` → `Import from GitHub` или загрузи zip
2. В `Secrets` (🔒) добавь `BOT_TOKEN`
3. Нажми `Run` — бот запустится
4. Чтобы не засыпал: добавь https://uptimerobot.com → монитор на URL твоего Repl (каждые 5 мин пингует)

---

## Вариант 5: PythonAnywhere (для новичков, без Docker)

1. https://www.pythonanywhere.com → бесплатный аккаунт
2. `Consoles` → `Bash` → `git clone ТВОЙ_РЕПО && cd gamusonbot`
3. `pip install -r requirements.txt`
4. `Tasks` → `Create a new always-on task` → `python3 /home/твой_юзер/gamusonbot/bot.py`

---

## ⚡️ Быстрый старт без GitHub (zip)

Я уже собрал архив:

```bash
cd /home/user
zip -r gamusonbot.zip gamebot/ -x "gamebot/gamebot.db" "gamebot/__pycache__/*"
```

Скачай `gamusonbot.zip` и залей на любой хостинг из списка.

---

## 🔑 Переменные окружения

Везде нужно указать только одну переменную:

```
BOT_TOKEN=8652086324:AAEXTu3NS3Xl8G1NYrhYJmKF-bJnr-vtk8Q
PORT=10000  # для Render (уже в render.yaml)
```

Файл `.env` не нужен на хостинге — используй `Variables`/`Secrets` в панели.

---

## 🩺 Проверка после деплоя

1. В логах должно быть: `Бот @Gamusonbot запущен. Polling...` и `Health server запущен на порту 10000`
2. Открой `https://ТВОЙ_СЕРВИС.onrender.com/health` — должен ответить `ok`
3. В Telegram: `@Gamusonbot` → `/start` → бот отвечает

---

## ❓ Что выбрать?

- **Хочешь 1 клик и не париться** → **Render**
- **Хочешь чтобы не засыпал** → **Fly.io**
- **Хочешь без карты и GitHub** → **Replit + UptimeRobot**
- **У тебя есть VPS** → `nohup python bot.py &`

Напиши какой вариант выбрал — я дам точные команды или задеплою за тебя (скинь доступ к GitHub/Render).
