CHANNEL_USERNAME = "@gamefi_hunters"
CHANNEL_ID = -1003642138077  # КриптоКатика
CHANNEL_TITLE = "КриптоКатика | GameFi Hunters"

# ID админа для ручного постинга
ADMIN_IDS = [8206258615]

# Расписание автопостинга (UTC)
# Франкфурт UTC+2 (лето) -> 09:00 Frankfurt = 07:00 UTC, 13:00 = 11:00 UTC, 17:00 = 15:00 UTC, 20:00 = 18:00 UTC
POST_SCHEDULE = [
    {"time": "07:00", "type": "gaming"},   # 09:00 Frankfurt — гейминг
    {"time": "11:00", "type": "crypto"},   # 13:00 Frankfurt — крипта
    {"time": "15:00", "type": "gamefi"},   # 17:00 Frankfurt — GameFi
    {"time": "18:00", "type": "top"},      # 20:00 Frankfurt — топ + розыгрыш
]
