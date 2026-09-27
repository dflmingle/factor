@echo off
setlocal
set "READER_SERVER=D:\factor\scripts\markdown_reader_server.py"
start "Markdown Reader Server" /min python "%READER_SERVER%" --host 127.0.0.1 --port 8765
timeout /t 1 /nobreak >nul
start "" "http://127.0.0.1:8765/"
