from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import Base, SessionLocal, engine, get_db
from .models import User
from .routers import admin, auth_routes, browse, hotel
from .seed import seed
from .services import meals_reserved
from .templating import BASE_DIR, templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="LeftoverEat", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(auth_routes.router)
app.include_router(hotel.router)
app.include_router(browse.router)
app.include_router(admin.router)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/")
def home(request: Request, msg: str = "", user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "home.html", {"user": user, "msg": msg, "meals": meals_reserved(db)}
    )
