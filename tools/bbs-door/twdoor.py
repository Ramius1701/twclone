"""twclone rlogin door for any BBS that offers rlogin doors.

    python twdoor.py            run the door (settings in twdoor.json, made on first run)

For each rlogin caller it:
  * reads the rlogin handshake (client user, server user, terminal/speed),
  * starts the TWClone text client signed in as that caller (door_client.py),
  * echoes and edits the caller's typing a line at a time, and
  * turns the client's output into CR/LF text the caller's terminal can show.

The caller's TWClone password is an HMAC of their name with this door's secret,
so nobody types or sees one. rlogin has no password of its own, so only the
addresses in "allow" may connect.

It also starts the TWClone game server (server.exe) when it isn't already
listening, if "start_server" is on.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import socket
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "twdoor.json")

DEFAULTS = {
    "listen": "127.0.0.1:2341",
    "allow": ["127.0.0.1", "::1"],
    "server": "127.0.0.1:1234",
    "start_server": True,
    "server_exe": "bin/server.exe",
    "name_from": "server",       # which rlogin name is the caller: "server" (remote user) or "client"
    "columns": 80,
    "rows": 24,
    "charset": "cp437",          # what the caller's terminal gets: cp437 or utf-8
    "color": "auto",             # auto (by rlogin terminal type), on or off; colours are in door-theme.json
    "plain_terminals": ["dumb", "tty", "ascii", "unknown"],
    "hotkeys": True,             # menu prompts take a single key, no Enter
    "max_callers": 20,
    "idle_minutes": 30,
    "secret": "",
}

log = logging.getLogger("twdoor")

HOTKEY_MARK = "\x00HK\x00"  # door_ansi.py writes this before a menu prompt

# Characters the client prints that a CP437 terminal can't show well.
ASCII_SWAPS = {
    "→": "->", "←": "<-", "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", "•": "*", " ": " ",
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    if not cfg.get("secret"):
        cfg["secret"] = secrets.token_hex(32)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        log.info("wrote %s with a new door secret", CONFIG_PATH)
    return cfg


def split_hostport(value: str) -> tuple[str, int]:
    host, _, port = value.rpartition(":")
    return host.strip("[]") or "127.0.0.1", int(port)


def door_password(secret: str, name: str) -> str:
    return hmac.new(secret.encode(), name.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def clean_name(name: str) -> str:
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:40]


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def ensure_server(cfg: dict) -> None:
    host, port = split_hostport(cfg["server"])
    if port_open(host, port) or not cfg.get("start_server"):
        return
    exe = os.path.join(HERE, cfg["server_exe"])
    log.info("starting %s", exe)
    out = open(os.path.join(HERE, "server.log"), "ab")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([exe], cwd=HERE, stdin=subprocess.DEVNULL, stdout=out, stderr=out, creationflags=flags)


class Session:
    def __init__(self, cfg: dict, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.cfg = cfg
        self.reader = reader
        self.writer = writer
        self.charset = cfg["charset"]
        self.line = bytearray()
        self.last_cr = False
        self.hotkey = False
        self.out_tail = ""

    def to_terminal(self, text: str) -> bytes:
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        if self.charset.lower() in ("cp437", "ascii"):
            for k, v in ASCII_SWAPS.items():
                text = text.replace(k, v)
        return text.encode(self.charset, errors="replace")

    async def handshake(self) -> tuple[str, str, str] | None:
        # NUL, client user, NUL, server user, NUL, terminal/speed, NUL
        data = b""
        try:
            while data.count(b"\x00") < 4:
                chunk = await asyncio.wait_for(self.reader.read(512), timeout=15)
                if not chunk:
                    return None
                data += chunk
        except asyncio.TimeoutError:
            return None
        parts = data.split(b"\x00")
        if parts[0] != b"":
            return None
        client_user, server_user, term = (p.decode("latin-1") for p in parts[1:4])
        rest = b"\x00".join(parts[4:])
        self.writer.write(b"\x00")
        await self.writer.drain()
        self.pending = rest
        return client_user, server_user, term

    async def run(self) -> None:
        peer = self.writer.get_extra_info("peername")
        hs = await self.handshake()
        if not hs:
            log.info("%s: bad rlogin handshake", peer)
            return
        client_user, server_user, term = hs
        name = clean_name(server_user if self.cfg["name_from"] == "server" else client_user)
        if not name:
            self.writer.write(self.to_terminal("No caller name was sent.\n"))
            await self.writer.drain()
            return
        log.info("%s: %s connected (%s)", peer, name, term)

        ensure_server(self.cfg)
        host, port = split_hostport(self.cfg["server"])
        mode = str(self.cfg.get("color", "auto")).lower()
        term_name = term.split("/")[0].strip().lower()
        if mode == "auto":
            color = term_name not in [t.lower() for t in self.cfg.get("plain_terminals", [])]
        else:
            color = mode in ("on", "1", "true", "yes")
        env = dict(os.environ)
        env.update({
            "TWDOOR_COLOR": "1" if color else "0",
            "TWDOOR_USER": name,
            "TWDOOR_PASS": door_password(self.cfg["secret"], name),
            "TWDOOR_HOST": host,
            "TWDOOR_PORT": str(port),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
            "COLUMNS": str(self.cfg["columns"]),
            "LINES": str(self.cfg["rows"]),
        })
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        errlog = open(os.path.join(HERE, "client-errors.log"), "ab")
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-u", os.path.join(HERE, "client", "door_client.py"),
            cwd=os.path.join(HERE, "client"), env=env,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=errlog,
            creationflags=flags,
        )
        out_task = asyncio.create_task(self.pump_output(proc))
        in_task = asyncio.create_task(self.pump_input(proc))
        done, pending = await asyncio.wait({out_task, in_task}, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        await proc.wait()
        errlog.close()
        log.info("%s: %s left", peer, name)

    async def pump_output(self, proc) -> None:
        decoder_buf = b""
        while True:
            chunk = await proc.stdout.read(4096)
            if not chunk:
                break
            decoder_buf += chunk
            try:
                text = decoder_buf.decode("utf-8")
                decoder_buf = b""
            except UnicodeDecodeError as e:
                text = decoder_buf[: e.start].decode("utf-8")
                decoder_buf = decoder_buf[e.start:]
            text = self.take_hotkey_marks(self.out_tail + text)
            self.writer.write(self.to_terminal(text))
            await self.writer.drain()
        try:
            self.writer.write(self.to_terminal("\nReturning to the BBS...\n"))
            await self.writer.drain()
        except Exception:
            pass

    def take_hotkey_marks(self, text: str) -> str:
        """Strip the client's hotkey marker; remember that the next key is a hotkey."""
        self.out_tail = ""
        if HOTKEY_MARK in text:
            text = text.replace(HOTKEY_MARK, "")
            self.hotkey = bool(self.cfg.get("hotkeys", True))
        # a marker split across two reads: hold the partial start back
        for n in range(len(HOTKEY_MARK) - 1, 0, -1):
            if text.endswith(HOTKEY_MARK[:n]):
                self.out_tail = text[-n:]
                text = text[:-n]
                break
        return text

    async def pump_input(self, proc) -> None:
        idle = max(1, int(self.cfg["idle_minutes"])) * 60
        data = getattr(self, "pending", b"")
        while True:
            if data:
                await self.handle_keys(data, proc)
            try:
                data = await asyncio.wait_for(self.reader.read(1024), timeout=idle)
            except asyncio.TimeoutError:
                self.writer.write(self.to_terminal("\nIdle too long. Returning to the BBS.\n"))
                await self.writer.drain()
                return
            if not data:
                return

    async def handle_keys(self, data: bytes, proc) -> None:
        echo = bytearray()
        for b in data:
            if self.hotkey and not self.line and (32 < b < 127 or b in (13, 10)):
                if b == 10 and self.last_cr:
                    self.last_cr = False
                    continue
                # one key answers a menu prompt
                self.hotkey = False
                self.last_cr = b == 13
                key = "" if b in (13, 10) else chr(b)
                self.writer.write(bytes(echo) + key.encode() + b"\r\n")
                echo.clear()
                await self.writer.drain()
                if proc.stdin and not proc.stdin.is_closing():
                    proc.stdin.write((key + "\n").encode("utf-8"))
                    await proc.stdin.drain()
                continue
            if b in (13, 10):
                if b == 10 and self.last_cr:
                    self.last_cr = False
                    continue
                self.last_cr = b == 13
                echo += b"\r\n"
                line = bytes(self.line).decode(self.charset, errors="replace")
                self.line.clear()
                self.writer.write(bytes(echo))
                echo.clear()
                await self.writer.drain()
                if proc.stdin and not proc.stdin.is_closing():
                    proc.stdin.write((line + "\n").encode("utf-8"))
                    await proc.stdin.drain()
                continue
            self.last_cr = False
            if b in (8, 127):
                if self.line:
                    self.line.pop()
                    echo += b"\x08 \x08"
            elif b == 0x1b or b < 32:
                continue  # ignore escape sequences and other controls
            elif len(self.line) < 200:
                self.line.append(b)
                echo.append(b)
        if echo:
            self.writer.write(bytes(echo))
            await self.writer.drain()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(message)s",
        handlers=[logging.FileHandler(os.path.join(HERE, "twdoor.log"), encoding="utf-8"), logging.StreamHandler()],
    )
    cfg = load_config()
    ensure_server(cfg)
    allow = set(cfg["allow"])
    active = 0

    async def on_connect(reader, writer):
        nonlocal active
        ip = (writer.get_extra_info("peername") or ("?",))[0]
        if ip not in allow:
            log.info("refused %s (not in allow list)", ip)
            writer.close()
            return
        if active >= int(cfg["max_callers"]):
            writer.write(b"\x00The game is full right now. Please try again later.\r\n")
            await writer.drain()
            writer.close()
            return
        active += 1
        try:
            await Session(cfg, reader, writer).run()
        except Exception:
            log.exception("session failed")
        finally:
            active -= 1
            try:
                writer.close()
            except Exception:
                pass

    host, port = split_hostport(cfg["listen"])
    server = await asyncio.start_server(on_connect, host, port)
    log.info("TWClone rlogin door listening on %s:%d", host, port)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
