from datetime import timedelta

from app.config import now_local

PW = "password123"


def register(c, role, email, org):
    r = c.post("/register", data={"role": role, "email": email, "password": PW, "org_name": org, "address": "1 Test Road"})
    assert r.status_code == 303, r.text
    return r


def login_admin(c):
    r = c.post("/login", data={"email": "admin@test.local", "password": "adminpass123"})
    assert r.status_code == 303


def dt(offset_hours):
    return (now_local() + timedelta(hours=offset_hours)).strftime("%Y-%m-%dT%H:%M")


def post_listing(hotel, stream, qty=5, price="50"):
    data = {
        "title": f"{stream} food", "description": "", "stream": stream, "price": price if stream == "deal" else "",
        "quantity": qty, "pickup_start": dt(-1), "pickup_end": dt(3), "safe_until": dt(4), "temp_note": "hot",
        "address": "",
    }
    r = hotel.post("/hotel/listings", data=data)
    assert r.status_code == 303
    assert "msg=" in r.headers["location"], r.headers["location"]


def verify(admin, user_email):
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == user_email))
    r = admin.post(f"/admin/users/{uid}/review", data={"decision": "verified"})
    assert r.status_code == 303


def test_three_claim_paths(client_factory):
    hotel, cust, ngo, shelter, admin = (client_factory() for _ in range(5))
    register(hotel, "hotel", "h@t.test", "Hotel A")
    register(cust, "customer", "c@t.test", "Cust")
    register(ngo, "ngo", "n@t.test", "NGO A")
    register(shelter, "shelter", "s@t.test", "Shelter A")
    login_admin(admin)
    for s in ("deal", "give", "shelter"):
        post_listing(hotel, s)

    # Customer sees only the deal.
    page = cust.get("/browse").text
    assert "deal food" in page and "give food" not in page and "shelter food" not in page
    # Pending NGO/shelter see the verification empty state, not inventory.
    assert "Verification pending" in ngo.get("/browse").text
    assert "give food" not in ngo.get("/browse").text
    assert "Verification pending" in shelter.get("/browse").text

    verify(admin, "n@t.test")
    verify(admin, "s@t.test")
    assert "give food" in ngo.get("/browse").text and "deal food" not in ngo.get("/browse").text
    assert "shelter food" in shelter.get("/browse").text

    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import Listing

    with SessionLocal() as db:
        ids = {l.stream: l.id for l in db.scalars(select(Listing))}
    for client, stream in ((cust, "deal"), (ngo, "give"), (shelter, "shelter")):
        r = client.post(f"/browse/claim/{ids[stream]}", data={"qty": 2})
        assert "msg=" in r.headers["location"]
    with SessionLocal() as db:
        assert all(db.get(Listing, i).remaining == 3 for i in ids.values())


def test_wrong_stream_and_pending_cannot_claim(client_factory):
    hotel, cust, ngo = (client_factory() for _ in range(3))
    register(hotel, "hotel", "h@t.test", "Hotel A")
    register(cust, "customer", "c@t.test", "Cust")
    register(ngo, "ngo", "n@t.test", "NGO A")
    post_listing(hotel, "give")
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import Listing

    with SessionLocal() as db:
        lid = db.scalar(select(Listing.id))
    assert "error=" in cust.post(f"/browse/claim/{lid}", data={"qty": 1}).headers["location"]
    assert "error=" in ngo.post(f"/browse/claim/{lid}", data={"qty": 1}).headers["location"]  # still pending


def test_cannot_overclaim_and_cancel_restores(client_factory):
    hotel, cust = client_factory(), client_factory()
    register(hotel, "hotel", "h@t.test", "Hotel A")
    register(cust, "customer", "c@t.test", "Cust")
    post_listing(hotel, "deal", qty=3)
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import Claim, Listing

    with SessionLocal() as db:
        lid = db.scalar(select(Listing.id))
    assert "error=" in cust.post(f"/browse/claim/{lid}", data={"qty": 4}).headers["location"]
    assert "msg=" in cust.post(f"/browse/claim/{lid}", data={"qty": 3}).headers["location"]
    assert "error=" in cust.post(f"/browse/claim/{lid}", data={"qty": 1}).headers["location"]
    with SessionLocal() as db:
        cid = db.scalar(select(Claim.id))
        assert db.get(Listing, lid).remaining == 0
    cust.post(f"/browse/claims/{cid}/cancel")
    with SessionLocal() as db:
        assert db.get(Listing, lid).remaining == 3


def test_role_gates(client_factory):
    cust, anon = client_factory(), client_factory()
    register(cust, "customer", "c@t.test", "Cust")
    assert anon.get("/hotel").status_code == 303
    assert cust.get("/hotel").status_code == 303
    assert cust.get("/admin").status_code == 303
    assert anon.get("/health").json() == {"status": "ok"}
