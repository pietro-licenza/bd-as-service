# app/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.auth import authenticate_user, create_access_token
from app.core.database import get_db
from app.core.config import settings

router = APIRouter()

@router.post("/login")
async def login(
    response: Response, 
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    # Tenta autenticar no Supabase
    user = await authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Cria o Token com validade de 24 horas
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=60 * 24)
    )
    
    # Define o Cookie para o navegador manter a sessão
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=60 * 60 * 24, # 1 dia
        samesite="lax",
        secure=False # Em produção (HTTPS) deve ser True
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "user": {"username": user.username, "name": user.name}
    }