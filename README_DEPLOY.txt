БЕСПЛАТНЫЙ ДЕПЛОЙ - ИНСТРУКЦИЯ 2 МИНУТЫ
=====================================

САМЫЙ ПРОСТОЙ СПОСОБ (Render, без карты, бесплатно навсегда):
1. Создай репо https://github.com/new -> gamusonbot -> Public -> Create
2. Загрузи файлы из gamusonbot.zip на GitHub (drag & drop прямо в браузере!)
   Или через git:
     git clone https://github.com/ТВОЙ/gamusonbot.git
     unzip gamusonbot.zip -d gamusonbot
     cd gamusonbot && git add . && git commit -m "init" && git push
3. Зайди на https://dashboard.render.com -> New -> Blueprint -> выбери gamusonbot
4. Добавь переменную BOT_TOKEN = 8652086324:AAEXTu3NS3Xl8G1NYrhYJmKF-bJnr-vtk8Q
5. Нажми Apply -> бот запустится через 2-3 минуты, логи увидишь в Render

АЛЬТЕРНАТИВА без GitHub (Replit, 1 минута):
1. https://replit.com -> Create Repl -> Import from ZIP -> загрузи gamusonbot.zip
2. Вкладка Secrets (замок) -> добавь BOT_TOKEN
3. Нажми Run -> бот онлайн
4. Чтобы не засыпал: https://uptimerobot.com -> Add Monitor -> HTTP -> URL твоего repl -> 5 min

Fly.io (не засыпает, но нужна карта для верификации):
fly auth login
fly launch
fly secrets set BOT_TOKEN=...
fly deploy

Готово! Бот уже работает и отвечает в @Gamusonbot
