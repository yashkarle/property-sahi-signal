import sys
from pathlib import Path

# Add the repo root to Python path so tests can import ingestion module
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))
