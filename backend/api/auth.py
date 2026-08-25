from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from core.database import get_db
from core.security import (
    create_access_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)
from models.user import APIKey, User
from schemas.auth import APIKeyCreate, APIKeyOut, Token, UserCreate, UserLogin, UserOut
from services.organization_service import provision_default_workspace

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.flush()
    provision_default_workspace(db, user)
    db.commit()
    db.refresh(user)
    return Token(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return Token(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/api-keys", response_model=APIKeyOut, status_code=status.HTTP_201_CREATED)
def create_api_key(payload: APIKeyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    raw_key = generate_api_key()
    api_key = APIKey(
        user_id=current_user.id,
        name=payload.name,
        hashed_key=hash_api_key(raw_key),
        prefix=raw_key[:12],
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return APIKeyOut(id=api_key.id, name=api_key.name, key=raw_key, prefix=api_key.prefix)


@router.get("/api-keys", response_model=list[APIKeyOut])
def list_api_keys(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    keys = db.query(APIKey).filter(APIKey.user_id == current_user.id).all()
    return [APIKeyOut(id=k.id, name=k.name, key=None, prefix=k.prefix) for k in keys]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(key_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    api_key = db.query(APIKey).filter(APIKey.id == key_id, APIKey.user_id == current_user.id).first()
    if not api_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    db.delete(api_key)
    db.commit()
