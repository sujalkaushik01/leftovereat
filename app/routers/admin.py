from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_role
from ..db import get_db
from ..models import CERTIFIED_ROLES, User
from ..templating import templates

router = APIRouter(prefix="/admin")


@router.get("")
def admin_home(request: Request, msg: str = "", user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    orgs = list(
        db.scalars(select(User).where(User.role.in_(CERTIFIED_ROLES)).order_by(User.created_at.desc()))
    )
    pending = [o for o in orgs if o.verification_status == "pending"]
    reviewed = [o for o in orgs if o.verification_status != "pending"]
    return templates.TemplateResponse(
        request, "admin.html", {"user": user, "pending": pending, "reviewed": reviewed, "msg": msg}
    )


@router.post("/users/{user_id}/review")
def review(
    user_id: int,
    decision: str = Form(...),
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target or target.role not in CERTIFIED_ROLES or decision not in ("verified", "rejected"):
        return RedirectResponse("/admin?msg=" + quote_plus("Could not update that profile"), status_code=303)
    target.verification_status = decision
    db.commit()
    word = "approved" if decision == "verified" else "rejected"
    return RedirectResponse("/admin?msg=" + quote_plus(f"{target.org_name} {word}"), status_code=303)
