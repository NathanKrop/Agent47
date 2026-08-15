"""Vercel serverless function entry point for FastAPI app."""

import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dashboard.app import app

# Export app for Vercel
__all__ = ['app']
