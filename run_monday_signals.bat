@echo off
:: Launcher Bloomberg V2 Monday Signals
:: Schedulato ogni lunedi alle 14:00 ora Bali (WITA UTC+8)

cd /D "C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot"

echo [%date% %time%] Avvio segnali Bloomberg V2... >> monday_signals.log 2>&1
"C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot\venv\Scripts\python.exe" -X utf8 -u main.py >> monday_signals.log 2>&1
echo [%date% %time%] Completato. >> monday_signals.log 2>&1
