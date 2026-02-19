# app/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import timedelta
from jose import JWTError, jwt  # Necessário para decodificar o token

from app.core.auth import authenticate_user, create_access_token
from app.core.database import get_db
from app.core.config import settings
from app.models.entities import User  # Importado para buscar o usuário no banco

router = APIRouter()

# Define onde o FastAPI deve procurar o token (no header Authorization: Bearer ...)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

@router.post("/login")
async def login(
    response: Response, 
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    # Tenta autenticar no banco de dados local
    user = await authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Cria o Token com validade de 24 horas
    access_token = create_access_token(
        data={
            "sub": user.username,
            "loja_permissao": user.loja_permissao 
        },
        expires_delta=timedelta(minutes=60 * 24)
        )
    
    # Define o Cookie para o navegador manter a sessão
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=60 * 60 * 24, # 1 dia
        samesite="lax",
        secure=False 
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "user": {"username": user.username, "name": user.name, "loja_permissao": user.loja_permissao}
    }

# --- FUNÇÃO ADICIONADA PARA RESOLVER O ERRO DE IMPORTAÇÃO E FILTRAR VENDAS ---

async def get_current_user(
    db: Session = Depends(get_db), 
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Dependência que valida o JWT e retorna o objeto do usuário logado.
    Isso permite que a rota de ordens saiba se o Igor ou o Victor está acessando.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token de acesso inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decodifica o token usando as chaves configuradas no app
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        
        if username is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
        
    # Busca o usuário no banco de dados para acessar o campo 'loja_permissao'
    user = db.query(User).filter(User.username == username).first()
    
    if user is None:
        raise credentials_exception
        
    return user