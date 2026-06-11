"""Зависимости FastAPI."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.auth.jwt_tokens import decode_access_token
from api.auth.service import AuthError, user_from_token_payload
from db.users import User
from services.run_manager import RunManager
from services.trip_service import TripService

_bearer = HTTPBearer(auto_error=False)

_trip_service = TripService()
_run_manager = RunManager(_trip_service)


def get_trip_service() -> TripService:
    return _trip_service


def get_run_manager() -> RunManager:
    return _run_manager


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    try:
        payload = decode_access_token(credentials.credentials)
        return user_from_token_payload(payload)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Недействительный токен") from exc
