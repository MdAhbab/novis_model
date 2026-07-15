"""NOVIS host package: BLE receiver, AEAD, frame assembly, live inference.

Importing the package puts the project's `src/` on sys.path so the `novis`
model package is available to the host modules.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
