"""SEC-001 auth primitives: signed session cookies, login rate limiter, login page.

Stdlib only (hmac/hashlib/secrets) — no new dependencies. The session signing key
IS the access password: rotating the password invalidates all sessions (accepted
in specs/SEC-001/proposal.md).
"""

import hashlib
import hmac
import time

SESSION_COOKIE_NAME = "garsync_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600

LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 300

_LOGIN_PAGE_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="robots" content="noindex, nofollow" />
    <meta name="color-scheme" content="dark" />
    <title>Sign in</title>
    <style>
      :root {
        color-scheme: dark;
        --bg: #0f172a;
        --card: #1e293b;
        --line: #334155;
        --text: #f8fafc;
        --muted: #94a3b8;
        --accent: #60a5fa;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0; min-height: 100vh; min-height: 100dvh; padding: 1.5rem 1rem;
        display: flex; align-items: center; justify-content: center;
        background: var(--bg); color: var(--text);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 16px; line-height: 1.5; -webkit-font-smoothing: antialiased;
      }
      main {
        width: 100%; max-width: 22rem; padding: 1.75rem;
        background: var(--card); border: 1px solid var(--line);
        border-radius: 0.75rem; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.35);
      }
      h1 { margin: 0 0 0.25rem; font-size: 1.5rem; font-weight: 700; color: var(--accent); }
      .hint { margin: 0 0 1.25rem; color: var(--muted); font-size: 0.875rem; }
      label {
        display: block; margin-bottom: 0.375rem;
        font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.05em; color: var(--muted);
      }
      input[type="password"] {
        width: 100%; padding: 0.625rem 0.75rem; font: inherit;
        color: var(--text); background: var(--bg);
        border: 1px solid var(--line); border-radius: 0.5rem; letter-spacing: 0.02em;
      }
      input[type="password"]:hover { border-color: var(--muted); }
      :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
      button {
        width: 100%; margin-top: 1rem; padding: 0.625rem 1rem;
        border: 0; border-radius: 0.5rem; font: inherit; font-weight: 600;
        background: #2563eb; color: var(--text); cursor: pointer;
      }
      button:hover { background: #1d4ed8; }
      .error {
        margin: 0 0 1.25rem; padding: 0.625rem 0.75rem; font-size: 0.875rem;
        color: #fca5a5; background: rgb(127 29 29 / 0.28);
        border: 1px solid #7f1d1d; border-left-width: 4px; border-radius: 0.5rem;
      }
      .error:empty { display: none; }
      footer { margin-top: 1.25rem; color: var(--muted); font-size: 0.75rem; }
      @media (min-width: 40rem) { main { padding: 2rem; } }
    </style>
  </head>
  <body>
    <main>
      <h1>Sign in</h1>
      <p class="hint">This dashboard is private. Enter the access password to continue.</p>

      <div class="error" role="alert">{{ERROR}}</div>

      <form method="POST" action="/login">
        <label for="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          autocomplete="current-password"
          autocapitalize="off"
          spellcheck="false"
          maxlength="256"
          required
          autofocus
        />
        <button type="submit">Sign in</button>
      </form>

      <footer>Repeated failed attempts are temporarily blocked.</footer>
    </main>
  </body>
</html>
"""


def render_login_page(error: str = "") -> str:
    """Render the login page with the error banner filled (empty collapses it)."""
    return _LOGIN_PAGE_HTML.replace("{{ERROR}}", error)


def make_session_token(access_password: str, now: float | None = None) -> str:
    """Return '<expiry>.<hmac>' — signature keyed by the access password."""
    current = time.time() if now is None else now
    expiry = int(current + SESSION_TTL_SECONDS)
    payload = f"garsync-session|{expiry}"
    sig = hmac.new(access_password.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{expiry}.{sig}"


def verify_session_token(token: str | None, access_password: str, now: float | None = None) -> bool:
    """Constant-time token verification; False on tamper, bad format or expiry."""
    if not token or not access_password:
        return False
    parts = token.split(".", 1)
    if len(parts) != 2 or not parts[0].isdigit():
        return False
    expiry_str, provided_sig = parts
    expected = hmac.new(
        access_password.encode(),
        f"garsync-session|{expiry_str}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(provided_sig, expected):
        return False
    current = time.time() if now is None else now
    return int(expiry_str) > current


class LoginRateLimiter:
    """In-memory per-client-IP limiter for failed logins (single-process apps)."""

    def __init__(
        self, max_failures: int = LOGIN_MAX_FAILURES, window_seconds: int = LOGIN_WINDOW_SECONDS
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, list[float]] = {}

    def _purge(self, client_ip: str) -> list[float]:
        cutoff = time.time() - self.window_seconds
        recent = [t for t in self._failures.get(client_ip, []) if t > cutoff]
        self._failures[client_ip] = recent
        return recent

    def is_blocked(self, client_ip: str) -> bool:
        return len(self._purge(client_ip)) >= self.max_failures

    def record_failure(self, client_ip: str) -> None:
        self._purge(client_ip)
        self._failures[client_ip].append(time.time())

    def reset(self, client_ip: str) -> None:
        self._failures.pop(client_ip, None)
