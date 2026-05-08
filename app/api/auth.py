from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select
from app.database import get_session
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.core.security import create_access_token, create_refresh_token, decode_refresh_token, hash_password, token_hash, verify_password
from app.models.domain import DriverProfile, RefreshToken, Restaurant, Shelter, User, UserRole
from app.schemas.common import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenPair, UserRead

router = APIRouter(prefix='/auth', tags=['auth'])
settings = get_settings()


def store_refresh_token(session: Session, user: User, refresh_token: str) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    session.add(RefreshToken(user_id=user.id, token_hash=token_hash(refresh_token), expires_at=expires_at))
    session.commit()


@router.post('/register', response_model=UserRead, status_code=201)
def register(payload: RegisterRequest, request: Request, session: Session = Depends(get_session)):
    rate_limit(request, 'register')
    existing = session.exec(select(User).where((User.email == payload.email) | (User.username == payload.username))).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='email or username already exists')
    if payload.role == UserRole.admin:
        admin_exists = session.exec(select(User).where(User.role == UserRole.admin)).first()
        if admin_exists:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='admin registration is closed')
    user = User(email=payload.email, username=payload.username, password_hash=hash_password(payload.password), role=payload.role)
    session.add(user)
    session.commit()
    session.refresh(user)
    if payload.role == UserRole.restaurant_manager:
        session.add(Restaurant(owner_id=user.id, name=f'{user.username} Restaurant', address='Pending verification', lat=43.238949, lng=76.889709))
    elif payload.role == UserRole.shelter_coordinator:
        session.add(Shelter(coordinator_id=user.id, name=f'{user.username} Shelter', lat=43.238949, lng=76.889709))
    elif payload.role == UserRole.driver:
        session.add(DriverProfile(user_id=user.id))
    session.commit()
    return user


@router.post('/login', response_model=TokenPair)
def login(payload: LoginRequest, request: Request, session: Session = Depends(get_session)):
    rate_limit(request, 'login')
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid credentials')
    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id, user.role.value)
    store_refresh_token(session, user, refresh)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post('/refresh', response_model=TokenPair)
def refresh(payload: RefreshRequest, session: Session = Depends(get_session)):
    try:
        decoded = decode_refresh_token(payload.refresh_token)
        user_id = int(decoded['sub'])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid refresh token') from None
    stored = session.exec(select(RefreshToken).where(RefreshToken.token_hash == token_hash(payload.refresh_token))).first()
    now = datetime.now(timezone.utc)

    if stored and stored.expires_at.tzinfo is None:
       stored.expires_at = stored.expires_at.replace(tzinfo=timezone.utc)

    if not stored or stored.revoked or stored.expires_at < now:
      raise HTTPException(status_code=401, detail="invalid refresh token")
        
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='user not found')
    access = create_access_token(user.id, user.role.value)
    refresh_token = create_refresh_token(user.id, user.role.value)
    store_refresh_token(session, user, refresh_token)
    return TokenPair(access_token=access, refresh_token=refresh_token)


@router.post('/logout', status_code=204)
def logout(payload: LogoutRequest, session: Session = Depends(get_session)):
    stored = session.exec(select(RefreshToken).where(RefreshToken.token_hash == token_hash(payload.refresh_token))).first()
    if stored:
        stored.revoked = True
        session.add(stored)
        session.commit()
    return None
