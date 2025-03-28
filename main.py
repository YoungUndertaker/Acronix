from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import random
import string
import smtplib
from email.mime.text import MIMEText
from twilio.rest import Client

app = FastAPI()

# SQLite
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

# Twilio (пока заглушки, заменишь позже)
TWILIO_SID = "your_twilio_sid"
TWILIO_AUTH_TOKEN = "your_twilio_auth_token"
TWILIO_PHONE_NUMBER = "your_twilio_phone_number"
twilio_client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

# Gmail (пока заглушки, заменишь позже)
EMAIL_ADDRESS = "your_email@gmail.com"
EMAIL_PASSWORD = "your_app_password"

# Модели
class PhoneAuth(BaseModel):
    phone: str

class PhoneCode(BaseModel):
    phone: str
    code: str

class EmailAuth(BaseModel):
    email: str
    password: str

# Хранилище кодов
phone_codes = {}

# Генерация кода
def generate_code():
    return ''.join(random.choices(string.digits, k=6))

# Отправка SMS
def send_sms(phone: str, code: str):
    message = twilio_client.messages.create(
        body=f"Your code: {code}",
        from_=TWILIO_PHONE_NUMBER,
        to=phone
    )
    return message.sid

# Отправка email
def send_email(email: str, code: str):
    msg = MIMEText(f"Your code: {code}")
    msg['Subject'] = 'Verification Code'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = email
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

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

@app.post("/auth/email")
async def auth_email(data: EmailAuth):
    cursor.execute("SELECT id, auth_key FROM users WHERE email = ?", (data.email,))
    user = cursor.fetchone()
    if user:
        cursor.execute("SELECT password FROM users WHERE email = ?", (data.email,))
        if cursor.fetchone()[0] == data.password:
            return {"auth_key": user[1]}
        raise HTTPException(status_code=401, detail="Invalid password")
    else:
        auth_key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        code = generate_code()
        send_email(data.email, code)
        cursor.execute("INSERT INTO users (email, password, auth_key) VALUES (?, ?, ?)", 
                       (data.email, data.password, auth_key))
        conn.commit()
        return {"message": "Code sent to email", "auth_key": auth_key}
