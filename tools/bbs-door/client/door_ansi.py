"""ANSI colour and BBS-style screens for the twclone text client (BBS door).

Loaded by door_client.py. It leaves client.py untouched and instead:
  * redraws the sector display, the status bar, menus and prompts in colour,
  * colours every other line the client prints (headers, "Label: value"
    lines, numbers, errors) through a stdout filter, and
  * marks menu prompts so the rlogin bridge can take a single key (hotkeys).

Every colour comes from door-theme.json (one folder up), so the sysop can
change the look without touching code. TWDOOR_COLOR=0 turns colour off.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
THEME_PATH = os.path.join(os.path.dirname(HERE), "door-theme.json")

# Sent just before a menu prompt; twdoor.py strips it and takes one key.
HOTKEY_MARK = "\x00HK\x00"

DEFAULT_THEME = {
    "frame": "blue",
    "title": "bright white",
    "title_text": "bright yellow",
    "label": "green",
    "value": "bright cyan",
    "number": "bright yellow",
    "sector": "bright yellow",
    "fedspace": "bright green",
    "port": "bright cyan",
    "planet": "bright magenta",
    "ship": "bright white",
    "fighters": "bright red",
    "beacon": "yellow",
    "warps": "bright green",
    "none": "bright black",
    "status_label": "cyan",
    "status_value": "bright white",
    "status_bar": "blue",
    "menu_key": "bright yellow",
    "menu_bracket": "magenta",
    "menu_text": "cyan",
    "section": "bright magenta",
    "prompt": "bright magenta",
    "prompt_text": "bright yellow",
    "header": "bright cyan",
    "error": "bright red",
    "warn": "yellow",
    "ok": "bright green",
    "text": "white",
    "rule_char": "─",
    "box_char": "═",
    "width": 79,
}

_BASE = {"black": 0, "red": 1, "green": 2, "yellow": 3, "blue": 4, "magenta": 5, "cyan": 6, "white": 7}


def _sgr(spec: str) -> str:
    """'bright yellow on blue' -> ANSI SGR sequence."""
    words = str(spec or "").lower().replace("_", " ").split()
    codes = ["0"]
    bright = False
    on = False
    for w in words:
        if w in ("bright", "bold", "light"):
            bright = True
        elif w == "on":
            on = True
        elif w in _BASE:
            if on:
                codes.append(str(40 + _BASE[w]))
            else:
                codes.append(str(30 + _BASE[w]))
                if bright:
                    codes.append("1")
            bright = False
        elif w == "blink":
            codes.append("5")
    return "\x1b[" + ";".join(codes) + "m"


class Theme:
    def __init__(self, enabled: bool):
        cfg = dict(DEFAULT_THEME)
        try:
            with open(THEME_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except FileNotFoundError:
            try:
                with open(THEME_PATH, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_THEME, f, indent=2, ensure_ascii=False)
            except OSError:
                pass
        except (OSError, ValueError):
            pass
        self.cfg = cfg
        self.enabled = enabled
        self.width = int(cfg.get("width", 79))
        self.rule_char = cfg.get("rule_char", "-") or "-"
        self.box_char = cfg.get("box_char", "=") or "="
        self.bar_char = "│"
        if not enabled:  # plain terminals: stick to ASCII lines
            self.rule_char, self.box_char, self.bar_char = "-", "=", "|"

    def c(self, element: str, text: str = "") -> str:
        """Colour `text` as `element`, resetting to the base text colour after."""
        if not self.enabled:
            return text
        return _sgr(self.cfg.get(element, "white")) + text + _sgr(self.cfg.get("text", "white"))

    def reset(self) -> str:
        return _sgr(self.cfg.get("text", "white")) if self.enabled else ""


T: Theme  # set by install()
_ESC = re.compile(r"\x1b\[[0-9;]*m")


def visible_len(s: str) -> int:
    return len(_ESC.sub("", s))


# ---------------------------------------------------------------------------
# Generic line colouring for everything the client prints
# ---------------------------------------------------------------------------
_HEADER = re.compile(r"^(\s*)(-{2,3}|={2,3})\s*(.+?)\s*(-{2,3}|={2,3})\s*$")
_ERROR = re.compile(r"^\s*(\[Error\]|Error:|Unknown command|Login failed|Cannot |Failed|Not enough|Insufficient|You can't|You cannot|Refused|.*\b(refused|failed|denied)\b)", re.I)
_WARN = re.compile(r"^\s*(\[Warn\]|\[NYI\]|Warning|Cancelled)", re.I)
_OK = re.compile(r"^\s*(\[OK\]|Success|Done\b|Welcome aboard|Account created|You (bought|sold|moved|warp|land|dock))", re.I)
_SECTION = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_KV = re.compile(r"^([\s│┃├┌└|+]*)([A-Za-z][A-Za-z0-9 '()/#.&-]{0,30}?)(\s*:\s+)(\S.*)$")
_BOXED = re.compile(r"^(\s*[─-╿+=][─-╿+=\- ]*)(.*)$")
_NUM = re.compile(r"(?<![\w.\x1b\[])(\d[\d,]*(?:\.\d+)?)(?![\w])")


def _colour_numbers(text: str, base: str) -> str:
    return _NUM.sub(lambda m: T.c("number", m.group(1)) + _sgr(T.cfg.get(base, "white")), text)


def colour_line(line: str) -> str:
    if not T.enabled or not line.strip() or "\x1b[" in line:
        return line
    m = _HEADER.match(line)
    if m:
        return m.group(1) + T.c("frame", m.group(2) + " ") + T.c("header", m.group(3)) + T.c("frame", " " + m.group(4))
    if _ERROR.match(line):
        return T.c("error", line)
    if _WARN.match(line):
        return T.c("warn", line)
    if _OK.match(line):
        return T.c("ok", line)
    m = _SECTION.match(line)
    if m:
        return T.c("section", line)
    m = _KV.match(line)
    if m and "http" not in line:
        indent, key, sep, val = m.groups()
        coloured_val = _sgr(T.cfg.get("value", "white")) + _colour_numbers(val, "value")
        return T.c("frame", indent) + T.c("label", key) + T.c("frame", sep) + coloured_val + T.reset()
    m = _BOXED.match(line)
    if m:
        edge, rest = m.groups()
        if re.search(r"[A-Za-z]", rest):
            return T.c("frame", edge) + colour_line(rest)
        return T.c("frame", line)
    return _sgr(T.cfg.get("text", "white")) + _colour_numbers(line, "text")


class ColourStream(io.TextIOBase):
    """Wraps stdout: colours whole lines; partial lines (prompts) on flush."""

    def __init__(self, raw):
        self.raw = raw
        self.buf = ""

    def writable(self):
        return True

    @property
    def encoding(self):
        return getattr(self.raw, "encoding", "utf-8")

    def isatty(self):
        return False

    def write(self, s):
        if not isinstance(s, str):
            s = str(s)
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            self.raw.write(colour_line(line) + "\n")
        return len(s)

    def flush(self):
        if self.buf:
            part, self.buf = self.buf, ""
            if T.enabled and "\x1b[" not in part and HOTKEY_MARK not in part:
                part = T.c("prompt_text", part)
            self.raw.write(part)
        self.raw.flush()

    def fileno(self):
        return self.raw.fileno()


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------
def rule(title: str = "") -> str:
    w = T.width
    if not title:
        return T.c("frame", T.rule_char * w)
    left = T.box_char * 3 + " "
    right_len = max(3, w - len(left) - len(title) - 1)
    return T.c("frame", left) + T.c("title_text", title) + T.c("frame", " " + T.box_char * right_len)


def kv(label: str, value: str, width: int = 9) -> str:
    if not label:  # continuation line under the same label
        return " " * (width + 2) + value
    return T.c("label", label.ljust(width)) + T.c("frame", ": ") + value


def install(client) -> None:
    global T
    color = os.environ.get("TWDOOR_COLOR", "1") not in ("0", "off", "no", "false")
    T = Theme(color)
    sys.stdout = ColourStream(sys.stdout)

    hud_module = client.hud_module

    def redisplay_sector(ctx):
        d = ctx.last_sector_desc or {}
        sid, name = d.get("id"), d.get("name")
        none = T.c("none", "none")
        print()
        print(rule("Sector Scan"))
        where = T.c("sector", str(sid))
        if name:
            fed = "fed" in str(name).lower()
            where += T.c("frame", " in ") + T.c("fedspace" if fed else "value", str(name))
        print(kv("Sector", where))

        port = d.get("port")
        # V3 clients record "no port here" as {"present": False}.
        if isinstance(port, dict) and port.get("present") is False:
            port = None
        if port:
            cls = port.get("class")
            pnm = port.get("name") or "Port"
            extra = []
            if cls not in (None, "", "?"):
                extra.append(f"Class {cls}")
            code = port.get("type_code") or port.get("code") or port.get("trade_code")
            if code:
                extra.append(str(code))
            tail = (T.c("frame", ", ") + T.c("value", ", ".join(extra))) if extra else ""
            print(kv("Port", T.c("port", pnm) + tail))
        else:
            print(kv("Port", none))

        planets = d.get("planets") or []
        if planets:
            first = True
            for pl in planets:
                cls = pl.get("class") or pl.get("planet_class") or pl.get("type")
                tag = (T.c("menu_bracket", "(") + T.c("planet", str(cls)) + T.c("menu_bracket", ") ")) if cls else ""
                text = tag + T.c("planet", pl.get("name") or "Unnamed")
                print(kv("Planets" if first else "", text))
                first = False
        else:
            print(kv("Planets", none))

        ships = d.get("ships") or []
        if ships:
            first = True
            for s in ships:
                nm = s.get("name") or s.get("ship_name") or "Unnamed"
                owner = s.get("owner_name") or s.get("player_name")
                text = T.c("ship", nm)
                if owner:
                    text += T.c("frame", ", owned by ") + T.c("value", owner)
                print(kv("Ships" if first else "", text))
                first = False
        else:
            print(kv("Ships", none))

        counts = d.get("counts")
        if isinstance(counts, dict):
            f = counts.get("fighters")
            if isinstance(f, int) and f > 0:
                print(kv("Fighters", T.c("fighters", f"{f:,}")))
            m = counts.get("mines")
            if isinstance(m, int) and m > 0:
                print(kv("Mines", T.c("fighters", f"{m:,}")))

        beacon = d.get("beacon")
        print(kv("Beacon", T.c("beacon", beacon) if beacon else none))

        adj = d.get("adjacent") or []
        nums = [str(a.get("to_sector", "?")) if isinstance(a, dict) else str(a) for a in adj]
        sep = T.c("frame", " - ")
        exits = sep.join(T.c("warps", n) for n in nums) if nums else none
        print(kv("Exits", exits))

    # Replace the registered handler and the module function (direct callers).
    client.register("redisplay_sector")(redisplay_sector)
    client.redisplay_sector = redisplay_sector

    def render_hud(ctx, width):
        if ctx.current_menu in client._HUD_EXCLUDED_MENUS:
            return
        h = ctx.hud
        u = hud_module.UNAVAILABLE

        def v(x):
            return u if x is None else str(x)

        credits = u if h.credits is None else client.format_credits(h.credits)
        holds = f"{h.cargo_used}/{h.cargo_total}" if h.cargo_used is not None and h.cargo_total is not None else u
        link = hud_module.connection_label(ctx.conn.connected, h.last_refresh_ts)
        bar = T.c("status_bar", T.bar_char)

        def item(label, value):
            return T.c("status_label", label + " ") + T.c("status_value", value)

        line1 = [item("Turns", v(h.turns_remaining)), item("Credits", credits), item("Holds", holds),
                 item("Fighters", v(h.fighters)), item("Shields", v(h.shields))]
        extra = []
        unread = []
        for attr, label in (("unread_mail", "mail"), ("unread_notices", "notices"), ("unread_news", "news")):
            n = getattr(h, attr, None)
            if isinstance(n, int) and n > 0:
                unread.append(f"{n} {label}")
        if unread:
            extra.append(T.c("ok", "New: " + ", ".join(unread)))
        if link != "ONLINE":
            extra.append(T.c("error", "Link " + link))
        print()
        print(T.c("status_bar", T.rule_char * T.width))
        print(" " + (" " + bar + " ").join(line1))
        if h.ship_name:
            ship_name = "".join(char for char in h.ship_name if char.isprintable())
            print(" " + item("Ship", ship_name))
        if extra:
            print(" " + (" " + bar + " ").join(extra))
        print(T.c("status_bar", T.rule_char * T.width))

    client._render_hud = render_hud

    def render_menu(ctx):
        client._door_ctx = ctx  # lets read_choice show the sector
        menu = ctx.menus.get(ctx.current_menu)
        if not menu:
            print(f"[Error] Menu '{ctx.current_menu}' not found.")
            return
        render_hud(ctx, T.width)
        try:
            client.menu_on_enter(ctx, menu)
        except ConnectionError:
            raise
        except Exception:
            pass
        flags = client.compute_flags(ctx)
        title = menu.get("title", ctx.current_menu)
        title = title.replace("{{sector_id}}", str(ctx.current_sector_id or "?"))
        port_name = (ctx.last_sector_desc.get("port") or {}).get("name") or "Port"
        title = title.replace("{{port_name}}", str(port_name))
        lines = title.split("\n")
        head = re.sub(r"^\s*-+\s*|\s*-+\s*$", "", lines[0])
        print(rule(head))
        for extra in lines[1:]:
            print(T.c("value", extra.strip()))

        def visible(opts):
            # drop protocol names such as "(move.scan)" that the stock labels carry
            return [_PROTO.sub("", client._interp_label(o["label"], ctx)) for o in opts
                    if client.option_visible(o, flags) and client._option_visible_with_ctx(ctx, o)]

        groups = []
        if "sections" in menu:
            for sec in menu["sections"]:
                groups.append((sec.get("name"), visible(sec.get("options", []))))
        else:
            groups.append((None, visible(menu.get("options", []))))

        for name, labels in groups:
            if name:
                print(T.c("section", f" {name}"))
            colw = max((len(x) for x in labels), default=0)
            two = len(labels) > 1 and colw <= (T.width - 6) // 2
            step = 2 if two else 1
            for i in range(0, len(labels), step):
                row = labels[i:i + step]
                cells = [style_option(lbl, colw if (two and j == 0) else 0) for j, lbl in enumerate(row)]
                print("  " + "    ".join(cells))

    client.render_menu = render_menu

    def read_choice():
        try:
            sid = None
            try:
                sid = client._door_ctx.current_sector_id  # set by door_client
            except AttributeError:
                pass
            where = (T.c("frame", "[") + T.c("sector", str(sid)) + T.c("frame", "] ")) if sid else ""
            prompt = "\n" + T.c("prompt", "Command ") + where + T.c("frame", "(?=menu) ") + T.c("prompt_text", ": ")
            sys.stdout.write(prompt)
            sys.stdout.write(HOTKEY_MARK)
            sys.stdout.flush()
            return input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "q"

    client.read_choice = read_choice

    orig_handle = client.handle_choice

    def handle_choice(ctx, choice):
        if choice == "":
            return  # the menu is drawn again on the next loop
        if choice == "?":
            menu = ctx.menus.get(ctx.current_menu, {})
            opts = menu.get("options", []) + [o for s in menu.get("sections", []) for o in s.get("options", [])]
            if not any(o.get("key") == "?" for o in opts):
                return  # "?" redraws the menu unless the menu has its own "?"
        return orig_handle(ctx, choice)

    client.handle_choice = handle_choice


_OPT = re.compile(r"^\(([^)]+)\)\s*(.*)$")
_PROTO = re.compile(r"\s*\((?:[a-z_]+\.)+[a-z_]+\)")


def style_option(label: str, pad: int = 0) -> str:
    m = _OPT.match(label)
    if m:
        key, text = m.groups()
        out = T.c("menu_bracket", "<") + T.c("menu_key", key) + T.c("menu_bracket", ">") + " " + T.c("menu_text", text)
    else:
        out = T.c("menu_text", label)
    if pad:
        out += " " * max(0, pad - len(label))
    return out
