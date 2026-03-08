#!/usr/bin/env bash
set -e

VENV_DIR="$(dirname "$0")/.venv"

echo "Creating virtual environment at $VENV_DIR..."
python3 -m venv "$VENV_DIR"

echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$(dirname "$0")/requirements.txt"

echo ""
echo "Done. To run the bot:"
echo "  cp .env.example .env  # then fill in your API keys"
echo "  $VENV_DIR/bin/python bot.py"
