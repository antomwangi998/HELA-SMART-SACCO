from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from passlib.hash import bcrypt
from database import SessionLocal, engine
from models import Base, User
from auth import create_token, verify_token
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(title="HELA SMART SACCO API")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Load portal
def load_portal():
    if os.path.exists("hela_portal.html"):
        with open("hela_portal.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h2>HELA SACCO PORTAL</h2>"

@app.get("/", response_class=HTMLResponse)
def portal():
    return load_portal()

@app.post("/api/auth/register")
def register(data: dict, db: Session = Depends(get_db)):
    phone = data.get("phone")
    password = data.get("password")
    name = data.get("full_name")

    if db.query(User).filter(User.phone == phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered")

    hashed_pw = bcrypt.hash(password)

    user = User(phone=phone, full_name=name, password=hashed_pw)
    db.add(user)
    db.commit()

    token = create_token({"sub": user.id, "role": "member"})
    return {"token": token, "role": "member"}

@app.post("/api/auth/login")
def login(data: dict, db: Session = Depends(get_db)):
    phone = data.get("phone")
    password = data.get("password")

    user = db.query(User).filter(User.phone == phone).first()

    if not user or not bcrypt.verify(password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"sub": user.id, "role": user.role})
    return {"token": token, "role": user.role}
