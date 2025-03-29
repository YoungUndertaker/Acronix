from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import random
import string
import smtplib
from email.mime.text import MIMEText
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
        email TEXT UNIQUE,
        password TEXT,
        auth_key TEXT,
        is_active INTEGER DEFAULT 1
    )
""")
conn.commit()

# Подтягиваем переменные окружения
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

if not all([EMAIL_ADDRESS, EMAIL_PASSWORD]):
    logger.error("One or more environment variables are missing!")
    raise RuntimeError("Missing environment variables")

# Модели
class UserRegister(BaseModel):
    email: str
    password: str

class EmailCode(BaseModel):
    email: str
    code: str

class UserLogin(BaseModel):
    email: str
    password: str

# Хранилище кодов для верификации
email_codes = {}

# Генерация кода
def generate_code():
    return ''.join(random.choices(string.digits, k=6))

# Отправка кода через email
def send_email(email: str, code: str):
    try:
        msg = MIMEText(f"Your verification code for Acronix Messenger: {code}")
        msg['Subject'] = 'Verification Code'
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send email to {email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

# Эндпоинты
@app.post("/register")
async def register(data: UserRegister):
    # Проверяем, есть ли уже такой email
    cursor.execute("SELECT id FROM users WHERE email = ?", (data.email,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Генерируем код для верификации
    code = generate_code()
    email_codes[data.email] = code
    
    # Отправляем код на email
    send_email(data.email, code)
    
    # Сохраняем email и пароль в базе (но пока без auth_key, ждём верификации)
    cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (data.email, data.password))
    conn.commit()
    
    return {"message": "Code sent to email for verification"}

@app.post("/register/verify")
async def verify_registration(data: EmailCode):
    if email_codes.get(data.email) == data.code:
        # Проверяем, есть ли пользователь
        cursor.execute("SELECT id FROM users WHERE email = ?", (data.email,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=400, detail="User not found")
        
        # Генерируем auth_key после успешной верификации
        auth_key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        cursor.execute("UPDATE users SET auth_key = ? WHERE email = ?", (auth_key, data.email))
        conn.commit()
        
        # Удаляем код из временного хранилища
        del email_codes[data.email]
        return {"auth_key": auth_key}
    raise HTTPException(status_code=400, detail="Invalid code")

@app.post("/login")
async def login(data: UserLogin):
    cursor.execute("SELECT auth_key, password FROM users WHERE email = ?", (data.email,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    if user[1] != data.password:
        raise HTTPException(status_code=400, detail="Invalid password")
    if not user[0]:  # Проверяем, есть ли auth_key (то есть прошла ли верификация)
        raise HTTPException(status_code=400, detail="Email not verified")
    return {"auth_key": user[0]}

@app.get("/")
async def root():
    return {"message": "Welcome to Acronix Messenger API"}
