# twclone as a BBS door

An rlogin door for any BBS that offers rlogin doors. Callers play twclone from
the BBS with no password of their own: the door signs them in by their BBS name.

The Windows ZIP includes these files next to `bin`, `sql` and `client`.

## Pieces
| File | What it is |
|---|---|
| `twdoor.py` | The rlogin door. Listens on 127.0.0.1:2341, starts `bin/server.exe` if the game server isn't running. |
| `twdoor.json` | Its settings. Made on the first run, with a new secret. |
| `client/door_client.py` | Runs the stock text client signed in as the caller; makes a new captain on the first visit. |
| `client/door_ansi.py`, `door-theme.json` | Colour screens, status bar and one-key menu prompts. |
| `start-twdoor.cmd` | Starts the door from its folder. |

Needs Python 3 on the `PATH`, and a universe made with `Initialize-Universe.ps1`.

## Settings (`twdoor.json`)
- `listen`, `allow`: where the door listens and which addresses may connect. rlogin has no password, so keep `allow` to the BBS.
- `server`, `start_server`, `server_exe`: the game server.
- `name_from`: which rlogin name is the caller, `server` (the remote user) or `client`.
- `charset` (`cp437` or `utf-8`), `columns`, `rows`, `max_callers`, `idle_minutes`.
- `color` (`auto`, `on`, `off`) and `plain_terminals`: with `auto`, callers whose terminal type is in that list get plain text.
- `hotkeys`: menu prompts take one key, no Enter.
- `secret`: makes each caller's twclone password (an HMAC of their name). **Keep it: changing it locks out existing captains.**

## Colours (`door-theme.json`)
Every colour is a word like `"bright yellow"` or `"white on blue"`; also `rule_char`, `box_char` and `width`. Changes apply on the next visit.

## Game server settings
In the `config` table of the game database. For a door, set the idle timeout to the door's own (the default 10 s drops a player who stops to read):

    INSERT INTO config(key, value, type) VALUES
      ('turnsperday', '250', 'int'), ('startingcredits', '20000', 'int'),
      ('server_request_timeout_ms', '1800000', 'int')
    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

Restart the game server after changing them.

## On the BBS
Add an rlogin door to 127.0.0.1:2341 that sends the caller's name as the remote user.
