import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "dndtable.db"
SECRET_KEY = os.environ.get("DNDTABLE_SECRET_KEY", "development-secret-key")
