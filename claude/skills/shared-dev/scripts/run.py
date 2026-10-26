"""Entry point for the sd modules: python -I run.py MODULE [ARGS...].

-I keeps the caller's directory off sys.path; this file adds its own
directory so the sd package imports from wherever it is called.
"""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python -I run.py MODULE [ARGS...]")
    importlib.import_module(f"sd.{sys.argv[1]}").main(sys.argv[2:])
