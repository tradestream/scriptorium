#!/usr/bin/env python3
"""
Migrate books and metadata from Booklore (MariaDB) to Scriptorium (SQLite).

Run inside the Scriptorium backend container:
  docker exec scriptorium-backend-1 python3 /app/migrate_booklore.py

Requires pymysql: pip install pymysql
"""

import hashlib
import os
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path

BOOKLORE_DB_HOST = os.environ.get("BOOKLORE_DB_HOST", "host.docker.internal")
BOOKLORE_DB_PORT = int(os.environ.get("BOOKLORE_DB_PORT", "3307"))
BOOKLORE_DB_USER = "bookloreuser"
BOOKLORE_DB_PASS = "booklorepass"
BOOKLORE_DB_NAME = "booklore"

SCRIPTORIUM_DB = "/data/config/scriptorium.db"
COVERS_PATH = Path("/data/covers")
BOOKLORE_IMAGES = Path("/data/library/booklore/_images")

# Map Booklore library_path → mount name inside Scriptorium container
LIBRARY_PATH_MAP = {
    "/books": "books",
    "/academic": "academic",
    "/comics": "comics",
    "/comics-mature": "comics-mature",
    "/books-mature": "books-mature",
    "/art-photography": "art-photography",
    "/art-photography-mature": "art-photography-mature",
    "/cookbooks": "cookbooks",
    "/playboy-mature": "playboy-mature",
    "/magazines-periodicals": "magazines-periodicals",
}

try:
    import pymysql
    import pymysql.cursors
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pymysql", "-q"])
    import pymysql
    import pymysql.cursors

import sqlite3


