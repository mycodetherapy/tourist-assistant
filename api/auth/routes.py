"""REST: регистрация, вход, Google OAuth."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from fastapi.responses import RedirectResponse
from starlette import status

from api.auth.google_oauth import google_oauth_configured, google_redirect_uri, oauth
from api.auth.service import (
    AuthError,
    login_or_link_google,
    login_user,
    register_user,
    user_from_token_payload,
)
from api.deps import get_current_user
from api.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from db.users import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_response(user: User, token: str) -> AuthResponse:
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(id=user.id, email=user.email),
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest) -> AuthResponse:
    try:
        user, token = register_user(email=payload.email, password=payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _auth_response(user, token)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    try:
        user, token = login_user(email=payload.email, password=payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _auth_response(user, token)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=user.id, email=user.email)


@router.post("/logout", status_code=204, response_class=Response)
def logout() -> Response:
    """JWT stateless — клиент удаляет токен."""
    return Response(status_code=204)


@router.get("/google")
async def google_login(request: Request) -> RedirectResponse:
    if not google_oauth_configured():
        raise HTTPException(status_code=503, detail="Google OAuth не настроен")
    redirect_uri = google_redirect_uri()
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request) -> RedirectResponse:
    if not google_oauth_configured():
        raise HTTPException(status_code=503, detail="Google OAuth не настроен")
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ошибка авторизации Google",
        ) from exc
    userinfo = token.get("userinfo")
    if not userinfo:
        raise HTTPException(status_code=400, detail="Нет данных профиля Google")
    google_sub = str(userinfo.get("sub", ""))
    email = str(userinfo.get("email", ""))
    if not google_sub or not email:
        raise HTTPException(status_code=400, detail="Google не вернул email")
    try:
        user, access_token = login_or_link_google(google_sub=google_sub, email=email)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    frontend = request.query_params.get("frontend", "http://localhost:5173")
    url = f"{frontend.rstrip('/')}/auth/callback?token={access_token}"
    return RedirectResponse(url=url, status_code=302)
