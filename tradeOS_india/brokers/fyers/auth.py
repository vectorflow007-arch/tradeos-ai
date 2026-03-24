"""
TradeOS India — Fyers OAuth2 authentication.

Runs a local FastAPI callback server on :8182, opens a QWebEngineView
dialog for login, captures the auth_code, exchanges it for an
access_token, and stores it securely in the OS keyring.
"""

import asyncio
import threading
from typing import Optional

import httpx
import uvicorn
from fastapi import FastAPI
from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout

from config.settings import get_settings
from utils.keychain import get_secret, set_secret, delete_secret
from utils.logger import get_logger

log = get_logger("brokers.fyers.auth")

# ─── Keyring keys ────────────────────────────────────────────────
_KEYRING_TOKEN = "fyers_token"
_KEYRING_APP_ID = "fyers_app_id"
_KEYRING_SECRET = "fyers_secret_key"


# ═════════════════════════════════════════════════════════════════
# Local OAuth callback server
# ═════════════════════════════════════════════════════════════════

class _CallbackServer:
    """Embedded FastAPI server that captures the OAuth auth_code."""

    def __init__(self) -> None:
        self.app = FastAPI()
        self.auth_code: Optional[str] = None
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Register the /callback route."""

        @self.app.get("/callback")
        async def callback(auth_code: str = "", s: str = "ok") -> str:
            """Capture the auth_code from Fyers redirect."""
            self.auth_code = auth_code
            log.info(
                f"OAuth callback received: code={auth_code[:4]}***"
                if auth_code else "OAuth callback: no code"
            )
            return (
                "<html><body style='background:#1e1e1e;color:#fff;"
                "font-family:sans-serif;text-align:center;padding-top:80px'>"
                "<h2>Login Successful</h2>"
                "<p>You can close this window and return to TradeOS India.</p>"
                "</body></html>"
            )

    def start(self, host: str = "127.0.0.1", port: int = 8182) -> None:
        """Start the callback server in a background thread."""
        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="error",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(
            target=self._server.run,
            daemon=True,
            name="fyers-oauth-server",
        )
        self._thread.start()
        log.info(f"OAuth callback server started on {host}:{port}")

    def stop(self) -> None:
        """Signal the server to shut down."""
        if self._server:
            self._server.should_exit = True
            log.info("OAuth callback server stopped")


# ═════════════════════════════════════════════════════════════════
# Fyers Auth
# ═════════════════════════════════════════════════════════════════

class FyersAuth(QObject):
    """Handles the full Fyers OAuth2 flow inside the app.

    Signals:
        auth_complete: Emitted with the access_token string on success.
        auth_failed: Emitted with error message on failure.
    """

    auth_complete = Signal(str)
    auth_failed = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._callback_server = _CallbackServer()
        self._app_id: str = ""
        self._secret_key: str = ""
        self._redirect_uri: str = "http://127.0.0.1:8182/callback"

    # ─── Credential management ───────────────────────────────────

    def load_credentials(self) -> bool:
        """Load app_id and secret_key from keyring.

        Returns:
            True if both credentials are found.
        """
        self._app_id = get_secret(_KEYRING_APP_ID) or ""
        self._secret_key = get_secret(_KEYRING_SECRET) or ""
        if self._app_id and self._secret_key:
            log.info(
                f"Fyers credentials loaded: app_id={self._app_id[:4]}***"
            )
            return True
        log.warning("Fyers credentials not found in keyring")
        return False

    def save_credentials(self, app_id: str, secret_key: str) -> None:
        """Save app_id and secret_key to keyring.

        Args:
            app_id: Fyers app ID.
            secret_key: Fyers secret key.
        """
        self._app_id = app_id
        self._secret_key = secret_key
        set_secret(_KEYRING_APP_ID, app_id)
        set_secret(_KEYRING_SECRET, secret_key)
        log.info("Fyers credentials saved to keyring")

    # ─── OAuth URL ───────────────────────────────────────────────

    def get_auth_url(self) -> str:
        """Build the Fyers OAuth authorization URL.

        Returns:
            The full authorization URL to load in the browser.
        """
        base = "https://api-t1.fyers.in/api/v3/generate-authcode"
        params = (
            f"?client_id={self._app_id}"
            f"&redirect_uri={self._redirect_uri}"
            f"&response_type=code"
            f"&state=tradeos"
        )
        url = base + params
        log.debug(f"Auth URL generated: {url[:60]}...")
        return url

    # ─── Callback server ────────────────────────────────────────

    def start_callback_server(self) -> None:
        """Start the local FastAPI callback server."""
        self._callback_server.start()

    def stop_callback_server(self) -> None:
        """Stop the local callback server."""
        self._callback_server.stop()

    def get_captured_code(self) -> Optional[str]:
        """Return the auth_code captured by the callback server."""
        return self._callback_server.auth_code

    # ─── Token exchange ──────────────────────────────────────────

    async def exchange_token(self, auth_code: str) -> Optional[str]:
        """Exchange the auth_code for an access_token.

        Args:
            auth_code: The authorization code from the OAuth callback.

        Returns:
            The access_token string, or None on failure.
        """
        url = "https://api-t1.fyers.in/api/v3/validate-authcode"
        payload = {
            "grant_type": "authorization_code",
            "appIdHash": self._app_id,
            "code": auth_code,
            "secret_key": self._secret_key,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                data = resp.json()

            if data.get("s") == "ok" and data.get("access_token"):
                token = data["access_token"]
                log.info("Token exchange successful")
                return token

            error_msg = data.get("message", "Unknown error during token exchange")
            log.error(f"Token exchange failed: {error_msg}")
            return None

        except Exception as exc:
            log.error(f"Token exchange error: {exc}")
            return None

    # ─── Token storage ───────────────────────────────────────────

    def save_token(self, token: str) -> None:
        """Save the access_token to the OS keyring.

        Args:
            token: The Fyers access token.
        """
        set_secret(_KEYRING_TOKEN, token)
        log.info("Fyers token saved to keyring")

    def load_token(self) -> Optional[str]:
        """Load the access_token from the OS keyring.

        Returns:
            The token string, or None if not found.
        """
        token = get_secret(_KEYRING_TOKEN)
        if token:
            log.debug(f"Fyers token loaded: {token[:4]}***")
        return token

    def clear_token(self) -> None:
        """Delete the access_token from the OS keyring."""
        delete_secret(_KEYRING_TOKEN)
        log.info("Fyers token cleared from keyring")

    # ─── Token validation ────────────────────────────────────────

    async def validate_token(self, token: Optional[str] = None) -> bool:
        """Validate the token by calling the Fyers profile API.

        Args:
            token: Token to validate. Uses stored token if None.

        Returns:
            True if the token is valid.
        """
        token = token or self.load_token()
        if not token:
            return False

        url = "https://api-t1.fyers.in/api/v3/profile"
        headers = {"Authorization": f"{self._app_id}:{token}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                data = resp.json()

            if data.get("s") == "ok":
                log.info("Fyers token validated successfully")
                return True

            log.warning(f"Token validation failed: {data.get('message', '?')}")
            return False

        except Exception as exc:
            log.error(f"Token validation error: {exc}")
            return False

    # ─── Auth dialog (QWebEngineView) ────────────────────────────

    def open_auth_dialog(self, parent=None) -> Optional[QDialog]:
        """Open a QDialog with QWebEngineView for OAuth login.

        Args:
            parent: Parent QWidget for the dialog.

        Returns:
            The QDialog instance (caller should exec()).
        """
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            log.error(
                "QWebEngineView not available. "
                "Install PySide6-WebEngine."
            )
            self.auth_failed.emit("QWebEngineView not available")
            return None

        dialog = QDialog(parent)
        dialog.setWindowTitle("Fyers Login - TradeOS India")
        dialog.setFixedSize(800, 650)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        web_view = QWebEngineView()
        layout.addWidget(web_view)

        auth_url = self.get_auth_url()
        web_view.load(QUrl(auth_url))

        # Monitor URL changes for callback redirect
        def _on_url_changed(url: QUrl) -> None:
            url_str = url.toString()
            if "/callback" in url_str and "auth_code=" in url_str:
                log.info("Auth code detected in redirect URL")
                dialog.accept()

        web_view.urlChanged.connect(_on_url_changed)

        return dialog

    # ─── Full auth flow ──────────────────────────────────────────

    async def run_full_auth(self) -> Optional[str]:
        """Execute the complete auth flow programmatically.

        Starts callback server, waits for auth_code, exchanges token.
        Note: The dialog must be opened separately by the UI layer.

        Returns:
            The access_token, or None on failure.
        """
        code = self.get_captured_code()
        if not code:
            self.auth_failed.emit("No auth code received")
            return None

        token = await self.exchange_token(code)
        if token:
            self.save_token(token)
            self.auth_complete.emit(token)
            return token

        self.auth_failed.emit("Token exchange failed")
        return None


__all__ = ["FyersAuth"]
