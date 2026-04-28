from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///data/config/scriptorium.db"

    # Paths
    LIBRARY_PATH: str = "data/library"
    INGEST_PATH: str = "data/ingest"
    CONFIG_PATH: str = "data/config"
    COVERS_PATH: str = "data/covers"
    MARKDOWN_PATH: str = "data/markdown"

    # Security
    SECRET_KEY: str = "your-secret-key-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "scriptorium"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "capacitor://localhost",   # iOS Capacitor app
        "ionic://localhost",       # alternative Capacitor scheme
    ]

    # API
    API_VERSION: str = "v1"

    # Metadata Enrichment API keys
    GOOGLE_BOOKS_API_KEY: str | None = None        # optional; raises rate limit without it
    HARDCOVER_API_KEY: str | None = None           # https://hardcover.app/account/api
    COMICVINE_API_KEY: str | None = None           # https://comicvine.gamespot.com/api/
    ISBNDB_API_KEY: str | None = None              # https://isbndb.com/apidocs/v2
    # Amazon metadata (cookie-based, no API account needed)
    # Paste your full cookie string from browser DevTools → Application → Cookies
    AMAZON_COOKIE: str | None = None
    LIBRARYTHING_API_KEY: str | None = None  # https://www.librarything.com/developer

    # OIDC / SSO authentication
    OIDC_ENABLED: bool = False
    OIDC_DISCOVERY_URL: str | None = None    # e.g. https://accounts.google.com
    OIDC_CLIENT_ID: str | None = None
    OIDC_CLIENT_SECRET: str | None = None
    OIDC_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oidc/callback"
    OIDC_SCOPES: str = "openid email profile"

    # SMTP (for Send-to-Kindle / email delivery)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASS: str | None = None
    SMTP_FROM: str | None = None
    SMTP_TLS: bool = True

    # Path rewriting for local dev (maps Docker container paths to local mounts)
    # e.g. "/data/library/booklore=/Volumes/docker/scriptorium/library"
    PATH_REWRITE: str | None = None

    # Loose Leaves — staged review queue (distinct from auto-ingest)
    LOOSE_LEAVES_PATH: str = "data/loose-leaves"

    # Ingest / conversion preferences
    INGEST_DEFAULT_LIBRARY: str = ""           # Library name for ingest (empty = first active)
    INGEST_AUTO_CONVERT: bool = False          # Auto-convert ingested files
    INGEST_TARGET_FORMAT: str = "epub"         # Target format when auto-converting
    INGEST_AUTO_ENRICH: bool = False           # Auto-enrich metadata on ingest
    INGEST_DEFAULT_PROVIDER: str = ""          # Provider to use for auto-enrichment

    # File naming pattern (Booklore-compatible)
    # Placeholders: {title} {author} {authors} {year} {series} {series_index}
    #               {language} {publisher} {isbn}
    # Wrap in <...> for optional blocks dropped when placeholders are empty.
    # Example: "{authors}/<{series}/{series_index}. >{title}"
    LIBRARY_NAMING_PATTERN: str = "{authors}/{title}"
    LIBRARY_NAMING_ENABLED: bool = False       # Set True to rename on import

    # AudiobookShelf integration
    ABS_URL: str | None = None              # e.g. http://192.168.1.10:13378
    ABS_API_KEY: str | None = None          # API key from ABS profile → API tab

    # Instapaper integration (OAuth 1.0a consumer credentials)
    INSTAPAPER_CONSUMER_KEY: str | None = None
    INSTAPAPER_CONSUMER_SECRET: str | None = None

    # LLM Configuration
    LLM_PROVIDER: str = "anthropic"  # "anthropic", "ollama", "openai"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20250514"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"

    # Cloud TTS — multiple providers, all optional. The frontend probes
    # ``/api/v1/tts/config`` to learn which are wired up.
    DASHSCOPE_API_KEY: str | None = None
    DASHSCOPE_BASE_URL: str = "https://dashscope-intl.aliyuncs.com"
    QWEN_TTS_MODEL: str = "qwen3-tts-flash"
    QWEN_TTS_VOICE: str = "Cherry"

    # ElevenLabs — studio-quality TTS, paid per character.
    ELEVENLABS_API_KEY: str | None = None
    ELEVENLABS_BASE_URL: str = "https://api.elevenlabs.io"
    ELEVENLABS_MODEL: str = "eleven_multilingual_v2"
    # Default voice id is Rachel (a stock voice every account has access to).
    ELEVENLABS_VOICE: str = "21m00Tcm4TlvDq8ikWAM"

    class Config:
        env_file = ".env"
        case_sensitive = True


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Dependency to get settings."""
    # No caching — allows hot-reload to pick up .env changes
    return Settings()


def resolve_path(path: str) -> str:
    """Rewrite a stored file path using PATH_REWRITE if configured.

    PATH_REWRITE format: semicolon-separated "docker_prefix=local_prefix" rules.
    Rules are tried in order; first match wins.
    e.g. "/data/library/booklore=/Volumes/docker/scriptorium/library;/data/library=/Volumes/docker/scriptorium/library"
    """
    settings = get_settings()
    if not settings.PATH_REWRITE:
        return path
    for rule in settings.PATH_REWRITE.split(";"):
        rule = rule.strip()
        if not rule:
            continue
        try:
            docker_prefix, local_prefix = rule.split("=", 1)
            if path.startswith(docker_prefix):
                return local_prefix + path[len(docker_prefix):]
        except ValueError:
            continue
    return path
