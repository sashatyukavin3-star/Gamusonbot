CHANNEL_USERNAME = "@gamefi_hunters"
CHANNEL_ID = -1003642138077  # КриптоКатика
CHANNEL_TITLE = "КриптоКатика | GameFi Hunters"

# ID админа для ручного постинга
ADMIN_IDS = [8206258615]

# Расписание автопостинга (UTC) — раз в 2 часа = 12 постов/сутки
# Frankfurt UTC+2 (лето) -> 00 UTC=02 Frankfurt, 02=04, 04=06, 06=08, 08=10, 10=12, 12=14, 14=16, 16=18, 18=20, 20=22, 22=00
POST_SCHEDULE = [
    {"time": "00:00", "type": "gaming"},   # 02:00 Frankfurt — гейминг
    {"time": "02:00", "type": "crypto"},   # 04:00 Frankfurt — крипта
    {"time": "04:00", "type": "gamefi"},   # 06:00 Frankfurt — GameFi
    {"time": "06:00", "type": "top"},      # 08:00 Frankfurt — топ
    {"time": "08:00", "type": "gaming"},   # 10:00 Frankfurt — гейминг
    {"time": "10:00", "type": "crypto"},   # 12:00 Frankfurt — крипта
    {"time": "12:00", "type": "gamefi"},   # 14:00 Frankfurt — GameFi
    {"time": "14:00", "type": "top"},      # 16:00 Frankfurt — топ
    {"time": "16:00", "type": "gaming"},   # 18:00 Frankfurt — гейминг
    {"time": "18:00", "type": "crypto"},   # 20:00 Frankfurt — крипта
    {"time": "20:00", "type": "gamefi"},   # 22:00 Frankfurt — GameFi
    {"time": "22:00", "type": "top"},      # 00:00 Frankfurt — топ
]
