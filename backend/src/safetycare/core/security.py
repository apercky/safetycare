"""Security utilities for password management and JWT tokens."""

import secrets
import string
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import bcrypt
from jose import JWTError, jwt

from safetycare.config import get_settings


def generate_secure_password(length: int = 18) -> str:
    """Generate a cryptographically secure password.

    Args:
        length: Password length (minimum 12, default 18)

    Returns:
        Secure password with uppercase, lowercase, digits, and special characters
    """
    if length < 12:
        length = 12

    # Character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    # Using a subset of special characters that are safe for most systems
    special = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    # Ensure at least one character from each category
    password_chars = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special),
    ]

    # Fill remaining length with random characters from all categories
    all_chars = uppercase + lowercase + digits + special
    remaining_length = length - len(password_chars)
    password_chars.extend(secrets.choice(all_chars) for _ in range(remaining_length))

    # Shuffle to avoid predictable pattern
    secrets.SystemRandom().shuffle(password_chars)

    return "".join(password_chars)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored password hash

    Returns:
        True if password matches, False otherwise
    """
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token.

    Args:
        data: Payload data to encode
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token
    """
    settings = get_settings()
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(hours=settings.jwt_expire_hours)

    to_encode.update({"exp": expire, "iat": datetime.now(UTC)})

    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_access_token(token: str) -> dict[str, Any] | None:
    """Verify and decode a JWT access token.

    Args:
        token: JWT token to verify

    Returns:
        Decoded payload if valid, None otherwise
    """
    settings = get_settings()

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


class PasswordManager:
    """Manages initial password generation and storage."""

    def __init__(self, auth_dir: Path) -> None:
        """Initialize password manager.

        Args:
            auth_dir: Directory for storing authentication data
        """
        self.auth_dir = auth_dir
        self.hash_file = auth_dir / "password.hash"
        self.initial_password_file = auth_dir / "initial_password.txt"

    def is_initialized(self) -> bool:
        """Check if password has been set up."""
        return self.hash_file.exists()

    def has_initial_password(self) -> bool:
        """Check if initial password file exists (first run)."""
        return self.initial_password_file.exists()

    def initialize(self) -> str:
        """Generate and store initial password.

        Returns:
            Generated plain text password (for display to user)
        """
        if self.is_initialized():
            raise RuntimeError("Password already initialized")

        # Generate secure password
        password = generate_secure_password(18)

        # Store hash
        password_hash = hash_password(password)
        self.hash_file.write_text(password_hash)

        # Store plain text temporarily for first-run display
        self.initial_password_file.write_text(password)

        return password

    def get_initial_password(self) -> str | None:
        """Get initial password for first-run display.

        Returns:
            Plain text password if exists, None otherwise
        """
        if not self.has_initial_password():
            return None
        return self.initial_password_file.read_text().strip()

    def clear_initial_password(self) -> None:
        """Remove initial password file after user acknowledges it."""
        if self.initial_password_file.exists():
            self.initial_password_file.unlink()

    def verify(self, password: str) -> bool:
        """Verify password against stored hash.

        Args:
            password: Password to verify

        Returns:
            True if valid, False otherwise
        """
        if not self.is_initialized():
            return False

        stored_hash = self.hash_file.read_text().strip()
        return verify_password(password, stored_hash)


def get_or_create_jwt_secret() -> str:
    """Get or create JWT secret key.

    Returns:
        JWT secret key
    """
    settings = get_settings()

    # If secret is provided in environment, use it
    if settings.jwt_secret:
        return settings.jwt_secret

    # Otherwise, generate and store one
    secret_file = settings.auth_dir / "jwt_secret.key"

    if secret_file.exists():
        return secret_file.read_text().strip()

    # Generate new secret
    secret = secrets.token_urlsafe(64)
    secret_file.write_text(secret)

    return secret
