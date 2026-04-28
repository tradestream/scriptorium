"""One-shot: move 254 today's-ingest editions from Academic (lib 1) to Books (lib 3).

The trigger_scan run earlier today imported these into the first active
library (Academic) because INGEST_DEFAULT_LIBRARY was unset. Now that
``.env`` is fixed, this script relocates the rows and the underlying files.

For each edition:
  - Move the file on disk: <library_path>/academic/...  →  <library_path>/books/...
  - Update edition_files.file_path / filename
  - Update editions.library_id  (1 → 3)

Run with --apply to actually perform the changes; default is dry run.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from app.config import get_settings, resolve_path


SRC_LIB_ID = 1   # Academic
DST_LIB_ID = 3   # Books
SRC_PATH_FRAGMENT = "/booklore/academic/"
DST_PATH_FRAGMENT = "/booklore/books/"


def main(apply: bool, min_id: int, max_id: int) -> int:
    settings = get_settings()
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Resolve target library's host path so we can mkdir it.
    dst_row = c.execute("SELECT path FROM libraries WHERE id=?", (DST_LIB_ID,)).fetchone()
    dst_lib_container = dst_row[0]
    dst_lib_host = Path(resolve_path(dst_lib_container))
    dst_lib_host.mkdir(parents=True, exist_ok=True)

    rows = c.execute(
        """
        SELECT e.id, ef.id, ef.file_path, ef.filename
        FROM editions e
        JOIN edition_files ef ON ef.edition_id = e.id
        WHERE e.library_id = ?
          AND e.id BETWEEN ? AND ?
        ORDER BY e.id
        """,
        (SRC_LIB_ID, min_id, max_id),
    ).fetchall()
    print(f"Editions to reassign: {len({r[0] for r in rows})}, "
          f"edition_files to update: {len(rows)}")

    moved = skipped_missing = collisions = errors = 0
    for ed_id, ef_id, container_path, filename in rows:
        host_src = Path(resolve_path(container_path))
        if not host_src.exists():
            print(f"  [missing] ed={ed_id} ef={ef_id}  src not on disk: {host_src}")
            skipped_missing += 1
            continue

        # Compute destination
        if SRC_PATH_FRAGMENT in container_path:
            new_container = container_path.replace(SRC_PATH_FRAGMENT, DST_PATH_FRAGMENT, 1)
        else:
            # Edge case — wasn't in academic per stored path. Drop into books root.
            new_container = str(Path(dst_lib_container) / filename)
        host_dst = Path(resolve_path(new_container))
        # Avoid clobbering pre-existing files
        if host_dst.exists():
            stem, ext = host_dst.stem, host_dst.suffix
            for n in range(2, 100):
                candidate = host_dst.with_name(f"{stem} ({n}){ext}")
                if not candidate.exists():
                    host_dst = candidate
                    new_container = str(Path(new_container).with_name(candidate.name))
                    print(f"  [rename-on-collide] ed={ed_id}  → {candidate.name}")
                    collisions += 1
                    break
            else:
                print(f"  [no-free-name] ed={ed_id} ef={ef_id}  base={filename}")
                errors += 1
                continue

        host_dst.parent.mkdir(parents=True, exist_ok=True)

        if apply:
            try:
                host_src.rename(host_dst)
            except OSError as exc:
                print(f"  [io-error] ed={ed_id} ef={ef_id}: {exc}")
                errors += 1
                continue
            c.execute(
                "UPDATE edition_files SET file_path=?, filename=? WHERE id=?",
                (new_container, host_dst.name, ef_id),
            )
            c.execute(
                "UPDATE editions SET library_id=? WHERE id=?",
                (DST_LIB_ID, ed_id),
            )
            conn.commit()
        moved += 1

    print()
    print(f"Summary: moved={moved} collisions={collisions} "
          f"missing={skipped_missing} errors={errors}")
    print("DRY RUN — re-run with --apply to commit." if not apply else "Applied.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Actually move files and update the DB.")
    parser.add_argument("--min-id", type=int, default=8719,
                        help="Lowest edition.id to reassign (inclusive).")
    parser.add_argument("--max-id", type=int, default=8972,
                        help="Highest edition.id to reassign (inclusive).")
    args = parser.parse_args()
    sys.exit(main(apply=args.apply, min_id=args.min_id, max_id=args.max_id))
