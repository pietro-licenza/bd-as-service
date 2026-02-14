"""
Authentication and JWT utilities for BD | AS Platform
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

# Secret key for JWT (should be kept secret in production)
SECRET_KEY = "supersecretkey123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Hardcoded users (username: {name, password hash, loja})
users_db = {
    "admin": {"name": "Administrador", "hashed_password": "$2b$12$w1Qw1Qw1Qw1Qw1Qw1Qw1QeQw1Qw1Qw1Qw1Qw1Qw1Qw1Qw1Qw1Qw1Q", "loja": "todas"},
    "teste": {"name": "teste", "hashed_password": "$2b$12$hHE9hoSmTf/pvVV.302zCOqIEzQiV4Oo8bqUUI4i0WNlRN74KXHGe", "loja": "todas"},
    "primo1": {"name": "Primo 1", "hashed_password": "$2b$12$w1Qw1Qw1Qw1Qw1Qw1Qw1QeQw1Qw1Qw1Qw1Qw1Qw1Qw1Qw1Qw1Qw1Q", "loja": "loja1"},
    "primo2": {"name": "Primo 2", "hashed_password": "$2b$12$w1Qw1Qw1Qw1Qw1Qw1Qw1QeQw1Qw1Qw1Qw1Qw1Qw1Qw1Qw1Qw1Qw1Q", "loja": "loja2"}
}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(username: str):
    user = users_db.get(username)
    if user:
        return {"username": username, **user}
    return None

def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(username)
    if user is None:
        raise credentials_exception
    return user
