from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, AliasChoices


# --- Analysis Templates ---

class AnalysisTemplateBase(BaseModel):
    """Base schema for analysis templates."""
    name: str
    description: Optional[str] = None
    system_prompt: str
    user_prompt_template: str = Field(
        description="Template string. Use {text} as placeholder for the book text."
    )


class AnalysisTemplateCreate(AnalysisTemplateBase):
    """Create a new analysis template."""
    is_default: bool = False


class AnalysisTemplateUpdate(BaseModel):
    """Update an existing analysis template."""
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    is_default: Optional[bool] = None


class AnalysisTemplateRead(AnalysisTemplateBase):
    """Read schema for analysis templates."""
    id: int
    is_default: bool
    is_builtin: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Book Analyses ---

class AnalysisRequest(BaseModel):
    """Request to generate a new book analysis."""
    template_id: Optional[int] = None  # Use specific template, or default
    custom_prompt: Optional[str] = None  # One-off prompt override
    title: str = "Literary Analysis"  # Label for this analysis


class BookAnalysisRead(BaseModel):
    """Read schema for a book analysis."""
    id: int
    book_id: int = Field(validation_alias=AliasChoices("book_id", "work_id"))
    template_id: Optional[int] = None
    title: str
    content: str
    esoteric_reading: Optional[str] = None
    model_used: Optional[str] = None
    token_count: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    template: Optional[AnalysisTemplateRead] = None

    class Config:
        from_attributes = True


class BookAnalysisSummary(BaseModel):
    """Lightweight summary for listing analyses."""
    id: int
    book_id: int = Field(validation_alias=AliasChoices("book_id", "work_id"))
    title: str
    status: str
    model_used: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
