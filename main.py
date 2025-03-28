from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import random
import string

app = FastAPI()

# Подключение к SQLite
conn = sqlite3.connect("telegram_clone.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE,
        email TEXT UNIQUE,
        password TEXT,
        auth_key TEXT,
        is_premium INTEGER DEFAULT 0
    )
""")
conn.commit()

# Модели для данных
class PhoneAuth(BaseModel):
    phone: str

class PhoneCode(BaseModel):
    phone: str
    code: str

class EmailAuth(BaseModel):
    email: str
    password: str

# Временное хранилище кодов (вместо SMS)
phone_codes = {}

# Генерация случайного кода
def generate_code():
    return ''.join(random.choices(string.digits, k=6))

# Авторизация по номеру телефона
@app.post("/auth/phone")
async def auth_phone(data: PhoneAuth):
    cursor.execute("SELECT id FROM users WHERE phone = ?", (data.phone,))
    user = cursor.fetchone()
    code = generate_code()
    phone_codes[data.phone] = code
    # В реале отправь SMS, тут просто выводим в консоль
    print(f"Code for {data.phone}: {code}")
    return {"message": "Code sent"}

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

# Авторизация по email
@app.post("/auth/email")
async def auth_email(data: EmailAuth):
    cursor.execute("SELECT id, auth_key FROM users WHERE email = ?", (data.email,))
    user = cursor.fetchone()
    if user:
        cursor.execute("SELECT password FROM users WHERE email = ?", (data.email,))
        stored_password = cursor.fetchone()[0]
        if stored_password == data.password:
            return {"auth_key": user[1]}
        raise HTTPException(status_code=401, detail="Invalid password")
    else:
        auth_key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        cursor.execute("INSERT INTO users (email, password, auth_key) VALUES (?, ?, ?)", 
                       (data.email, data.password, auth_key))
        conn.commit()
        return {"auth_key": auth_key}

# Пример эндпоинта для отправки сообщения (для Telegram-функций)
@app.post("/messages/send")
async def send_message(from_id: int, to_id: int, text: str, auth_key: str):
    cursor.execute("SELECT id FROM users WHERE auth_key = ?", (auth_key,))
    if cursor.fetchone():
        # Здесь логика сохранения сообщения в БД (пока заглушка)
        return {"message": "Sent"}
    raise HTTPException(status_code=403, detail="Unauthorized")