def get_booklore_conn():
    return pymysql.connect(
        host=BOOKLORE_DB_HOST,
        port=BOOKLORE_DB_PORT,
        user=BOOKLORE_DB_USER,
        password=BOOKLORE_DB_PASS,
        database=BOOKLORE_DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_scriptorium_conn():
    conn = sqlite3.connect(SCRIPTORIUM_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def now_iso():
    return datetime.utcnow().isoformat()


def copy_cover(booklore_book_id: int, book_uuid: str):
    """Copy cover from Booklore image cache to Scriptorium covers dir."""
    cover_src = BOOKLORE_IMAGES / str(booklore_book_id) / "cover.jpg"
    try:
        if not cover_src.exists():
            return None, None
    except OSError:
        return None, None
    cover_dst = COVERS_PATH / f"{book_uuid}.jpg"
    try:
        if not cover_dst.exists():
            shutil.copy2(cover_src, cover_dst)
        cover_hash = hashlib.md5(cover_dst.read_bytes()).hexdigest()[:8]
        return cover_hash, "jpg"
    except OSError:
        return None, None


def resolve_file_path(lib_path: str, sub_path: str, file_name: str):
    """Resolve a Booklore file path to the container-internal path.

    We trust the DB — don't check existence (avoids macOS NFS open-file limits).
    """
    mount_name = LIBRARY_PATH_MAP.get(lib_path)
    if not mount_name:
        return None
    base = f"/data/library/booklore/{mount_name}"
    if sub_path:
        return f"{base}/{sub_path}/{file_name}"
    return f"{base}/{file_name}"


def get_or_create_author(sconn, name: str, cache: dict) -> int:
    key = name.strip().lower()
    if key in cache:
        return cache[key]
    row = sconn.execute("SELECT id FROM authors WHERE lower(name) = ?", (key,)).fetchone()
    if row:
        cache[key] = row[0]
        return row[0]
    cur = sconn.execute("INSERT INTO authors (name) VALUES (?)", (name.strip(),))
    aid = cur.lastrowid
    cache[key] = aid
    return aid


def get_or_create_tag(sconn, name: str, cache: dict) -> int:
    key = name.strip().lower()
    if key in cache:
        return cache[key]
    row = sconn.execute("SELECT id FROM tags WHERE lower(name) = ?", (key,)).fetchone()
    if row:
        cache[key] = row[0]
        return row[0]
    cur = sconn.execute("INSERT INTO tags (name) VALUES (?)", (name.strip(),))
    tid = cur.lastrowid
    cache[key] = tid
    return tid


def get_or_create_series(sconn, name: str, cache: dict) -> int:
    key = name.strip().lower()
    if key in cache:
        return cache[key]
    row = sconn.execute("SELECT id FROM series WHERE lower(name) = ?", (key,)).fetchone()
    if row:
        cache[key] = row[0]
        return row[0]
    cur = sconn.execute("INSERT INTO series (name) VALUES (?)", (name.strip(),))
    sid = cur.lastrowid
    cache[key] = sid
    return sid


def migrate():
    print("Connecting to Booklore DB...")
    bconn = get_booklore_conn()
    print("Connecting to Scriptorium DB...")
    sconn = get_scriptorium_conn()

    COVERS_PATH.mkdir(parents=True, exist_ok=True)

    # ── Verify there is at least one user ───────────────────────────────────
    user_row = sconn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
    if not user_row:
        print("ERROR: No users in Scriptorium. Create a user first, then run migration.")
        sys.exit(1)
    user_id = user_row[0]
    print(f"Using Scriptorium user_id={user_id}")

    # ── Map Booklore libraries to Scriptorium ────────────────────────────────
    with bconn.cursor() as cur:
        cur.execute("SELECT l.id, l.name, lp.path FROM library l LEFT JOIN library_path lp ON lp.library_id = l.id")
        booklore_libs = {row["id"]: row for row in cur.fetchall()}

    scriptorium_lib_map = {}
    for bl_id, bl_lib in booklore_libs.items():
        name = bl_lib["name"]
        lib_path = bl_lib["path"] or ""
        mount_name = LIBRARY_PATH_MAP.get(lib_path, lib_path.lstrip("/"))
        container_path = f"/data/library/booklore/{mount_name}"

        row = sconn.execute("SELECT id FROM libraries WHERE name = ?", (name,)).fetchone()
        if row:
            scriptorium_lib_map[bl_id] = row[0]
        else:
            cur2 = sconn.execute(
                "INSERT INTO libraries (name, path, is_active, is_hidden, created_at, updated_at) VALUES (?, ?, 1, 0, ?, ?)",
                (name, container_path, now_iso(), now_iso()),
            )
            scriptorium_lib_map[bl_id] = cur2.lastrowid
    sconn.commit()
    print(f"  {len(scriptorium_lib_map)} libraries mapped")

    # ── Load bulk data from Booklore ─────────────────────────────────────────
    print("Loading Booklore data...")
    with bconn.cursor() as cur:
        cur.execute("""
            SELECT b.id, b.library_id, b.added_on,
                   lp.path as lib_path,
                   bm.title, bm.description,
                   bm.isbn_13, bm.isbn_10,
                   bm.published_date, bm.language,
                   bm.series_name, bm.series_number
            FROM book b
            LEFT JOIN library_path lp ON lp.library_id = b.library_id
            LEFT JOIN book_metadata bm ON bm.book_id = b.id
            WHERE b.deleted = 0
            ORDER BY b.id
        """)
        books = cur.fetchall()

    with bconn.cursor() as cur:
        cur.execute("""
            SELECT bam.book_id, a.name
            FROM book_metadata_author_mapping bam
            JOIN author a ON a.id = bam.author_id
        """)
        book_authors_map = {}
        for row in cur.fetchall():
            book_authors_map.setdefault(row["book_id"], []).append(row["name"])

    with bconn.cursor() as cur:
        cur.execute("""
            SELECT btm.book_id, t.name
            FROM book_metadata_tag_mapping btm
            JOIN tag t ON t.id = btm.tag_id
        """)
        book_tags_map = {}
        for row in cur.fetchall():
            book_tags_map.setdefault(row["book_id"], []).append(row["name"])

    with bconn.cursor() as cur:
        cur.execute("""
            SELECT bf.book_id, bf.file_name, bf.file_sub_path,
                   bf.book_type, bf.file_size_kb, lp.path as lib_path
            FROM book_file bf
            JOIN book b ON b.id = bf.book_id
            LEFT JOIN library_path lp ON lp.library_id = b.library_id
            WHERE bf.is_book = 1 AND b.deleted = 0
        """)
        book_files_map = {}
        for row in cur.fetchall():
            book_files_map.setdefault(row["book_id"], []).append(dict(row))

    with bconn.cursor() as cur:
        cur.execute("""
            SELECT book_id, read_status, personal_rating,
                   pdf_progress_percent, epub_progress_percent,
                   cbx_progress_percent, koreader_progress_percent,
                   kobo_progress_percent, last_read_time, date_finished
            FROM user_book_progress
            WHERE user_id = 1
        """)
        book_progress_map = {row["book_id"]: dict(row) for row in cur.fetchall()}

    # ── Get/create migration device ──────────────────────────────────────────
    device_row = sconn.execute("SELECT id FROM devices WHERE name = 'Booklore Import'").fetchone()
    if device_row:
        device_id = device_row[0]
    else:
        cur2 = sconn.execute(
            "INSERT INTO devices (user_id, name, device_type, created_at, updated_at) VALUES (?, 'Booklore Import', 'web', ?, ?)",
            (user_id, now_iso(), now_iso()),
        )
        device_id = cur2.lastrowid
    sconn.commit()

    # ── Import books ─────────────────────────────────────────────────────────
    author_cache = {}
    tag_cache = {}
    series_cache = {}
    imported = 0
    skipped = 0
    no_title = 0
    no_file = 0
    covers_copied = 0

    print(f"Importing {len(books)} books...")
    for bl_book in books:
        bl_id = bl_book["id"]
        title = bl_book["title"]

        if not title:
            no_title += 1
            continue

        # Skip if already present (match on title)
        if sconn.execute("SELECT 1 FROM books WHERE title = ?", (title,)).fetchone():
            skipped += 1
            continue

        lib_id = scriptorium_lib_map.get(bl_book["library_id"])
        book_uuid = str(uuid.uuid4())

        # Copy cover
        cover_hash, cover_format = copy_cover(bl_id, book_uuid)
        if cover_hash:
            covers_copied += 1

        # Insert book
        sconn.execute("""
            INSERT INTO books (
                uuid, library_id, title, description, isbn,
                published_date, language, cover_hash, cover_format,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            book_uuid, lib_id, title,
            bl_book["description"],
            bl_book["isbn_13"] or bl_book["isbn_10"],
            str(bl_book["published_date"]) if bl_book["published_date"] else None,
            bl_book["language"],
            cover_hash, cover_format,
            bl_book["added_on"].isoformat() if bl_book["added_on"] else now_iso(),
            now_iso(),
        ))
        book_id = sconn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Authors
        for aname in book_authors_map.get(bl_id, []):
            if aname:
                aid = get_or_create_author(sconn, aname, author_cache)
                sconn.execute("INSERT OR IGNORE INTO book_authors (book_id, author_id) VALUES (?, ?)", (book_id, aid))

        # Tags
        for tname in book_tags_map.get(bl_id, []):
            if tname:
                tid = get_or_create_tag(sconn, tname, tag_cache)
                sconn.execute("INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?, ?)", (book_id, tid))

        # Series
        sname = bl_book["series_name"]
        if sname:
            sid = get_or_create_series(sconn, sname, series_cache)
            sconn.execute("INSERT OR IGNORE INTO book_series (book_id, series_id) VALUES (?, ?)", (book_id, sid))

        # Files
        lib_path = bl_book["lib_path"] or ""
        files_added = 0
        for bf in book_files_map.get(bl_id, []):
            fp = resolve_file_path(
                bf["lib_path"] or lib_path,
                bf["file_sub_path"] or "",
                bf["file_name"],
            )
            if not fp:
                continue
            fmt = (bf["book_type"] or "").lower()
            size_bytes = (bf["file_size_kb"] or 0) * 1024
            # Use SHA256 of the path as a placeholder hash (fast, unique per path)
            path_hash = hashlib.sha256(fp.encode()).hexdigest()
            sconn.execute("""
                INSERT OR IGNORE INTO book_files (book_id, filename, file_path, format, file_size, file_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (book_id, bf["file_name"], fp, fmt, size_bytes, path_hash, now_iso()))
            files_added += 1
        if files_added == 0:
            no_file += 1

        # Reading progress
        prog = book_progress_map.get(bl_id)
        if prog:
            status_map = {"READ": "completed", "READING": "reading", "UNREAD": "want_to_read", "DNF": "abandoned"}
            status = status_map.get(prog["read_status"] or "UNREAD", "want_to_read")
            pct_vals = [v for v in [
                prog["pdf_progress_percent"],
                prog["epub_progress_percent"],
                prog["cbx_progress_percent"],
                prog["koreader_progress_percent"],
                prog["kobo_progress_percent"],
            ] if v is not None]
            pct = max(pct_vals) if pct_vals else 0.0
            rating = prog["personal_rating"]
            last_read = prog["last_read_time"]
            date_fin = prog["date_finished"]
            sconn.execute("""
                INSERT OR IGNORE INTO read_progress (
                    user_id, book_id, device_id, status, percentage, rating,
                    started_at, completed_at, last_opened, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, book_id, device_id, status, pct, rating,
                last_read.isoformat() if last_read else None,
                date_fin.isoformat() if date_fin else None,
                last_read.isoformat() if last_read else now_iso(),
                now_iso(), now_iso(),
            ))

        imported += 1
        if imported % 250 == 0:
            sconn.commit()
            print(f"  {imported} books imported...")

    sconn.commit()
    bconn.close()
    sconn.close()

    print(f"\n✓ Migration complete!")
    print(f"  Imported:        {imported}")
    print(f"  Skipped (dup):   {skipped}")
    print(f"  No title:        {no_title}")
    print(f"  No file found:   {no_file}")
    print(f"  Covers copied:   {covers_copied}")


if __name__ == "__main__":
    migrate()
