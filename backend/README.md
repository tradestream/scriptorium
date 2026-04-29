# Scriptorium Backend

Self-hosted book and comics library server with FastAPI.

## Features

- User authentication with JWT tokens
- Book library management with metadata
- Comic book support (CBZ format)
- Reading progress tracking across devices
- Personal bookshelves and collections
- Full-text search with SQLite FTS5
- OPDS 1.2 catalog for e-reader compatibility
- Device sync support (Kobo, KOReader, Calibre)
- File format conversion via Calibre CLI
- Cover extraction and thumbnail generation
- Text-to-speech in the EPUB reader (Web Speech, local mlx-audio, Qwen via DashScope, ElevenLabs) — see [docs/tts-setup.md](../docs/tts-setup.md)

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app factory with lifespan
│   ├── config.py            # Settings via pydantic-settings
│   ├── database.py          # AsyncSQLAlchemy setup
│   ├── models/              # SQLAlchemy 2.0 models
│   │   ├── book.py          # Book, Author, Tag, Series models
│   │   ├── library.py       # Library model
│   │   ├── user.py          # User authentication model
│   │   ├── shelf.py         # Shelf/collection model
│   │   └── progress.py      # Reading progress tracking
│   ├── schemas/             # Pydantic schemas
│   │   ├── book.py
│   │   ├── library.py
│   │   ├── user.py
│   │   ├── shelf.py
│   │   └── progress.py
│   ├── api/                 # API endpoints
│   │   ├── auth.py          # Login, register, JWT
│   │   ├── books.py         # Book CRUD + cover/download
│   │   ├── libraries.py     # Library CRUD + scan
│   │   ├── shelves.py       # Shelf management
│   │   ├── search.py        # Full-text search
│   │   ├── ingest.py        # File ingestion pipeline
│   │   ├── opds.py          # OPDS 1.2 catalog
│   │   └── sync.py          # Device sync stubs
│   ├── services/            # Business logic
│   │   ├── auth.py          # JWT + password hashing
│   │   ├── ingest.py        # File watcher + pipeline
│   │   ├── metadata.py      # Metadata extraction
│   │   ├── conversion.py    # Calibre wrapper
│   │   ├── covers.py        # Cover processing
│   │   └── search.py        # FTS5 search
│   └── utils/               # Utilities
│       ├── files.py         # File hashing, format detection
│       └── calibre.py       # Calibre CLI subprocess
├── alembic/                 # Database migrations
│   ├── env.py               # Async migration support
│   └── versions/            # Migration files
├── pyproject.toml           # Project dependencies
├── Dockerfile               # Multi-stage Docker build
└── alembic.ini              # Alembic configuration
```

## Quick Start

### Prerequisites

- Python 3.11+
- SQLite 3.35+ (for FTS5)
- Calibre CLI tools (for format conversion)
- pip or uv

### Installation

1. Clone the repository and navigate to the backend directory
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -e .
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Initialize the database:
   ```bash
   python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"
   ```

6. Run the development server:
   ```bash
   uvicorn app.main:app --reload
   ```

The API will be available at `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login with credentials
- `GET /api/v1/auth/me` - Get current user profile

### Books
- `GET /api/v1/books` - List books (with pagination/filtering)
- `GET /api/v1/books/{id}` - Get book details
- `POST /api/v1/books` - Create book (admin only)
- `PUT /api/v1/books/{id}` - Update book (admin only)
- `DELETE /api/v1/books/{id}` - Delete book (admin only)
- `GET /api/v1/books/{id}/cover` - Download book cover
- `GET /api/v1/books/{id}/download/{file_id}` - Download book file

### Libraries
- `GET /api/v1/libraries` - List all libraries
- `GET /api/v1/libraries/{id}` - Get library details
- `POST /api/v1/libraries` - Create library (admin only)
- `PUT /api/v1/libraries/{id}` - Update library (admin only)
- `DELETE /api/v1/libraries/{id}` - Delete library (admin only)
- `POST /api/v1/libraries/{id}/scan` - Trigger library scan (admin only)

