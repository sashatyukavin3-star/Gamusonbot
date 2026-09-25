FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .
# .env не копируем - токен приходит через переменные окружения Render (BOT_TOKEN)
ENV PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["python", "bot.py"]
