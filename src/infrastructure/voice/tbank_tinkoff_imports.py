"""Добавляет путь к вендорным `tinkoff.*` (protobuf + gRPC), см. `tinkoff_cloud/`."""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent / "tinkoff_cloud"
if _root.is_dir() and str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