### Shelves
- `GET /api/v1/shelves` - List user's shelves
- `GET /api/v1/shelves/{id}` - Get shelf details
- `POST /api/v1/shelves` - Create shelf
- `PUT /api/v1/shelves/{id}` - Update shelf
- `DELETE /api/v1/shelves/{id}` - Delete shelf
- `POST /api/v1/shelves/{id}/books` - Add book to shelf
- `DELETE /api/v1/shelves/{id}/books/{book_id}` - Remove book from shelf

### Search
- `GET /api/v1/search?q=query` - Full-text search books

### Ingest
- `GET /api/v1/ingest/status` - Get ingest pipeline status
- `POST /api/v1/ingest/trigger` - Manually trigger ingest
- `GET /api/v1/ingest/history` - Get ingest history

### OPDS & Sync
- `GET /api/v1/opds/` - OPDS 1.2 root feed
- `GET /api/v1/opds/search` - OPDS search
- `POST /api/v1/sync/kobo/sync` - Kobo device sync
- `POST /api/v1/sync/koreader/sync` - KOReader app sync

## Database Models

### User
- ID, username, email
- Password (bcrypt hashed)
- Admin flag, active status
- Timestamps

### Book
- ID, UUID, title, description
- ISBN, language, published date
- Cover hash/format
- Library association
- Authors, tags, series (many-to-many)
- Files (EPUB, PDF, CBZ, etc.)

### Library
- ID, name, description, path
- Active status, last scanned timestamp
- Book collection

### Shelf
- ID, user association, name, description
- Book collection with position tracking

### ReadProgress
- ID, user, book, device
- Current page, percentage, status (reading/completed/abandoned)
- Timestamps (started, completed, last opened)

### Device
- ID, user, device type (kobo, koreader, etc.)
- Last synced timestamp

## Configuration

All settings are managed via environment variables (see `.env.example`):

- `DATABASE_URL` - SQLAlchemy connection string
- `LIBRARY_PATH` - Base directory for book libraries
- `INGEST_PATH` - Directory for ingesting new books
- `CONFIG_PATH` - Configuration directory
- `COVERS_PATH` - Cover image storage directory
- `SECRET_KEY` - JWT signing key
- `JWT_ALGORITHM` - Token algorithm (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token lifetime (default: 1440)
- `CALIBRE_PATH` - Calibre executable directory (default: /usr/bin)
- `CORS_ORIGINS` - CORS allowed origins (JSON list)

## Development

### Running Tests
```bash
pip install -e ".[dev]"
pytest
```

### Code Quality
```bash
black app/
ruff check app/
mypy app/
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

## TODO Items

The following features are marked with `TODO` comments and ready for implementation:

1. **File Ingestion**
   - File watcher for ingest directory
   - Format detection and routing
   - Automatic metadata extraction

2. **Metadata Extraction**
   - EPUB metadata parsing
   - PDF metadata extraction
   - CBZ comic metadata
   - Google Books API enrichment
   - Open Library API enrichment

3. **Cover Processing**
   - Cover extraction from EPUB
   - Cover extraction from PDF
   - Cover extraction from CBZ
   - Thumbnail generation

4. **Format Conversion**
   - Calibre CLI integration
   - Error handling
   - Conversion result caching

5. **Full-Text Search**
   - FTS5 virtual table setup
   - Query optimization
   - Result ranking

6. **OPDS Catalog**
   - Atom feed generation
   - Search results feed
   - Pagination support

7. **Device Sync**
   - Kobo sync protocol
   - KOReader sync
   - Calibre Content Server compatibility

8. **Real-Time Events**
   - WebSocket event streaming
   - Ingest progress notifications
   - Reading progress sync

## Docker

Build and run with Docker:

```bash
docker build -t scriptorium-backend .
docker run -p 8000:8000 -v scriptorium-data:/app/data scriptorium-backend
```

## Security Notes

- Change `SECRET_KEY` in production
- Enable HTTPS/TLS in reverse proxy
- Use strong passwords
- First registered user becomes admin
- Admin-only endpoints require auth token
- File paths are validated against directory traversal

## Performance Considerations

- SQLite with WAL mode for better concurrency
- Connection pooling with async sessions
- Query optimization with joinedload()
- FTS5 for efficient full-text search
- Cover caching with file hashing

## Contributing

This is a scaffold with working CRUD operations and authentication. Additional features should be implemented following the existing patterns and TODO comments throughout the codebase.

## License

MIT
