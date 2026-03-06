"""
Pytest configuration — adds backend/ to sys.path so imports like
`from services.llm_client import ...` work without hacks in each test file.
"""
import sys
from pathlib import Path

# Add backend/ directory to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
