"""JSON persistence repository for pack.json with atomic writes."""

import json
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class PackRepository:
    """Manages loading and atomic saving of a beatmap pack JSON file."""

    def __init__(self, pack_file: Path) -> None:
        self.pack_file = pack_file

    def load(self) -> dict[str, dict]:
        """Load pack data, returning an empty dict if missing or corrupted."""
        try:
            with open(self.pack_file, encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                return {k: v for k, v in data.items() if isinstance(v, dict)}
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            logger.warning("pack.json corrupto en %s; se inicia con pack vacío.", self.pack_file)
            return {}

    def save(self, pack: dict) -> None:
        """Persist pack data atomically via a temporary file and os.replace."""
        self.pack_file.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.pack_file.parent),
            prefix=f".{self.pack_file.stem}_",
            suffix=".tmp",
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(pack, f, indent=4)
            os.replace(tmp_path, self.pack_file)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

    def clear(self) -> None:
        """Reset pack data to an empty dictionary."""
        self.save({})

    @staticmethod
    def next_index(pack: dict) -> str:
        """Compute the next collision-free numeric string index."""
        numeric_keys = [int(k) for k in pack if k.isdigit()]
        return str(max(numeric_keys, default=0) + 1)
