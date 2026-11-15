@echo off
rem Starts the TWClone rlogin door (and the TWClone game server, if it isn't running).
rem Settings: twdoor.json   Logs: twdoor.log, server.log, twclone.log
cd /d "%~dp0"
python twdoor.py
