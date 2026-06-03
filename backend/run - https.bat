@echo off
cd /d "%~dp0"
call venv\Scripts\activate
set MOUNTHUB_SSL_CERTFILE=certs/localhost+3.pem
set MOUNTHUB_SSL_KEYFILE=certs/localhost+3-key.pem
python -m uvicorn app.main:app --host 0.0.0.0 --port 8014 --reload --ssl-certfile certs/localhost+3.pem --ssl-keyfile certs/localhost+3-key.pem
pause
