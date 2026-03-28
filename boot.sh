#!/usr/bin/env bash

echo "[SYSTEM] 1. Bypassing Local Model Vault (Cloud AI APIs Active)..."

echo "[SYSTEM] 2. Booting Neural Switchboard on Render Port ${PORT:-10000}..."

# Start the Flask-SocketIO app using Gunicorn with threaded workers
gunicorn -k gthread --workers 2 --threads 15 --timeout 1200 --keep-alive 5 --max-requests 800 --max-requests-jitter 50 --preload --bind 0.0.0.0:${PORT:-10000} app:app
