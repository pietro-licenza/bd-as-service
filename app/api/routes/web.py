"""
Web routes for serving HTML pages - Fixed Version
"""
from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.config import settings

router = APIRouter(tags=["Web Pages"])
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))

# Caminho para os arquivos estáticos na pasta frontend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    """Página inicial - Agora busca o usuário logado para mostrar o nome"""
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        # Tenta validar o usuário pelo token do cookie
        current_user = await get_current_user(request, db)
        return templates.TemplateResponse("home.html", {
            "request": request, 
            "user": current_user
        })
    except Exception:
        # Se o token for inválido ou expirado, manda para o login
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/login", response_class=HTMLResponse)
async def login_page():
    """Retorna a sua tela de login real da pasta frontend"""
    login_path = os.path.join(FRONTEND_DIR, "login.html")
    if os.path.exists(login_path):
        return FileResponse(login_path)
    return HTMLResponse("Erro: arquivo frontend/login.html não encontrado.", status_code=404)

@router.get("/logout")
async def logout():
    """Limpa o cookie e volta para o login"""
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

# Rotas de integração (Mantidas conforme seu padrão)
@router.get("/integracoes/{service}", response_class=HTMLResponse)
async def render_service(request: Request, service: str, db: Session = Depends(get_db)):
    try:
        current_user = await get_current_user(request, db)
        template_map = {
            "sams": "services/sams_club.html",
            "sodimac": "services/sodimac.html",
            "outras": "services/outras.html"
        }
        return templates.TemplateResponse(template_map.get(service, "services/outras.html"), {
            "request": request, 
            "user": current_user
        })
    except Exception:
        return RedirectResponse(url="/login")