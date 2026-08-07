import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so tests can import top-level packages like `config`.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def pytest_configure(config):
    # no-op placeholder for pytest configuration
    pass
