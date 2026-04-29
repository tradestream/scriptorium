# Shelfmark integration

[Shelfmark](https://github.com/calibrain/shelfmark) is a self-hosted multi-source book / audiobook discovery and download tool. It complements Scriptorium cleanly because the two responsibilities don't overlap:

| | Shelfmark | Scriptorium |
|---|---|---|
| **What it does** | Search across web / torrent / usenet / IRC sources, request, download | Catalog, read, sync to devices, analyze |
| **Outputs** | EPUB / PDF / etc. files dropped into a "books" folder | Reading state, marginalia, esoteric analysis, OPDS, Kobo sync |
| **Codebase** | Python + TypeScript, separate repo | Python + SvelteKit, this repo |

The two run as **separate Docker containers sharing one filesystem path** — Shelfmark writes downloads to its `/books` mount, Scriptorium watches the same host directory as `/data/ingest` and auto-imports anything that lands there. There is no Python or JS coupling; either side can be swapped out independently.

## Setup

### 1. Pick the host path

Choose a directory on the host that both containers will mount. The natural choice is your existing Scriptorium ingest folder:

| Deployment | Host path |
|---|---|
| Local dev (`docker-compose.yml`) | `/Volumes/docker/scriptorium/data/ingest` |
| NAS prod (`docker-compose.nas.yml`) | `/volume1/docker/scriptorium/data/ingest` |

### 2. Edit `docker-compose.shelfmark.yml`

The override file lives at the repo root. Update the `/books` mount line so the host side matches the path you picked above. Default is the NAS prod path:

```yaml
volumes:
  - /volume1/docker/scriptorium/data/ingest:/books   # ← edit this
  - /volume1/docker/shelfmark/config:/config         # ← Shelfmark's own config dir
```

### 3. Start with the override

Layer the Shelfmark service onto your existing compose file:

```bash
# Local dev
docker compose -f docker-compose.yml -f docker-compose.shelfmark.yml up

# NAS prod
docker compose -f docker-compose.nas.yml -f docker-compose.shelfmark.yml up -d
```

Shelfmark serves at `http://<host>:8084` once healthy.

### 4. (Optional) Surface a Discover link in Scriptorium's sidebar

Set `PUBLIC_SHELFMARK_URL` in your **frontend** env (this is read by SvelteKit at build / runtime, not by the backend):

```
# frontend/.env or wherever you build
PUBLIC_SHELFMARK_URL=http://localhost:8084
# Or behind a reverse proxy:
# PUBLIC_SHELFMARK_URL=https://discover.your-domain.com
```

The sidebar will render a **Discover** entry that opens Shelfmark in a new tab. Rebuild or restart the frontend to pick up the change.

If you don't set the env, no link is rendered — Shelfmark is reachable directly at its own URL like any other Docker service.

## How a download flows end-to-end

1. User opens Scriptorium, clicks **Discover** in the sidebar → opens Shelfmark in a new tab.
2. User searches in Shelfmark, requests a book, the configured download client fetches it.
3. Shelfmark drops the finished file at `/books/whatever.epub` (its container path).
4. The host filesystem now has the file at the shared path, e.g. `/volume1/docker/scriptorium/data/ingest/whatever.epub`.
5. Scriptorium's `IngestService` watcher (`watchfiles` against `/data/ingest`) sees the new file within ~1s.
6. `_ingest_file` hashes it, looks for duplicates, computes metadata, creates `Edition` + `EditionFile` rows, runs auto-enrichment, generates a markdown cache, and moves the file to the configured `INGEST_DEFAULT_LIBRARY` (`Books` by default).
7. The book appears in Scriptorium's catalog and is immediately readable / syncable.

## What this integration deliberately doesn't do

- **No shared auth.** Shelfmark has its own login (or OIDC, or proxy auth, etc. — see Shelfmark docs); Scriptorium has its own JWT auth. If you want SSO across both, plug them into a shared OIDC provider (Authelia, Authentik, etc.).
- **No code dependency.** Scriptorium doesn't import Shelfmark code, doesn't shell out to Shelfmark, doesn't poll Shelfmark's API. The only contract is the shared filesystem path.
- **No per-user request workflow.** Shelfmark's request-approval flow stays in Shelfmark. If you want admin-gated downloads, configure that there.

## When to *not* use Shelfmark

- You only ever drop books into ingest manually — Scriptorium's own admin UI already supports drag-and-drop upload (Loose Leaves) and an import API.
- You're worried about source legality. Shelfmark is a tool; what you point it at is your responsibility. Scriptorium has nothing to say about that side.

## Troubleshooting

**Shelfmark downloads but Scriptorium never picks them up.** Check the host path on both compose files matches exactly. Run `ls -la /volume1/docker/scriptorium/data/ingest` from the host (not from inside a container) and confirm new downloads land there. If they don't, your Shelfmark `/books` mount is pointing somewhere else.

**Files appear in ingest but get rejected with "Unsupported format".** Scriptorium's accepted extensions are listed in `backend/app/services/scanner.py:BOOK_EXTENSIONS`. Shelfmark may pull formats Scriptorium doesn't yet handle — those just sit in ingest.

**Permission denied writing to `/books`.** Shelfmark's `PUID` / `PGID` env must own the host directory. Default is `1000:1000`; adjust to match your NAS user.
