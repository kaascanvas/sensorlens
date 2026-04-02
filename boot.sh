#!/usr/bin/env bash

echo "[SYSTEM] 1. Bypassing Local Model Vault (Cloud AI APIs Active)..."

echo "[SYSTEM] 2. Booting Neural Switchboard on Render Port ${PORT:-10000}..."

# Start the Quart-SocketIO app using Uvicorn with native Asyncio
uvicorn app:asgi_app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --ws websockets