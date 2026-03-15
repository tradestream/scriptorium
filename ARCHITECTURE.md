# Scriptorium — Architecture & Roadmap

## Vision

Scriptorium is a fork of [BookLore](https://github.com/booklore-app/booklore) — a full-featured, self-hosted book library server — rebuilt from the ground up with a modern stack: **SvelteKit + Svelte 5** (frontend) and **FastAPI** (backend). BookLore is the feature blueprint; Scriptorium ports all of its functionality while improving on stability, developer experience, and extensibility.

### Why Fork?

BookLore (Angular 20 + Spring Boot/Java) does everything we want — library management, smart shelves, metadata enrichment, OPDS, Kobo sync, BookDrop auto-ingest, Komga-compatible API, and more. We're converting the stack to technologies we know and can maintain independently, while selectively incorporating the best automation ideas from Calibre-Web-Automated (ingest pipeline, format conversion, duplicate detection) and reading experience patterns from Kavita (reading profiles, annotations, comic support).

### What Carries Over from BookLore

All core features: library scanning, metadata editing/enrichment (Google Books, Open Library, Amazon), smart shelves, Loose Leaves folder watching, OPDS server, Kobo sync, KOReader sync, Komga-compatible API, Kindle email delivery, multi-user with JWT + OIDC, full-text search, grid/table views, reading progress tracking, and Reader DNA statistics.

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | SvelteKit 2 + Svelte 5 (runes) | Reactive, fast, minimal bundle size |
| UI Components | shadcn-svelte + Bits UI + Tailwind CSS 4 | Accessible headless primitives, copy-paste components |
| Backend | FastAPI (Python 3.12+) | Async-first, great DX, rich ecosystem for file processing |
| Database | SQLite (via aiosqlite + SQLAlchemy async) | Zero-config, single-file, perfect for self-hosted |
| ORM | SQLAlchemy 2.0 (async) + Alembic | Mature, async support, migration tooling |
| Task Queue | ARQ (Redis-backed) or Huey (SQLite-backed) | Background jobs for ingest, conversion, metadata |
| File Processing | Calibre CLI (`ebook-convert`, `ebook-meta`) | Industry standard for ebook conversion/metadata |
| Search | SQLite FTS5 | Full-text search with no extra services |
| Auth | JWT (local) + optional OIDC | Simple default, extensible |
| Container | Docker + Docker Compose | Standard self-hosted deployment |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Docker Compose                     │
│                                                       │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────┐ │
│  │   SvelteKit   │   │   FastAPI    │   │  Redis   │ │
│  │   Frontend    │◄──►   Backend    │◄──►  (optional│ │
│  │   :5173       │   │   :8000      │   │  for ARQ)│ │
│  └──────────────┘   └──────┬───────┘   └──────────┘ │
│                             │                         │
│                     ┌───────┴───────┐                 │
│                     │   SQLite DB    │                 │
│                     │  scriptorium.db│                 │
│                     └───────────────┘                 │
│                                                       │
│  Volumes:                                             │
│    /data/library     ← organized book storage         │
│    /data/ingest      ← watched folder for auto-import │
│    /data/config      ← DB, settings, covers cache     │
└─────────────────────────────────────────────────────┘
```

### Communication Pattern

- SvelteKit SSR pages call FastAPI via internal HTTP (server-side)
- Client-side SvelteKit uses FastAPI REST endpoints directly
- WebSocket connection for real-time ingest/conversion progress
- OPDS endpoints served directly by FastAPI

---

## Data Model

### Core Entities

```
Library
  ├── id (PK)
  ├── name
  ├── path (filesystem root)
  ├── type (BOOK | COMIC)
  └── scan_interval

Book
  ├── id (PK)
  ├── library_id (FK → Library)
  ├── title
  ├── sort_title
  ├── description
  ├── isbn, isbn13
  ├── publisher
  ├── publish_date
  ├── language
  ├── page_count
  ├── cover_path
  ├── added_at
  ├── updated_at
  └── file_hash (for duplicate detection)

BookFile
  ├── id (PK)
  ├── book_id (FK → Book)
  ├── format (EPUB, PDF, MOBI, CBR, CBZ, CB7)
  ├── path
  ├── size_bytes
  └── created_at

Author
  ├── id (PK)
  ├── name
  ├── sort_name
  └── bio

BookAuthor (join table)
  ├── book_id (FK)
  ├── author_id (FK)
  └── role (AUTHOR, EDITOR, ILLUSTRATOR, etc.)

Tag
  ├── id (PK)
  └── name

BookTag (join table)

Series
  ├── id (PK)
  ├── name
  └── sort_name

BookSeries (join table)
  ├── book_id (FK)
  ├── series_id (FK)
  └── position (float, for ordering)

Shelf
  ├── id (PK)
  ├── user_id (FK)
  ├── name
  ├── is_smart (boolean)
  └── smart_filter (JSON, for dynamic shelves)

ShelfBook (join table)

User
  ├── id (PK)
  ├── username
  ├── email
  ├── password_hash
  ├── role (ADMIN, USER)
  ├── oidc_subject (nullable)
  └── created_at

ReadProgress
  ├── id (PK)
  ├── user_id (FK)
  ├── book_id (FK)
  ├── book_file_id (FK)
  ├── progress (float 0-1)
  ├── page / position
  ├── device_id
  └── updated_at

Device
  ├── id (PK)
  ├── user_id (FK)
  ├── name
  ├── type (KOBO, KOREADER, OPDS, WEB)
  └── last_sync_at
```

---

## API Design

### REST Endpoints (FastAPI)

```
Auth
  POST   /api/auth/login
  POST   /api/auth/register  (first-user becomes admin)
  POST   /api/auth/refresh
  GET    /api/auth/oidc/callback

Libraries
  GET    /api/libraries
  POST   /api/libraries
  PUT    /api/libraries/{id}
  DELETE /api/libraries/{id}
  POST   /api/libraries/{id}/scan

Books
  GET    /api/books                    (paginated, filterable)
  GET    /api/books/{id}
  PUT    /api/books/{id}               (metadata edit)
  DELETE /api/books/{id}
  GET    /api/books/{id}/cover
  GET    /api/books/{id}/file/{format}  (download)
  POST   /api/books/{id}/convert        (trigger conversion)
  POST   /api/books/upload

Search
  GET    /api/search?q=...             (FTS5 powered)

Authors / Tags / Series
  GET    /api/authors
  GET    /api/authors/{id}/books
  GET    /api/tags
  GET    /api/series
  GET    /api/series/{id}/books

Shelves
  GET    /api/shelves
  POST   /api/shelves
  PUT    /api/shelves/{id}
  POST   /api/shelves/{id}/books       (add books)
  DELETE /api/shelves/{id}/books/{book_id}

Reading Progress
  GET    /api/progress/{book_id}
  PUT    /api/progress/{book_id}

Ingest
  GET    /api/ingest/status
  POST   /api/ingest/trigger
  GET    /api/ingest/history

Device Sync
  POST   /api/sync/kobo/...           (Kobo API compat)
  POST   /api/sync/koreader/...       (KOReader sync)
  GET    /api/sync/devices

OPDS
  GET    /opds/v1.2/catalog
  GET    /opds/v1.2/search
  GET    /opds/v1.2/series/{id}
  GET    /opds/v1.2/authors/{id}

WebSocket
  WS     /ws/events                    (ingest progress, scan status)
```

---

## Key Subsystems

### 1. Auto-Ingest Pipeline

```
/data/ingest/  (watched folder)
      │
      ▼
  File Watcher (watchfiles library)
      │
      ▼
  Format Detection
      │
      ├── Supported? → Queue for processing
      └── Unsupported? → Move to /data/ingest/rejected/
              │
              ▼
      Duplicate Check (file hash + fuzzy title match)
              │
              ├── Duplicate → Log + skip (or configurable merge)
              └── New → Continue
                      │
                      ▼
              Metadata Extraction
              (ebook-meta CLI, or parse OPF/ComicInfo.xml)
                      │
                      ▼
              Metadata Enrichment (optional)
              (Google Books API, Open Library, ComicVine)
                      │
                      ▼
              Format Conversion (if configured)
              (ebook-convert to user's preferred format)
                      │
                      ▼
              File Organization
              (move to /data/library/{Author}/{Title}/)
                      │
                      ▼
              Database Insert + Cover Extraction
                      │
                      ▼
              WebSocket notification → UI updates
```

### 2. OPDS Server

OPDS 1.2 Atom feed support for e-reader compatibility:
- Root catalog with navigation feeds
- Search via OpenSearch descriptor
- Acquisition feeds (direct download links)
- Pagination for large libraries
- HTTP Basic Auth (separate from JWT)

### 3. Kobo Device Sync

Full implementation of the reverse-engineered Kobo store sync protocol, allowing Kobo e-readers to sync their library, reading progress, and bookmarks with Scriptorium.

```
Kobo eReader (Nickel firmware)
      │
      │  Edit .kobo/Kobo/Kobo eReader.conf:
      │  [OneStoreServices]
      │  api_endpoint=https://your-server/kobo/{token}/v1/library/sync
      │
      ▼
  GET /kobo/{token}/v1/initialization
      → Returns endpoint URLs for all operations
      │
      ▼
  GET /kobo/{token}/v1/library/sync
      → Returns books + reading state changes (paginated)
      → Header: X-Kobo-Sync: continue (if more pages)
      → Incremental: only books modified since last sync
      │
      ├── GET /kobo/{token}/v1/library/{uuid}/download/{format}
      │   → Serves EPUB/KEPUB/PDF file to device
      │
      ├── GET /kobo/{token}/v1/library/{uuid}/state
      │   → Returns Kobo-format reading state (StatusInfo, Statistics, Bookmark)
      │
      ├── PUT /kobo/{token}/v1/library/{uuid}/state
      │   → Device reports reading progress → updates KoboBookState + ReadProgress
      │
      └── GET /kobo/{token}/v1/library/tags
          → Maps Scriptorium shelves to Kobo collections
```

**Authentication:** URL-path-based tokens (not headers). Tokens are generated via the management API (`POST /api/v1/kobo/tokens`) and configured on the device. Each token maps to a user.

**Data Models:** `KoboSyncToken` (auth + sync cursor), `KoboBookState` (per-book Kobo-specific state with StatusInfo/Statistics/Bookmark fields). Reading state updates are also synced into the unified `ReadProgress` table for cross-device visibility.

**Management API (JWT-authed):**
- `POST /api/v1/kobo/tokens` — Generate a sync token (returns sync URL for device config)
- `GET /api/v1/kobo/tokens` — List user's tokens
- `DELETE /api/v1/kobo/tokens/{id}` — Revoke a token

**Nginx:** The `/kobo/` location requires large buffer sizes (Kobo devices send large headers) and extended read timeouts for book downloads.

### 3b. Other Device Sync

- **KOReader**: KOReader progress sync API (TODO)
- **Send-to-Device**: Email delivery for Kindle and other e-readers (SMTP config, TODO)

### 4. Reader (Phase 2)

- EPUB: epub.js integration in SvelteKit
- PDF: pdf.js viewer
- Comics: Image viewer with page navigation, double-page spread support
- All readers share progress sync via the ReadProgress API

### 5. Text Extraction Pipeline (epub2md Integration)

High-quality text extraction for LLM analysis, adapted from the epub2md project. The extraction module (`app/services/text_extraction.py`) uses BeautifulSoup + markdownify for structured markdown output, then applies LLM-specific optimizations.

```
Book File on Disk
      │
      ▼
  Format Detection (EPUB > TXT > PDF > MOBI)
      │
      ├── EPUB → BeautifulSoup + markdownify (EnhancedMarkdownConverter)
      │          ├── CSS class heading detection
      │          ├── Style-based heading inference (centered, small-caps)
      │          ├── Image/SVG/comment stripping
      │          └── ATX-style heading output
      │
      ├── PDF  → pypdf page-by-page extraction
      │
      ├── TXT  → Direct UTF-8 read
      │
      └── CBR/CBZ → Metadata summary (image-based)
              │
              ▼
      LLM Optimization Pipeline
      ├── Unicode normalization (smart quotes → straight, em-dashes, etc.)
      ├── Front matter removal (ISBN, copyright, publisher lines)
      ├── TOC section stripping (keep title, skip navigation)
      ├── Footnote simplification (<sup>N</sup> → [N])
      ├── Internal EPUB link cleanup
      ├── Whitespace normalization
      └── Metadata header injection (title, author)
              │
              ▼
      Truncation at paragraph boundary (~200k chars / ~50k tokens)
```

**Dependencies:** `ebooklib`, `beautifulsoup4`, `markdownify`, `pypdf`

**Fallback:** If markdownify is not installed, falls back to plain HTML text extraction via Python's built-in HTMLParser.

### 6. LLM-Powered Book Analysis

AI-generated literary and analytical insights, stored per-book. Pluggable LLM backend.

```
User clicks "Analyze" on book detail page
      │
      ▼
  Template Selection
  (Literary / Non-Fiction / Esoteric Reading / Custom)
      │
      ▼
  Text Extraction (via text_extraction module, see above)
      │
      ▼
  LLM Provider
  ├── Anthropic Claude API (default)
  ├── Ollama (fully offline, local models)
  └── OpenAI-compatible (OpenAI, Together, Groq, etc.)
      │
      ▼
  Analysis stored in DB (BookAnalysis table)
  → Viewable on book detail page with expand/collapse
  → Markdown rendered, token count tracked
```

**Built-in Templates:**
- **Literary Analysis** — Plot structure, character arcs, themes & symbolism, narrative technique, emotional layer, philosophical questions, multi-layer summaries, discussion questions. Best for fiction.
- **Non-Fiction Analysis** — Central thesis, structural breakdown, key concepts & frameworks, actionable insights, critical thinking, knowledge graphs. Best for non-fiction and textbooks.
- **Esoteric Reading** — Two-layer (exoteric/esoteric) analysis based on Arthur Melzer and Leo Strauss. Detects loud silences, intentional contradictions, protective rhetoric, structural esotericism, speech vs. deed analysis, and the double doctrine. Best for classical, philosophical, and literary texts.
- **Custom templates** — Users can create and save their own prompt templates with `{text}` placeholder.

**Configuration:** Set `LLM_PROVIDER` and the relevant API key in `.env`. Ollama requires no API key (runs locally).

### 7. Computational Esoteric Analysis

Four Python-based analytical tools for detecting patterns of esoteric writing, complementing the LLM-based Esoteric Reading template. No external NLP dependencies — uses built-in lexicons and regex.

```
Book Text (extracted via text_extraction module)
      │
      ▼
  Auto-segment by structural markers
  (Book/Chapter/Canto/Part/Act/Section headers)
  Falls back to ~50-line chunks if no pattern found
      │
      ├── Tool 1: Loud Silence Detector
      │   Track keyword frequency per section. Flag sections where
      │   a keyword drops below silence_threshold × average frequency.
      │   Reveals strategic omissions.
      │
      ├── Tool 2: Contradiction Hunter
      │   Track entity sentiment using built-in positive/negative word lists.
      │   Identify sections where an entity's sentiment shifts dramatically.
      │   Reveals intentional contradictions.
      │
      ├── Tool 3: Center Locator
      │   Find the physical center of the full text and each section.
      │   Extract passage windows around center points.
      │   Classical texts often hide their core teaching at the center.
      │
      └── Tool 4: Exoteric/Esoteric Ratio Analyzer
          Measure pious word density vs. subversive word density per section.
          Flag sections with unusual ratios (>1.8× average).
          Default lexicons: 32 pious words, 34 subversive words.
              │
              ▼
      Results stored in ComputationalAnalysis table (JSON)
      → Viewable on book detail page with heatmaps, bar charts, passage highlights
```

**API Endpoints:**
- `GET /api/v1/books/{id}/esoteric` — List all computational analyses
- `POST /api/v1/books/{id}/esoteric` — Run analysis (types: full, loud_silence, contradiction, center, exoteric_esoteric)
- `GET /api/v1/books/{id}/esoteric/{analysis_id}` — Get specific analysis
- `DELETE /api/v1/books/{id}/esoteric/{analysis_id}` — Delete analysis

**Frontend:** `EsotericAnalysis.svelte` component with configurable keywords, entities, analysis type selector, and rich result visualization (heatmap tables, sentiment charts, center passage display, stacked ratio bars).

### 8. Hidden Libraries

Libraries can be marked `is_hidden` to exclude them from the dashboard, suggestions, and default book listings, while keeping them accessible in the sidebar and via direct URL. Useful for reference collections, archives, or content you want to keep indexed but not front-and-center.

- Sidebar shows all libraries (hidden ones have reduced opacity + eye-off icon)
- Dashboard and "recently added" exclude hidden libraries by default
- `/api/v1/libraries?include_hidden=true` includes them
- `/api/v1/books` excludes books from hidden libraries unless `include_hidden=true` or a specific `library_id` is passed

---

## Project Structure

```
scriptorium/
├── frontend/                    # SvelteKit application
│   ├── src/
│   │   ├── lib/
│   │   │   ├── components/      # Reusable Svelte 5 components
│   │   │   ├── stores/          # Svelte stores (runes)
│   │   │   ├── api/             # API client functions
│   │   │   ├── types/           # TypeScript interfaces
│   │   │   └── utils/           # Helpers
│   │   ├── routes/
│   │   │   ├── (app)/           # Authenticated layout group
│   │   │   │   ├── +layout.svelte
│   │   │   │   ├── library/[id]/
│   │   │   │   ├── book/[id]/
│   │   │   │   ├── shelves/
│   │   │   │   ├── search/
│   │   │   │   └── settings/
│   │   │   ├── auth/
│   │   │   │   ├── login/
│   │   │   │   └── register/
│   │   │   ├── reader/[id]/     # Book reader (Phase 2)
│   │   │   └── +layout.svelte
│   │   └── app.html
│   ├── static/
│   ├── svelte.config.js
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   └── package.json
│
├── backend/                     # FastAPI application
│   ├── app/
│   │   ├── main.py              # FastAPI app factory
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # SQLAlchemy async engine
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── book.py
│   │   │   ├── library.py
│   │   │   ├── user.py
│   │   │   ├── shelf.py
│   │   │   ├── progress.py
│   │   │   └── analysis.py         # BookAnalysis, AnalysisTemplate
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   │   ├── book.py
│   │   │   ├── library.py
│   │   │   ├── user.py
│   │   │   └── ...
│   │   ├── api/                 # Route handlers
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── books.py
│   │   │   ├── libraries.py
│   │   │   ├── shelves.py
│   │   │   ├── search.py
│   │   │   ├── opds.py
│   │   │   ├── sync.py              # KOReader + generic device sync
│   │   │   ├── kobo.py             # Kobo device sync + management endpoints
│   │   │   ├── ingest.py
│   │   │   └── analysis.py         # Book analysis + template CRUD
│   │   ├── services/            # Business logic
│   │   │   ├── ingest.py        # Auto-ingest pipeline
│   │   │   ├── metadata.py      # Metadata extraction/enrichment
│   │   │   ├── conversion.py    # Format conversion (Calibre CLI)
│   │   │   ├── covers.py        # Cover extraction/caching
│   │   │   ├── search.py        # FTS5 search
│   │   │   ├── opds.py          # OPDS feed generation
│   │   │   ├── kobo_sync.py     # Kobo sync protocol service
│   │   │   ├── llm.py           # LLM provider abstraction (Anthropic/Ollama/OpenAI)
│   │   │   ├── text_extraction.py # epub2md-based text extraction + LLM optimization
│   │   │   ├── esoteric.py      # Computational esoteric analysis (4 tools)
│   │   │   └── analysis.py      # LLM analysis orchestration + templates
│   │   ├── tasks/               # Background job definitions
│   │   │   ├── ingest_worker.py
│   │   │   ├── scan_worker.py
│   │   │   └── metadata_worker.py
│   │   └── utils/
│   │       ├── files.py
│   │       ├── hashing.py
│   │       └── calibre.py       # Calibre CLI wrapper
│   ├── alembic/                 # Database migrations
│   │   ├── env.py
│   │   └── versions/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
│
├── docker/
│   ├── Dockerfile.frontend
│   ├── Dockerfile.backend
│   └── nginx.conf               # Reverse proxy config
│
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── LICENSE                      # AGPL-3.0
└── README.md
```

---

## Development Roadmap

### Phase 0 — Foundation (Weeks 1-2)
- [x] Project scaffold (SvelteKit + FastAPI + Docker)
- [ ] Database models + Alembic migrations
- [ ] User auth (JWT, register/login)
- [ ] Library CRUD (create, list, delete)
- [ ] Basic book model and file upload
- [ ] Cover extraction (from EPUB/CBZ metadata)
- [ ] Docker Compose for dev (hot-reload both services)

### Phase 1 — Core Library (Weeks 3-5)
- [ ] Library scanning (walk filesystem, parse metadata)
- [ ] Metadata extraction from files (ebook-meta, OPF, ComicInfo.xml)
- [ ] Book grid + list views with pagination
- [ ] Book detail page (metadata display, file list, cover)
- [ ] Author / Series / Tag browsing
- [ ] Full-text search (FTS5)
- [ ] Metadata editor (edit title, authors, tags, series)
- [ ] Shelves (static collections)

### Phase 2 — Auto-Ingest Pipeline (Weeks 6-8)
- [ ] Folder watcher (watchfiles)
- [ ] Ingest queue with background processing
- [ ] Duplicate detection (hash + fuzzy match)
- [ ] Metadata enrichment (Google Books, Open Library)
- [ ] Format conversion via Calibre CLI
- [ ] File organization (move to library structure)
- [ ] Ingest history + status dashboard
- [ ] Smart shelves (rule-based dynamic collections)

### Phase 3 — Device Sync & OPDS (Weeks 9-11)
- [ ] OPDS 1.2 catalog server
- [ ] OPDS search + pagination
- [ ] HTTP Basic Auth for OPDS
- [ ] Kobo sync protocol
- [ ] KOReader progress sync
- [ ] Send-to-Kindle / email delivery
- [ ] Device management UI
- [ ] Reading progress tracking API

### Phase 4 — Reader & Polish (Weeks 12-14)
- [ ] EPUB reader (epub.js)
- [ ] PDF viewer (pdf.js)
- [ ] Comic reader (image viewer, page navigation)
- [ ] Reader progress sync (auto-save position)
- [ ] Reading statistics
- [ ] Dark mode / theme support
- [ ] Mobile-responsive layout polish
- [ ] Settings page (conversion prefs, ingest rules, SMTP config)

### Phase 5 — Hardening (Weeks 15-16)
- [ ] OIDC authentication support
- [ ] Rate limiting + security headers
- [ ] Backup/restore (DB + config export)
- [ ] Health check endpoint
- [ ] Logging + error handling polish
- [ ] Documentation (user guide, API docs)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] First tagged release

---

## Design Principles

1. **Stability over features** — Ship fewer things that work perfectly
2. **Offline-first** — Everything works without internet; metadata enrichment is optional
3. **Single-binary mindset** — Minimal external dependencies (SQLite, no Redis required for basic use)
4. **Respect the filesystem** — Never modify original files without explicit user action
5. **Progressive enhancement** — Core works without JS; reader and real-time features layer on top
