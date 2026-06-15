from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from database import create_db
from routers import auth, dashboard

app = FastAPI(title="Sistema Financeiro")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def on_startup():
    create_db()
