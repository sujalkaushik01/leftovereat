from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..auth import COOKIE_NAME, get_current_user, hash_password, make_session_token, verify_password
from ..db import get_db
from ..models import CERTIFIED_ROLES, User
from ..templating import templates

router = APIRouter()

REGISTERABLE = ("hotel", "customer", "ngo", "shelter")


def home_for(user: User) -> str:
    return {"hotel": "/hotel", "admin": "/admin"}.get(user.role, "/browse")


def _login_response(user: User) -> RedirectResponse:
    resp = RedirectResponse(home_for(user), status_code=303)
    resp.set_cookie(
        COOKIE_NAME, make_session_token(user.id), max_age=config.SESSION_MAX_AGE,
        httponly=True, samesite="lax", secure=config.COOKIE_SECURE,
    )
    return resp


@router.get("/register")
def register_form(request: Request, role: str = "customer", user: User | None = Depends(get_current_user)):
    if role not in REGISTERABLE:
        role = "customer"
    return templates.TemplateResponse(request, "register.html", {"user": user, "role": role, "form_error": "", "form": {}})


@router.post("/register")
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    org_name: str = Form(...),
    address: str = Form(""),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    org_name = org_name.strip()
    address = address.strip()
    form = {"email": email, "org_name": org_name, "address": address}

    def fail(msg: str):
        return templates.TemplateResponse(
            request, "register.html", {"user": None, "role": role, "form_error": msg, "form": form}, status_code=400
        )

    if role not in REGISTERABLE:
        return fail("Choose a valid account type.")
    if "@" not in email or len(email) > 255:
        return fail("Enter a valid email address.")
    if len(password) < 8:
        return fail("Use a password with at least 8 characters.")
    if not org_name:
        return fail("Enter your name or organisation.")
    if role in ("hotel", "ngo", "shelter") and not address:
        return fail("Enter your address so pickups can be arranged.")
    if db.scalar(select(User).where(User.email == email)):
        return fail("An account with that email already exists. Log in instead.")

    user = User(
        email=email,
        password_hash=hash_password(password),
        role=role,
        org_name=org_name,
        address=address,
        verification_status="pending" if role in CERTIFIED_ROLES else "verified",
    )
    db.add(user)
    db.commit()
    return _login_response(user)


@router.get("/login")
def login_form(request: Request, user: User | None = Depends(get_current_user)):
    return templates.TemplateResponse(request, "login.html", {"user": user, "form_error": "", "email": ""})


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request, "login.html",
            {"user": None, "form_error": "Email or password is incorrect.", "email": email}, status_code=400,
        )
    return _login_response(user)


@router.post("/logout")
def logout():
    resp = RedirectResponse("/?msg=" + quote_plus("You're logged out"), status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp
