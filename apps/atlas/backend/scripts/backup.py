#!/usr/bin/env python3
"""Consistent SQLite backup (safe while the app is running, thanks to WAL).

    python scripts/backup.py --db /data/atlas.db --out /backups --keep 7

Uses sqlite3's online backup API, so no downtime and no torn copies.
Wire it into cron once a day (yassin's task), e.g.:
    15 3 * * * cd /srv/atlas/backend && .venv/bin/python scripts/backup.py --db /data/atlas.db --out /backups --keep 7
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def backup(db_path: Path, out_dir: Path, keep: int) -> Path:
    if not db_path.exists():
        raise SystemExit(f"database not found: {db_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"{db_path.stem}-{stamp}.db"

    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
        integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        dst.close()
        src.close()
    if integrity != "ok":
        target.unlink(missing_ok=True)
        raise SystemExit(f"backup failed integrity check: {integrity}")

    daily = sorted(out_dir.glob(f"{db_path.stem}-*.db"))
    for old in daily[:-keep] if keep > 0 else []:
        old.unlink(missing_ok=True)

    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backup the Atlas SQLite database")
    parser.add_argument("--db", default="/data/atlas.db")
    parser.add_argument("--out", default="/backups")
    parser.add_argument("--keep", type=int, default=7, help="number of copies to retain")
    args = parser.parse_args(argv)

    path = backup(Path(args.db), Path(args.out), args.keep)
    size = path.stat().st_size
    print(f"backup ok: {path} ({size} bytes, integrity_check=ok)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
