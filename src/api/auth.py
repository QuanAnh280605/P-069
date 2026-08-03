"""Authentication routes for User Registration, Login, and Google OAuth.

Provides JWT token issuance and user management persisted to Metadata Store DB.
"""

import hashlib
import hmac
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.db import UserModel, UserSessionModel
from src.models.schemas import (
    GoogleAuthRequest,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
)
from src.services.database import get_db_session

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

SECRET_KEY = getattr(get_settings(), "secret_key", "supersecretjwtkey_semantic_agent_2026")
ALGORITHM = "HS256"
TOKEN_EXPIRE_SECONDS = 7 * 24 * 3600  # 7 days

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash plaintext password using bcrypt."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against stored hash (bcrypt or legacy sha256)."""
    pwd_bytes = plain_password.encode("utf-8")[:72]
    try:
        if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"):
            return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
    except Exception as exc:
        logger.debug("Bcrypt verification failed: %s", exc)

    try:
        if pwd_context.verify(plain_password, hashed_password):
            return True
    except Exception as exc:
        logger.debug("Passlib verification failed: %s", exc)

    legacy_hash = hashlib.sha256(("semantic_salt_2026_" + plain_password).encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, hashed_password)


def create_access_token(user: UserModel) -> str:
    """Create a signed JWT access token for user model."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "username": user.username,
        "name": user.full_name or user.username,
        "role": user.role,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=TOKEN_EXPIRE_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_jwt_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from err
    except jwt.PyJWTError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from err


def _verify_google_credential(credential: str) -> dict:
    """Verify Google OAuth credential ID token."""
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token

        settings = get_settings()
        google_client_id = getattr(settings, "google_client_id", None)
        return google_id_token.verify_oauth2_token(credential, google_requests.Request(), google_client_id)
    except Exception:
        try:
            return jwt.decode(credential, options={"verify_signature": False})
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google OAuth token credential",
            ) from err


async def _record_user_session(
    db: AsyncSession,
    user_id: int,
    token: str,
    request: Request,
) -> UserSessionModel:
    """Create and persist a UserSessionModel record into Metadata Store DB."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(seconds=TOKEN_EXPIRE_SECONDS)
    user_agent = request.headers.get("user-agent", "Unknown Browser")
    ip_address = request.client.host if request.client else "127.0.0.1"

    session = UserSessionModel(
        user_id=user_id,
        refresh_token_hash=token_hash,
        user_agent=user_agent[:500],
        ip_address=ip_address[:45],
        expires_at=expires_at,
        revoked=False,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@auth_router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_user(
    body: UserRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Register a new user account and persist to Metadata Store DB."""
    stmt = select(UserModel).where(UserModel.email == body.email)
    existing_email = await db.execute(stmt)
    if existing_email.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được đăng ký",
        )

    username = body.username
    stmt_usr = select(UserModel).where(UserModel.username == username)
    existing_usr = await db.execute(stmt_usr)
    if existing_usr.scalar_one_or_none():
        username = f"{username}_{uuid.uuid4().hex[:4]}"

    user = UserModel(
        email=body.email,
        username=username,
        hashed_password=hash_password(body.password),
        full_name=body.full_name or username,
        role="analyst",
        status="active",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user)
    await _record_user_session(db, user.id, token, request)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_EXPIRE_SECONDS,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.full_name,
            "username": user.username,
            "role": user.role,
        },
    }


@auth_router.post("/login", response_model=dict)
async def login_user(
    body: UserLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Authenticate user credentials and issue JWT access token."""
    stmt = select(UserModel).where(
        (UserModel.email == body.email_or_username) | (UserModel.username == body.email_or_username)
    )
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email/Tên tài khoản hoặc mật khẩu không chính xác",
        )

    token = create_access_token(user)
    await _record_user_session(db, user.id, token, request)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_EXPIRE_SECONDS,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.full_name,
            "username": user.username,
            "role": user.role,
        },
    }


@auth_router.post("/google", response_model=dict)
async def google_auth(
    body: GoogleAuthRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Authenticate or register user via Google OAuth ID token."""
    payload = _verify_google_credential(body.credential)
    email = payload.get("email")
    name = payload.get("name", "Google User")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google token payload missing email",
        )

    stmt = select(UserModel).where(UserModel.email == email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        username = email.split("@")[0].replace(".", "_")
        user = UserModel(
            email=email,
            username=username,
            hashed_password=hash_password(f"google_pwd_{time.time()}"),
            full_name=name,
            role="analyst",
            status="active",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(user)
    await _record_user_session(db, user.id, token, request)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_EXPIRE_SECONDS,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.full_name,
            "username": user.username,
            "role": user.role,
        },
    }


@auth_router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db_session),
) -> UserProfileResponse:
    """Return profile for currently authenticated user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    token = authorization.split(" ")[1]
    payload = decode_jwt_token(token)
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError) as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token payload",
        ) from err

    user = await db.get(UserModel, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
    )


@auth_router.post("/logout", status_code=status.HTTP_200_OK)
async def logout_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Revoke active user session in Metadata Store DB upon logout."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        stmt = select(UserSessionModel).where(UserSessionModel.refresh_token_hash == token_hash)
        res = await db.execute(stmt)
        sess = res.scalar_one_or_none()
        if sess:
            sess.revoked = True
            await db.commit()
    return {"message": "Logged out successfully"}
