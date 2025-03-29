from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import random
import string
import requests
import os
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# SQLite для хранения данных пользователей
conn = sqlite3.connect("messenger.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE,
        auth_key TEXT,
        is_active INTEGER DEFAULT 1
    )
""")
conn.commit()

# Подтягиваем переменные окружения
SINCH_SERVICE_PLAN_ID = os.getenv("SINCH_SERVICE_PLAN_ID")
SINCH_API_TOKEN = os.getenv("SINCH_API_TOKEN")
SINCH_PHONE_NUMBER = os.getenv("SINCH_PHONE_NUMBER")  # Опционально

if not all([SINCH_SERVICE_PLAN_ID, SINCH_API_TOKEN]):
    logger.error("One or more environment variables are missing!")
    raise RuntimeError("Missing environment variables")

# Модели
class PhoneAuth(BaseModel):
    phone: str

class PhoneCode(BaseModel):
    phone: str
    code: str

# Хранилище кодов (временное, можно заменить на Redis для масштабируемости)
phone_codes = {}

# Генерация кода
def generate_code():
    return ''.join(random.choices(string.digits, k=6))

# Отправка SMS через Sinch
def send_sms(phone: str, code: str):
    try:
        url = f"https://sms.api.sinch.com/xms/v1/{SINCH_SERVICE_PLAN_ID}/batches"
        headers = {
            "Authorization": f"Bearer {SINCH_API_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "from": SINCH_PHONE_NUMBER if SINCH_PHONE_NUMBER else "Messenger",
            "to": [phone],
            "body": f"Your verification code: {code}"
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 201:
            logger.info(f"SMS sent to {phone}: {response.json()['id']}")
            return response.json()["id"]
        else:
            logger.error(f"Failed to send SMS to {phone}: {response.text}")
            raise HTTPException(status_code=500, detail=f"Failed to send SMS: {response.text}")
    except Exception as e:
        logger.error(f"Failed to send SMS to {phone}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send SMS: {str(e)}")

# Эндпоинты
@app.post("/auth/phone")
async def auth_phone(data: PhoneAuth):
    code = generate_code()
    phone_codes[data.phone] = code
    send_sms(data.phone, code)
    return {"message": "Code sent to phone"}

@app.post("/auth/phone/verify")
async def verify_phone(data: PhoneCode):
    if phone_codes.get(data.phone) == data.code:
        cursor.execute("SELECT id, auth_key FROM users WHERE phone = ?", (data.phone,))
        user = cursor.fetchone()
        if not user:
            auth_key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            cursor.execute("INSERT INTO users (phone, auth_key) VALUES (?, ?)", (data.phone, auth_key))
            conn.commit()
        else:
            auth_key = user[1]
        del phone_codes[data.phone]
        return {"auth_key": auth_key}
    raise HTTPException(status_code=400, detail="Invalid code")

@app.get("/")
async def root():
    return {"message": "Welcome to Independent Messenger API"}
