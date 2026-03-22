from sqlalchemy.orm import declarative_base

Base = declarative_base()

from app.models.book import Author, Book, BookContributor, BookFile, Series, Tag, book_authors, book_series, book_tags
from app.models.work import Work, WorkContributor, work_authors, work_tags, work_series
from app.models.edition import Edition, EditionFile, EditionContributor, UserEdition, Loan
from app.models.library import Library, LibraryAccess
from app.models.progress import Device, KOReaderProgress, KoboBookState, KoboSyncToken, KoboTokenShelf, ReadProgress, ReadingGoal
from app.models.shelf import Shelf, ShelfBook
from app.models.user import User
from app.models.analysis import AnalysisTemplate, BookAnalysis, ComputationalAnalysis, BookPromptConfig
from app.models.ingest import IngestLog
from app.models.api_key import ApiKey
from app.models.collection import Collection, CollectionBook
from app.models.annotation import Annotation
from app.models.read_session import ReadSession
from app.models.marginalium import Marginalium
from app.models.notebook import Notebook, NotebookEntry
from app.models.location import Location
from app.models.article import Article, ArticleTag, ArticleHighlight
from app.models.system import SystemSettings
from app.models.background_job import BackgroundJob

__all__ = [
    "Base",
    # Compatibility aliases (Book = Edition, etc.) — remove once all callers migrated
    "Book",
    "BookContributor",
    "BookFile",
    "book_authors",
    "book_tags",
    "book_series",
    # Shared lookup models
    "Author",
    "Tag",
    "Series",
    # Works/Editions
    "Work",
    "WorkContributor",
    "work_authors",
    "work_tags",
    "work_series",
    "Edition",
    "EditionFile",
    "EditionContributor",
    "UserEdition",
    "Loan",
    # Infrastructure
    "Library",
    "LibraryAccess",
    "User",
    "Shelf",
    "ShelfBook",
    "ReadProgress",
    "Device",
    "KoboSyncToken",
    "KoboTokenShelf",
    "KoboBookState",
    "KOReaderProgress",
    "ReadingGoal",
    "AnalysisTemplate",
    "BookAnalysis",
    "BookPromptConfig",
    "ComputationalAnalysis",
    "IngestLog",
    "ApiKey",
    "Collection",
    "CollectionBook",
    "Annotation",
    "ReadSession",
    "Marginalium",
    "Notebook",
    "NotebookEntry",
    "Location",
    "Article",
    "ArticleTag",
    "ArticleHighlight",
    "SystemSettings",
    "BackgroundJob",
]
