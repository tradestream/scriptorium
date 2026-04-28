"""One-shot: relocate files left in /ingest/ whose DB rows still point there.

The original ingest pipeline imported the file (created edition_files row by
hash) but failed to move the file out of the ingest directory and update the
row's file_path. This script finishes that job: for each file currently
sitting in INGEST_PATH whose hash matches an edition_files row, move it to
the target library on disk and update the row.

Path translation (container <-> host):
  /data/ingest/...           <->  /Volumes/docker/scriptorium/data/ingest/...
  /data/library/booklore/... <->  /Volumes/docker/scriptorium/library/...

Run with --apply to actually move files; default is dry run.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from app.config import get_settings
from app.services.scanner import _hash_file, BOOK_EXTENSIONS


CONTAINER_TO_HOST = [
    # Most-specific first. ``booklore`` is an optional subfolder under
    # ``/data/library/`` that maps to the host library root either way.
    ("/data/library/booklore", "/Volumes/docker/scriptorium/library"),
    ("/data/library", "/Volumes/docker/scriptorium/library"),
    ("/data", "/Volumes/docker/scriptorium/data"),
]
HOST_TO_CONTAINER_LIBRARY = ("/Volumes/docker/scriptorium/library", "/data/library/booklore")


def container_to_host(p: str) -> Path:
    for container_pfx, host_pfx in CONTAINER_TO_HOST:
        if p.startswith(container_pfx + "/") or p == container_pfx:
            return Path(host_pfx + p[len(container_pfx):])
    return Path(p)


def host_to_container(p: Path) -> str:
    s = str(p)
    if s.startswith(HOST_TO_CONTAINER_LIBRARY[0] + "/"):
        return HOST_TO_CONTAINER_LIBRARY[1] + s[len(HOST_TO_CONTAINER_LIBRARY[0]):]
    raise ValueError(f"refusing to translate non-library host path: {s}")


def main(apply: bool) -> int:
    settings = get_settings()
    ingest_host = Path(settings.INGEST_PATH)
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    files = sorted(
        f for f in ingest_host.rglob("*")
        if f.is_file() and f.suffix.lower() in BOOK_EXTENSIONS
    )
    print(f"Found {len(files)} candidate files in {ingest_host}")

    moved = removed_dup = unmatched = errors = already_ok = 0
    for src in files:
        h = _hash_file(src)
        row = c.execute(
            "SELECT id, file_path FROM edition_files WHERE file_hash=? LIMIT 1",
            (h,),
        ).fetchone()
        if not row:
            print(f"  [unmatched] {src.name}")
            unmatched += 1
            continue
        ef_id, stored_path = row

        if stored_path.startswith("/data/library/"):
            # True duplicate — DB row already points to the library, the file
            # in ingest is a leftover copy.
            host_target = container_to_host(stored_path)
            if host_target.exists():
                print(f"  [dup→delete] {src.name}  (already at {host_target})")
                if apply:
                    src.unlink()
                removed_dup += 1
            else:
                print(f"  [dup-but-missing-target] {src.name}  (DB→{host_target} missing)")
                errors += 1
            continue

        if not stored_path.startswith("/data/ingest/"):
            print(f"  [skip-unexpected-path] {src.name}  → {stored_path}")
            unmatched += 1
            continue

        # Resolve target library from edition.
        lib_row = c.execute(
            """
            SELECT l.path
            FROM edition_files ef
            JOIN editions e ON ef.edition_id = e.id
            JOIN libraries l ON e.library_id = l.id
            WHERE ef.id = ?
            """,
            (ef_id,),
        ).fetchone()
        if not lib_row:
            print(f"  [no-library] {src.name}")
            errors += 1
            continue
        lib_container_path = lib_row[0]
        lib_host_path = container_to_host(lib_container_path)
        lib_host_path.mkdir(parents=True, exist_ok=True)

        dest = lib_host_path / src.name
        # Avoid clobbering anything pre-existing.
        if dest.exists():
            stem, ext = dest.stem, dest.suffix
            for n in range(2, 100):
                candidate = dest.with_name(f"{stem} ({n}){ext}")
                if not candidate.exists():
                    dest = candidate
                    break
            else:
                print(f"  [no-free-name] {src.name}")
                errors += 1
                continue

        new_container_path = host_to_container(dest)
        print(f"  [move] {src.name}")
        print(f"         → {dest}")
        print(f"         DB.file_path: {stored_path}")
        print(f"                    → {new_container_path}")

        if apply:
            try:
                src.rename(dest)
            except OSError as exc:
                print(f"         ERROR moving: {exc}")
                errors += 1
                continue
            c.execute(
                "UPDATE edition_files SET file_path=?, filename=? WHERE id=?",
                (new_container_path, dest.name, ef_id),
            )
            conn.commit()
        moved += 1

    print()
    print(f"Summary: moved={moved} dup_removed={removed_dup} "
          f"unmatched={unmatched} errors={errors} already_ok={already_ok}")
    print("DRY RUN — re-run with --apply to commit." if not apply else "Applied.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Actually move files and update the DB.")
    args = parser.parse_args()
    sys.exit(main(apply=args.apply))
