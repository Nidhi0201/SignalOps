#!/bin/bash
# Run backend using pip/venv

cd "$(dirname "$0")"

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found. Run ./setup.sh first"
    exit 1
fi

# Run uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
