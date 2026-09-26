#!/bin/bash
cd "$(dirname "$0")"
echo "🎮 Запуск Gamebot @Gamusonbot..."
pip install -r requirements.txt -q
python bot.py
