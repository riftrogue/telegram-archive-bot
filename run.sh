#!/bin/bash

# Ensure Termux stays awake in the background
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    echo "[*] termux-wake-lock acquired"
fi

echo "[*] Starting moviebot loop..."

while true; do
    python bot.py
    EXIT_CODE=$?
    
    echo "[!] Bot crashed or stopped with exit code $EXIT_CODE."
    echo "[!] Restarting in 5 seconds... (Press Ctrl+C again to force stop)"
    
    sleep 5
done
