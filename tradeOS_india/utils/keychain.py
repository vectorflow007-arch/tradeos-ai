"""
TradeOS India — OS keyring wrapper for secure credential storage.

All secrets (broker tokens, API keys) are stored via the OS keyring.
Never log or store credentials in plain text.
"""

from typing import Optional

import keyring

from utils.logger import get_logger

log = get_logger("utils.keychain")

# ─── Constants ───────────────────────────────────────────────────
SERVICE_NAME = "tradeOS"


def set_secret(key: str, value: str) -> bool:
    """Store a secret in the OS keyring.

    Args:
        key: Identifier for the secret (e.g. 'fyers_token').
        value: The secret value to store.

    Returns:
        True if stored successfully, False on error.
    """
    try:
        keyring.set_password(SERVICE_NAME, key, value)
        masked = value[:4] + "***" if len(value) > 4 else "***"
        log.info(f"Secret stored: {key} ({masked})")
        return True
    except Exception as exc:
        log.error(f"Failed to store secret '{key}': {exc}")
        return False


def get_secret(key: str) -> Optional[str]:
    """Retrieve a secret from the OS keyring.

    Args:
        key: Identifier for the secret.

    Returns:
        The secret string, or None if not found or on error.
    """
    try:
        value = keyring.get_password(SERVICE_NAME, key)
        if value is None:
            log.debug(f"Secret not found: {key}")
        return value
    except Exception as exc:
        log.error(f"Failed to retrieve secret '{key}': {exc}")
        return None


def delete_secret(key: str) -> bool:
    """Delete a secret from the OS keyring.

    Args:
        key: Identifier for the secret to delete.

    Returns:
        True if deleted successfully, False on error.
    """
    try:
        keyring.delete_password(SERVICE_NAME, key)
        log.info(f"Secret deleted: {key}")
        return True
    except keyring.errors.PasswordDeleteError:
        log.warning(f"Secret not found for deletion: {key}")
        return False
    except Exception as exc:
        log.error(f"Failed to delete secret '{key}': {exc}")
        return False


def has_secret(key: str) -> bool:
    """Check whether a secret exists in the keyring.

    Args:
        key: Identifier to check.

    Returns:
        True if the secret exists.
    """
    return get_secret(key) is not None


__all__ = [
    "set_secret",
    "get_secret",
    "delete_secret",
    "has_secret",
    "SERVICE_NAME",
]
