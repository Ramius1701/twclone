# twclone for Windows

Extract this ZIP on 64-bit Windows. The game executables and their Cygwin
runtime DLLs are in `bin`. Run the scripts from PowerShell.

1. Start a PostgreSQL instance. Create a login role with permission to create
   the game database. Use a dedicated role and database for this game.
2. Copy `bigbang.example.json` to `bigbang.json`. Set both connection strings
   for your PostgreSQL instance. Keep `%DB%` in the application connection
   string. PostgreSQL's `%APPDATA%\postgresql\pgpass.conf` can provide the
   password. With the bundled Cygwin client library, set `PGPASSFILE` to
   the password file's absolute path if it is not found automatically.
3. Run `.\Initialize-Universe.ps1`. Big Bang can replace an existing universe
   after confirmation. Choose a new database name for the first run.
4. Run `.\Start-Server.ps1`. Keep this window open while hosting the game.
5. With Python 3 installed, run
   `py -3 .\client\client.py --register --host 127.0.0.1 --port 1234`
   to create a player. Omit `--register` on subsequent launches. For a
   remote server, use its hostname and game port.

The standalone server and client communicate over TCP. For access outside a
trusted network, configure encrypted transport before exposing the game port.

The game source is in the [twclone fork](https://github.com/Ramius1701/twclone)
at the revision in `source-commit.txt`. The bundled runtime libraries are
from [Cygwin packages](https://cygwin.com/packages/), where package source is
available. Package notices are under `licenses`.

To run it as a BBS rlogin door, see `DOOR-README.md`.
