import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1] / "expense_tracker_project"
sys.path.insert(0, str(PROJECT_DIR))

from app import app  # noqa: E402
