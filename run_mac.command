#!/bin/bash
set -u
cd "$(dirname "$0")" || exit 1

fail() {
    printf '\n%s\n' "$1" >&2
    read -r -p "Press Enter to close... " _
    exit 1
}

if [[ -x .venv/bin/python3 ]]; then
    PYTHON="$PWD/.venv/bin/python3"
else
    PYTHON="$(command -v python3)" || fail "Python 3.10 or later with Tkinter is required. Install it from https://www.python.org/downloads/macos/"
fi

"$PYTHON" -c 'import sys; import tkinter; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || fail "Python 3.10 or later with Tkinter is required. Install it from https://www.python.org/downloads/macos/"
"$PYTHON" app.py
STATUS=$?
if [[ $STATUS -ne 0 ]]; then
    fail "Ollama Desk exited with an error ($STATUS). See the output above."
fi
