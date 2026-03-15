# Scriptorium Backend - Index & Quick Reference

## Quick Navigation

### Getting Started
- **README.md** - Complete setup guide and API documentation
- **run.sh** - Start development server with: `./run.sh`
- **.env.example** - Copy and customize for your environment

### Documentation
- **PROJECT_SUMMARY.md** - Architecture and feature overview
- **FILE_MANIFEST.txt** - Complete file listing and feature checklist
- **VERIFICATION_REPORT.md** - QA verification and testing guide
- **This file** - Quick reference and navigation

## Core Application Files

### Entry Point
- **app/main.py** - FastAPI factory, lifespan management, WebSocket stub

### Configuration & Database
- **app/config.py** - Environment-based settings
- **app/database.py** - AsyncSQLAlchemy setup, session management

### Data Layer
- **app/models/** - SQLAlchemy 2.0 ORM models
  - book.py - Books, files, authors, tags, series
  - library.py - Library containers
  - user.py - User authentication
  - shelf.py - User collections
  - progress.py - Reading progress tracking

- **app/schemas/** - Pydantic validation schemas
  - book.py - Book CRUD schemas
  - library.py - Library CRUD schemas
  - user.py - Auth and user schemas
  - shelf.py - Shelf schemas
  - progress.py - Progress schemas

### API Layer
- **app/api/** - REST API endpoints
  - auth.py - User registration, login, JWT
  - books.py - Book CRUD, filtering, cover, download
  - libraries.py - Library management, scanning
  - shelves.py - Personal collections
  - search.py - Full-text search
  - ingest.py - File ingest interface
  - opds.py - OPDS 1.2 catalog stub
  - sync.py - Device sync stubs

### Business Logic
- **app/services/** - Service layer
  - auth.py - JWT and password utilities
  - ingest.py - File watcher pipeline (TODO)
  - metadata.py - Metadata extraction (TODO)
  - covers.py - Cover processing (TODO)
  - conversion.py - Format conversion (TODO)
  - search.py - FTS5 search helper

### Utilities
- **app/utils/** - Helper utilities
  - files.py - File operations (hashing, format detection)
  - calibre.py - Calibre CLI wrapper

## API Endpoints Quick Reference

### Authentication
```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
GET    /api/v1/auth/me
```

### Books (CRUD)
```
GET    /api/v1/books              (list with filtering, pagination)
GET    /api/v1/books/{id}         (get one)
POST   /api/v1/books              (create, admin only)
PUT    /api/v1/books/{id}         (update, admin only)
DELETE /api/v1/books/{id}         (delete, admin only)
GET    /api/v1/books/{id}/cover   (get cover)
GET    /api/v1/books/{id}/download/{file_id}  (download file)
```

### Libraries
```
GET    /api/v1/libraries          (list all)
GET    /api/v1/libraries/{id}     (get one)
POST   /api/v1/libraries          (create, admin only)
PUT    /api/v1/libraries/{id}     (update, admin only)
DELETE /api/v1/libraries/{id}     (delete, admin only)
POST   /api/v1/libraries/{id}/scan (trigger scan, admin only)
```

### Shelves
```
GET    /api/v1/shelves            (list user's shelves)
GET    /api/v1/shelves/{id}       (get one)
POST   /api/v1/shelves            (create)
PUT    /api/v1/shelves/{id}       (update)
DELETE /api/v1/shelves/{id}       (delete)
POST   /api/v1/shelves/{id}/books (add book)
DELETE /api/v1/shelves/{id}/books/{book_id} (remove book)
```

### Other
```
GET    /api/v1/search?q=query     (full-text search)
GET    /api/v1/ingest/status      (ingest status)
POST   /api/v1/ingest/trigger     (manually trigger ingest)
GET    /api/v1/ingest/history     (ingest history)
GET    /api/v1/opds/              (OPDS catalog root)
GET    /api/v1/opds/search        (OPDS search)
POST   /api/v1/sync/kobo/sync     (Kobo sync)
POST   /api/v1/sync/koreader/sync (KOReader sync)
GET    /health                     (health check)
WS     /ws/events                  (WebSocket events stub)
```

## Database Models

### User
- id, username, email, hashed_password
- is_admin, is_active
- created_at, updated_at

### Book
- id, uuid, title, description
- isbn, language, published_date
- cover_hash, cover_format
- library_id (FK)
- authors (M2M), tags (M2M), series (M2M)
- files (1-M)

### BookFile
- id, filename, format
- file_path, file_hash, file_size
- book_id (FK)

### Library
- id, name, description, path
- is_active, last_scanned
- books (1-M)

### Shelf
- id, user_id (FK), name, description
- books (M2M with position)

### ReadProgress
- id, user_id, book_id, device_id (FKs)
- current_page, percentage, status
- started_at, completed_at, last_opened

### Device
- id, user_id, name, device_type
- last_synced

### Author, Tag, Series
- id, name, description
- Books (M2M relationships)

## Development Workflow

### Setup
```bash
cd /sessions/stoic-exciting-ritchie/mnt/scriptorium/scriptorium/backend
./run.sh
```

### Access Services
- **API**: http://localhost:8000/api/v1/...
- **Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Create User
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@example.com","password":"password123"}'
```

### Get Token
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password123"}'
```

### Make Authenticated Request
```bash
TOKEN="your_token_here"
curl -X GET http://localhost:8000/api/v1/books \
  -H "Authorization: Bearer $TOKEN"
```

## Configuration

See **.env.example** for all options:

- `DATABASE_URL` - SQLAlchemy connection string
- `LIBRARY_PATH` - Base directory for libraries
- `INGEST_PATH` - Directory for new files
- `CONFIG_PATH` - Configuration storage
- `COVERS_PATH` - Cover image storage
- `SECRET_KEY` - JWT signing key
- `JWT_ALGORITHM` - Token algorithm (HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token lifetime
- `CALIBRE_PATH` - Calibre executable directory
- `CORS_ORIGINS` - Allowed CORS origins

## Database Operations

### Initialize Database
```bash
python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"
```

### Create Migration
```bash
alembic revision --autogenerate -m "Description"
```

### Apply Migrations
```bash
alembic upgrade head
```

## Docker

### Build Image
```bash
docker build -t scriptorium-backend .
```

### Run Container
```bash
docker run -p 8000:8000 -v scriptorium-data:/app/data scriptorium-backend
```

## TODO Items by Priority

### High Priority (Core Features)
1. **ingest.py** - File watcher with watchfiles
2. **metadata.py** - EPUB/PDF/CBZ metadata extraction
3. **covers.py** - Cover extraction and thumbnails

### Medium Priority (Integration)
4. **conversion.py** - Calibre format conversion
5. **opds.py** - OPDS 1.2 Atom feed generation
6. **sync.py** - Kobo/KOReader/Calibre sync

### Low Priority (Polish)
7. **main.py** - WebSocket real-time events
8. **search.py** - FTS5 virtual table optimization
9. Testing and performance optimization

## Key Features Implemented

✅ User authentication with JWT and bcrypt
✅ Complete CRUD for books, libraries, shelves
✅ Reading progress tracking
✅ Pagination and filtering
✅ Database with relationships
✅ Environment configuration
✅ Docker deployment
✅ Health check endpoint
✅ CORS support for SvelteKit

## Debugging Tips

### Enable SQL Logging
In `database.py`, change:
```python
create_async_engine(..., echo=False)
```
to:
```python
create_async_engine(..., echo=True)
```

### Check Database
```bash
sqlite3 data/config/scriptorium.db ".tables"
```

### View Logs
Server logs are printed to console with timestamps.

### Debug Routes
Visit http://localhost:8000/docs for interactive API exploration

## File Sizes

- pyproject.toml: ~1 KB
- Complete app/: ~100 KB
- Entire project: ~352 KB

## Lines of Code

- Python modules: ~2,300 lines
- Configuration: ~100 lines
- Documentation: ~2,000 lines
- **Total: ~4,400 lines**

## Next Steps

1. Review README.md for detailed setup
2. Run `./run.sh` to start development
3. Test endpoints via http://localhost:8000/docs
4. Pick a TODO item and implement it
5. Reference existing endpoints as patterns

## Support Files

- `pyproject.toml` - All dependencies for pip install
- `Dockerfile` - Complete container image
- `alembic.ini` - Migration configuration
- `.env.example` - Configuration template
- `.gitignore` - Git ignore patterns
- `run.sh` - Quick start script

---

**Status**: Production-ready scaffold with complete CRUD operations and clear TODO markers for advanced features.

**Ready to start**: `./run.sh` or `uvicorn app.main:app --reload`
