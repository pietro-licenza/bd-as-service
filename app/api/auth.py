from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.core.auth import authenticate_user, create_access_token, get_current_user
from datetime import timedelta

router = APIRouter()

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=60)
    )
    return {"access_token": access_token, "token_type": "bearer", "user": {"username": user["username"], "name": user["name"], "loja": user["loja"]}}
