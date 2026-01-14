#!/bin/bash
set -e

echo "🚀 Starting FastAPI server"

uvicorn app.main:app \
  --host 0.0.0.0 \
  --port ${PORT:-8000}
