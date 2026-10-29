import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
SCRIPTS_DIR = ROOT_DIR / "scripts"

# Ensure backend/ is first in sys.path so `from app.*` imports resolve to backend/app/
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from app.main import run_server  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    run_server(host="0.0.0.0", port=port)
