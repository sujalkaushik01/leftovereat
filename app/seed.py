from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .auth import hash_password
from .config import now_local
from .models import Listing, User


def _ensure_user(db: Session, email: str, password: str, role: str, org: str, address: str = "", status: str = "verified") -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=role,
        org_name=org,
        address=address,
        verification_status=status,
    )
    db.add(user)
    db.commit()
    return user


def seed(db: Session) -> None:
    _ensure_user(db, config.ADMIN_EMAIL, config.ADMIN_PASSWORD, "admin", "LeftoverEat Admin")
    if not config.SEED_DEMO:
        return

    hotel = _ensure_user(db, "hotel@demo.test", "demo12345", "hotel", "Hotel Saffron Court", "12 Connaught Place, New Delhi")
    _ensure_user(db, "customer@demo.test", "demo12345", "customer", "Demo Customer")
    _ensure_user(db, "ngo@demo.test", "demo12345", "ngo", "Roti Bank Delhi", "Karol Bagh, New Delhi", "verified")
    _ensure_user(db, "shelter@demo.test", "demo12345", "shelter", "Paws & Hooves Shelter", "Dwarka, New Delhi", "verified")
    _ensure_user(db, "pending-ngo@demo.test", "demo12345", "ngo", "New Hope Kitchen", "Rohini, New Delhi", "pending")

    if db.scalar(select(Listing.id).where(Listing.hotel_id == hotel.id)):
        return
    now = now_local()
    demos = [
        ("Veg biryani trays", "Fresh from the evening buffet, sealed trays.", "deal", 9900, 12, "hot"),
        ("Dal makhani and rice", "Whole-meal portions, packed hot.", "give", None, 30, "hot"),
        ("Vegetable peelings and rice scraps", "Plain, unseasoned; suitable for cattle and dogs.", "shelter", None, 20, "ambient"),
    ]
    for title, desc, stream, price, qty, temp in demos:
        db.add(
            Listing(
                hotel_id=hotel.id, title=title, description=desc, stream=stream,
                price_cents=price, quantity=qty, remaining=qty,
                pickup_start=now, pickup_end=now + timedelta(hours=4),
                address=hotel.address, safe_until=now + timedelta(hours=5), temp_note=temp,
            )
        )
    db.commit()
