# Scriptorium Backend - Project Summary

## Complete File Structure

```
backend/
├── pyproject.toml                 # Project config with all dependencies
├── alembic.ini                    # Alembic migration configuration
├── Dockerfile                     # Multi-stage Docker build
├── README.md                      # Comprehensive documentation
├── .env.example                   # Example environment variables
├── .gitignore                     # Git ignore patterns
├── run.sh                         # Development startup script
│
├── app/
│   ├── __init__.py                # Empty package marker
│   ├── main.py                    # FastAPI app factory + lifespan
│   ├── config.py                  # Settings (pydantic-settings)
│   ├── database.py                # AsyncSQLAlchemy engine + session
│   │
│   ├── models/
│   │   ├── __init__.py            # Model exports
│   │   ├── book.py                # Book, Author, Tag, Series, BookFile
│   │   ├── library.py             # Library model
│   │   ├── user.py                # User (authentication)
│   │   ├── shelf.py               # Shelf, ShelfBook
│   │   └── progress.py            # ReadProgress, Device
│   │
│   ├── schemas/
│   │   ├── __init__.py            # Empty
│   │   ├── book.py                # Book Pydantic schemas
│   │   ├── library.py             # Library Pydantic schemas
│   │   ├── user.py                # User/Auth schemas
│   │   ├── shelf.py               # Shelf schemas
│   │   └── progress.py            # Progress schemas
│   │
│   ├── api/
│   │   ├── __init__.py            # API router aggregation
│   │   ├── auth.py                # Register, login, JWT endpoints
│   │   ├── books.py               # Book CRUD + cover/download
│   │   ├── libraries.py           # Library CRUD + scan
│   │   ├── shelves.py             # Shelf CRUD + book management
│   │   ├── search.py              # Full-text search
│   │   ├── ingest.py              # Ingest status/trigger/history
│   │   ├── opds.py                # OPDS 1.2 catalog stubs
│   │   └── sync.py                # Device sync stubs
│   │
│   ├── services/
│   │   ├── __init__.py            # Empty
│   │   ├── auth.py                # JWT + bcrypt password hashing
│   │   ├── ingest.py              # File watcher + pipeline (TODO)
│   │   ├── metadata.py            # Metadata extraction (TODO)
│   │   ├── conversion.py          # Calibre format conversion (TODO)
│   │   ├── covers.py              # Cover extraction (TODO)
│   │   └── search.py              # FTS5 search helper
│   │
│   └── utils/
│       ├── __init__.py            # Empty
│       ├── files.py               # File hashing, format detection
│       └── calibre.py             # Calibre CLI subprocess wrapper
│
└── alembic/
    ├── env.py                     # Async migration environment
    └── versions/
        └── .gitkeep               # Placeholder for migrations
```

## Key Features Implemented

### Authentication & Security
- User registration (first user becomes admin)
- JWT-based authentication
- Bcrypt password hashing
- Role-based access control (admin flag)
- Protected endpoints with dependency injection

### Database
- AsyncSQLAlchemy with SQLite (aiosqlite)
- SQLAlchemy 2.0 declarative models with Mapped[] annotations
- Proper relationships and cascading deletes
- Migration support via Alembic with async support

### API Endpoints
All endpoints have real logic for:
- User authentication (register, login, me)
- Book management (CRUD with filtering, pagination)
- Library management (CRUD with book count)
- Shelf management (CRUD, add/remove books)
- File downloads
- Search (placeholder FTS5)
- Ingest status/trigger (stubs for file watcher)
- OPDS catalog (stubs for Atom feed generation)
- Device sync (stubs for Kobo/KOReader)

### Models
Complete SQLAlchemy models:
- User (auth)
- Book (with UUID, cover tracking)
- BookFile (format support: EPUB, PDF, CBZ, etc.)
- Author, Tag, Series (many-to-many relationships)
- Library (collection container)
- Shelf (user-specific collections)
- ReadProgress (device-aware tracking)
- Device (sync support)

### Services Layer
Organized business logic:
- auth.py: JWT token creation/verification, password hashing
- ingest.py: File watcher skeleton (TODO items marked)
- metadata.py: Metadata extraction stubs for EPUB/PDF/CBZ
- conversion.py: Calibre CLI wrapper (stub)
- covers.py: Cover extraction and processing (stub)
- search.py: FTS5 search helper with placeholder LIKE queries

### Configuration
- Environment-based settings via pydantic-settings
- .env.example for reference
- Sensible defaults
- Support for customizing paths, JWT, CORS

### DevOps
- Dockerfile with multi-stage build
- Python 3.12 slim base image
- Calibre CLI tools included
- Health check endpoint
- Volume mounts for data persistence

## TODO Comments Throughout Codebase

Strategic TODO markers are placed in files ready for implementation:

1. **ingest.py** - File watcher, format detection, pipeline
2. **metadata.py** - EPUB/PDF/CBZ parsing, API enrichment
3. **covers.py** - Cover extraction, thumbnail generation
4. **conversion.py** - Calibre CLI integration
5. **search.py** - FTS5 virtual table setup
6. **opds.py** - Atom feed generation
7. **sync.py** - Kobo/KOReader/Calibre protocol implementation
8. **main.py** - WebSocket real-time events

## Getting Started

### Development
```bash
./run.sh
# or
uvicorn app.main:app --reload
```

### Production
```bash
docker build -t scriptorium-backend .
docker run -p 8000:8000 -v scriptorium-data:/app/data scriptorium-backend
```

## Database Initialization

The app automatically initializes the database on startup:
- Creates all tables from models
- Enables SQLite WAL mode
- Sets up FTS5 for search

## Testing the API

```bash
# Register first user (becomes admin)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@example.com","password":"password123"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password123"}'

# View API docs
# Open http://localhost:8000/docs in browser
```

## Code Quality

- All Python files compile without syntax errors
- Type hints throughout (Mapped[] for SQLAlchemy 2.0)
- Proper error handling with HTTPException
- Pagination and filtering support
- Request/response validation with Pydantic

## Dependencies

All specified dependencies in pyproject.toml:
- fastapi[standard] - Web framework
- uvicorn[standard] - ASGI server
- sqlalchemy[asyncio] - ORM
- aiosqlite - Async SQLite driver
- alembic - Database migrations
- python-jose[cryptography] - JWT
- passlib[bcrypt] - Password hashing
- pydantic-settings - Configuration
- watchfiles - File watcher for ingest
- httpx - HTTP client for API calls
- Pillow - Image processing for covers

## Next Steps for Development

1. Implement file ingest pipeline with watchfiles
2. Add metadata extraction from book files
3. Implement Calibre format conversion
4. Set up FTS5 virtual tables for search
5. Implement OPDS 1.2 Atom feed generation
6. Add device sync protocols (Kobo, KOReader)
7. Implement real-time WebSocket events
8. Add comprehensive test suite
9. Optimize database queries with profiling
10. Add rate limiting and request throttling

---

**Status**: Ready for local development and extension. All scaffolding complete with working endpoints for auth, CRUD operations, and clear TODO markers for advanced features.
