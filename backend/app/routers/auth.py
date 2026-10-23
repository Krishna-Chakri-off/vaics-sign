from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..security import verify_password, create_token, get_current_user, hash_password, require_roles

router = APIRouter()


@router.post("/auth/login", response_model=schemas.LoginOut, tags=["auth"])
def login(body: schemas.LoginIn, db: Session = Depends(get_db)):
    u = db.query(models.User).filter(models.User.email == body.email.lower()).first()
    if not u or not u.is_active or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": create_token(u.id), "user": u}


@router.get("/auth/me", response_model=schemas.UserOut, tags=["auth"])
def me(user=Depends(get_current_user)):
    return user


@router.get("/users", response_model=list[schemas.UserOut], tags=["users"])
def list_users(role: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(models.User).filter_by(organization_id=user.organization_id)
    if role:
        q = q.filter_by(role=role)
    return q.order_by(models.User.full_name).all()


@router.post("/users", response_model=schemas.UserOut, status_code=201, tags=["users"])
def create_user(body: schemas.UserCreate, db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    if db.query(models.User).filter_by(email=body.email.lower()).first():
        raise HTTPException(409, "Email already exists")
    u = models.User(email=body.email.lower(), full_name=body.full_name, role=body.role, is_approver=body.is_approver, title=body.title,
                    password_hash=hash_password(body.password), organization_id=user.organization_id)
    db.add(u); db.commit()
    return u


@router.patch("/users/{uid}", response_model=schemas.UserOut, tags=["users"])
def update_user(uid: int, body: schemas.UserUpdate, db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    u = db.get(models.User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    if pw := data.pop("password", None):
        u.password_hash = hash_password(pw)
    for k, v in data.items():
        setattr(u, k, v)
    db.commit()
    return u
