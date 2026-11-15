"""BBS door wrapper for the twclone Python client.

Runs the stock client.py unchanged, but signs the caller in with the name and
password the rlogin bridge (twdoor.py) passes in the environment, and creates
the captain on the first visit. Passwords are derived by the bridge, so callers
never see or type one.
"""
from __future__ import annotations

import getpass
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import client  # noqa: E402  (the stock TWClone client)
import door_ansi  # noqa: E402  (colour screens, hotkey prompts)

door_ansi.install(client)

_user = os.environ.pop("TWDOOR_USER", "")
_pass = os.environ.pop("TWDOOR_PASS", "")
_host = os.environ.get("TWDOOR_HOST", "127.0.0.1")
_port = os.environ.get("TWDOOR_PORT", "1234")
_login_used = False


def _door_getpass(prompt: str = "Password: ", stream=None) -> str:
    """First call is the login prompt; later ones (change password) are refused."""
    global _login_used
    if not _login_used and prompt.strip().lower().startswith("password"):
        _login_used = True
        return _pass
    print("Your TWClone password is looked after by the BBS, so it can't be changed here.")
    return ""


getpass.getpass = _door_getpass

_orig_authenticate = client.authenticate


def _door_authenticate(conn, username, password):
    # The server hangs up after a failed login, so try to create the captain
    # first; an existing name is refused (1105) and we then log in normally.
    created = client.register_account(conn, username, password, "")
    if created.get("status") == "ok" and conn.session_token:
        print(f"Welcome aboard, Captain {username}. Your ship is waiting.")
        return created
    return _orig_authenticate(conn, username, password)


client.authenticate = _door_authenticate


def run() -> int:
    if not _user or not _pass:
        print("This game must be started from the BBS.")
        return 2
    sys.argv = [os.path.join(HERE, "client.py"), "--host", _host, "--port", str(_port), "--user", _user]
    return client.main() or 0


if __name__ == "__main__":
    sys.exit(run())
