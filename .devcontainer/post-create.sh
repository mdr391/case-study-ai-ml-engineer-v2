#!/usr/bin/env bash
set -e

echo "==============================================="
echo "  Third Way Health - Engineering Setup"
echo "==============================================="
echo ""

# Install Python dependencies
echo "[1/4] Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# Verify Anthropic SDK is importable
echo "[2/4] Verifying Anthropic SDK..."
python -c "import anthropic; print(f'  anthropic SDK v{anthropic.__version__} - OK')"

# Install Claude Code CLI
echo "[3/4] Installing Claude Code CLI..."
npm install -g @anthropic-ai/claude-code
echo "  Claude Code installed - OK"

# Check for API key
echo "[4/4] Checking API key..."
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo ""
  echo "  WARNING: ANTHROPIC_API_KEY is not set."
  echo "  In Codespaces, add it as a repository/codespace secret."
  echo ""
else
  echo "  ANTHROPIC_API_KEY is set - OK"
fi

echo ""
echo "==============================================="
echo "  Setup complete."
echo ""
echo "  Quick reference:"
echo "    Verify setup:  python verify_setup.py"
echo "    Run API:       uvicorn app.main:app --reload"
echo "    Docs:          http://127.0.0.1:8000/docs"
echo "==============================================="
