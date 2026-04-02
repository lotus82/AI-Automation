#!/usr/bin/env python3
"""Пересборка gRPC/Python из .proto в src/infrastructure/voice/sber_protos."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    proto_dir = root / "src" / "infrastructure" / "voice" / "sber_protos"
    if not proto_dir.is_dir():
        print("Не найден каталог:", proto_dir, file=sys.stderr)
        return 1

    protos = [
        "google/protobuf/duration.proto",
        "google/protobuf/timestamp.proto",
        "task.proto",
        "recognition.proto",
        "synthesis.proto",
    ]
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        "-I.",
        f"--python_out={proto_dir}",
        f"--grpc_python_out={proto_dir}",
        *protos,
    ]
    print("Запуск:", " ".join(cmd), file=sys.stderr)
    r = subprocess.run(cmd, cwd=proto_dir, check=False)
    if r.returncode != 0:
        return r.returncode
    print(
        "Далее вручную замените в сгенерированных файлах "
        "`import task_pb2` → `from . import task_pb2` и т.п. (см. README_PROTO.ru.md).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
