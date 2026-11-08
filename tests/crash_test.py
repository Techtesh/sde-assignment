"""Real process-exit matrix; run explicitly, not during ordinary pytest collection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.verify_delivery import main


if __name__ == "__main__":
    sys.argv.append("--crash-matrix")
    main()
