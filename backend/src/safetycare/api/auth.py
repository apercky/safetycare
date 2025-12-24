"""Authentication API endpoints."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status

from safetycare.config import Settings
from safetycare.core.dependencies import get_password_manager, get_settings
from safetycare.core.security import PasswordManager, create_access_token, verify_access_token
from safetycare.models.auth import (
    InitialPasswordResponse,
    LoginRequest,
    LoginResponse,
    SetupStatusResponse,
    TokenVerifyResponse,
)

router = APIRouter()


@router.get("/setup-status", response_model=SetupStatusResponse)
async def get_setup_status(
    password_manager: Annotated[PasswordManager, Depends(get_password_manager)],
) -> SetupStatusResponse:
    """Check if initial setup is required.

    Returns setup status including whether password exists and if
    first-run setup page should be shown.
    """
    is_initialized = password_manager.is_initialized()
    has_initial_password = password_manager.has_initial_password()

    return SetupStatusResponse(
        is_initialized=is_initialized,
        has_initial_password=has_initial_password,
        requires_setup=not is_initialized or has_initial_password,
    )


@router.get("/initial-password", response_model=InitialPasswordResponse)
async def get_initial_password(
    password_manager: Annotated[PasswordManager, Depends(get_password_manager)],
) -> InitialPasswordResponse:
    """Get initial password for first-run setup.

    Only available during initial setup. Returns the generated password
    that the user should save in their password manager.

    Raises:
        HTTPException: If initial password is not available
    """
    password = password_manager.get_initial_password()

    if password is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Password iniziale non disponibile. Il setup è già stato completato.",
        )

    return InitialPasswordResponse(
        password=password,
        message=(
            "Questa è la tua password di accesso. "
            "Salvala nel tuo password manager prima di continuare. "
            "Non sarà più visualizzabile dopo il primo accesso."
        ),
    )


@router.post("/acknowledge-password")
async def acknowledge_initial_password(
    password_manager: Annotated[PasswordManager, Depends(get_password_manager)],
) -> dict[str, str]:
    """Acknowledge that user has saved the initial password.

    Removes the plaintext password file after user confirmation.
    """
    if not password_manager.has_initial_password():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nessuna password iniziale da confermare.",
        )

    password_manager.clear_initial_password()

    return {"message": "Password iniziale confermata e rimossa dal sistema."}


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    response: Response,
    password_manager: Annotated[PasswordManager, Depends(get_password_manager)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    """Authenticate with password and receive session cookie.

    Args:
        request: Login credentials
        response: FastAPI response for setting cookie

    Returns:
        Login result

    Raises:
        HTTPException: If credentials are invalid
    """
    if not password_manager.is_initialized():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sistema non inizializzato. Completa il setup.",
        )

    if not password_manager.verify(request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password non valida.",
        )

    # Create JWT token
    token = create_access_token(
        data={"sub": "admin"},
        expires_delta=timedelta(hours=settings.jwt_expire_hours),
    )

    # Set HTTP-only cookie
    is_dev = settings.env == "development"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=not is_dev,  # HTTPS only in production
        samesite="lax" if is_dev else "strict",
        max_age=settings.jwt_expire_hours * 3600,
        path="/",
    )

    return LoginResponse(success=True, message="Accesso effettuato con successo.")


@router.post("/logout")
async def logout(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Log out and clear session cookie."""
    is_dev = settings.env == "development"
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=not is_dev,
        samesite="lax" if is_dev else "strict",
        path="/",
    )

    return {"message": "Logout effettuato con successo."}


@router.get("/verify", response_model=TokenVerifyResponse)
async def verify_token(
    access_token: Annotated[str | None, Cookie()] = None,
) -> TokenVerifyResponse:
    """Verify current session token.

    Checks if the current session cookie contains a valid token.
    """
    if not access_token:
        return TokenVerifyResponse(valid=False)

    payload = verify_access_token(access_token)

    if payload is None:
        return TokenVerifyResponse(valid=False)

    # Calculate remaining time
    import time

    exp = payload.get("exp", 0)
    remaining = max(0, exp - time.time())
    hours_remaining = remaining / 3600

    return TokenVerifyResponse(valid=True, expires_in_hours=hours_remaining)
