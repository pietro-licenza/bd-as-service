"""
Web routes for serving HTML pages
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, FileResponse
import os
from fastapi.templating import Jinja2Templates
from app.core.config import settings

router = APIRouter(tags=["Web Pages"])

# Setup templates
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    return templates.TemplateResponse("home.html", {"request": request})


@router.get("/integracoes/sams", response_class=HTMLResponse)
async def sams_club(request: Request):
    """Sam's Club integration page"""
    return templates.TemplateResponse("services/sams_club.html", {"request": request})


@router.get("/integracoes/sodimac", response_class=HTMLResponse)
async def sodimac(request: Request):
    """Sodimac integration page"""
    return templates.TemplateResponse("services/sodimac.html", {"request": request})


@router.get("/integracoes/outras", response_class=HTMLResponse)
async def outras_integracoes(request: Request):
    """Other integrations page"""
    return templates.TemplateResponse("services/outras.html", {"request": request})

@router.get("/login", response_class=HTMLResponse)
async def login_page():
    # Caminho absoluto correto para o login.html na raiz do projeto
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    login_path = os.path.join(base_dir, "frontend", "login.html")
    return FileResponse(login_path, media_type="text/html")
