from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from auth import criar_token, hash_senha, verificar_senha, get_usuario_atual
from database import get_session
from models import User

router = APIRouter()

from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader

# Cria um ambiente Jinja2 com cache desabilitado
env = Environment(
    loader=FileSystemLoader("templates"),
    cache_size=0  # desativa o cache
)

# Passa o ambiente personalizado para o Jinja2Templates
templates = Jinja2Templates(env=env)

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "erro": None})


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verificar_senha(password, user.password):
        return templates.TemplateResponse(
            "login.html", {"request": request, "erro": "Email ou senha incorretos."}
        )

    token = criar_token({"sub": str(user.id)})
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,
        samesite="lax",
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response
