#!/bin/zsh
# Run in Terminal: zsh run.command
cd "$(dirname "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  echo "Create the environment first: python3.12 -m venv .venv"
  exit 1
fi
.venv/bin/python scripts/check_demo.py
if [[ $? -ne 0 ]]; then
  echo "Fix the checks above before starting the demo."
  exit 1
fi
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502
