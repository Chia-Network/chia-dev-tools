from __future__ import annotations

import importlib.metadata

try:
    __version__ = importlib.metadata.version("chia-dev-tools")
except importlib.metadata.PackageNotFoundError:
    # package is not installed
    __version__ = "unknown"
