from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext
from sqlalchemy import select
import uuid
from db import SessionLocal
from models import User
from datetime import datetime, timedelta, timezone
from jose import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import settings

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter()
bearer = HTTPBearer()

class RegisterBody(BaseModel):
    username: str
    password: str

class LoginBody(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(body: LoginBody):
    async with SessionLocal() as db:
        user = (await db.execute(
            select(User).where(User.username == body.username)
        )).scalar_one_or_none()

        if not user or not pwd.verify(body.password, user.password_hash):
            raise HTTPException(401, "用户名或密码错误")

        token = jwt.encode(
            {
                "sub": user.id,
                "exp": datetime.now(timezone.utc) + timedelta(hours=24),
            },
            settings.jwt_secret,
            algorithm="HS256",
        )
        return {"access_token": token, "token_type": "bearer"}

@router.post("/register")
async def register(body: RegisterBody):
    async with SessionLocal() as db:
        existing = await db.execute(select(User).where(User.username == body.username))
        if existing.scalar_one_or_none():
            raise HTTPException(400, "用户名已存在")

        user = User(
            id=str(uuid.uuid4()),
            username=body.username,
            password_hash=pwd.hash(body.password),
        )
        db.add(user)
        await db.commit()
        return {"ok": True}


async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    token = creds.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(401, "登录已过期，请重新登录")
    return user_id

@router.get("/me")
async def me(user_id: str = Depends(get_current_user)):
    return {"user_id": user_id}