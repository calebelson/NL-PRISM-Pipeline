from __future__ import annotations
import json, pathlib
from typing import Any, Mapping

__all__ = ["update_meta"]

def update_meta(base: str | pathlib.Path, key: str, entry: Mapping[str, Any], filename: str = "meta.json") -> pathlib.Path:
    """Create or update a JSON meta file with a top-level key.

    If the file exists and is a JSON object, it is loaded and the key overwritten.
    If the file is missing or invalid, a new object is created.

    Parameters:
      base: directory containing the meta file (created if needed)
      key: top-level key to set (e.g. 'parse_scenario', 'prism_generation')
      entry: JSON-serializable mapping to store under the key
      filename: meta file name (default 'meta.json')

    Returns the pathlib.Path to the written file.
    """
    base_path = pathlib.Path(base)
    base_path.mkdir(parents=True, exist_ok=True)
    meta_path = base_path / filename

    data: dict[str, Any] = {}
    if meta_path.exists():
        try:
            loaded = json.loads(meta_path.read_text())
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}

    # Overwrite / insert key
    data[key] = entry
    meta_path.write_text(json.dumps(data, indent=2))
    return meta_path
