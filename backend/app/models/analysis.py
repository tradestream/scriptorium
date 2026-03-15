from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class AnalysisTemplate(Base):
    """Reusable prompt templates for LLM book analysis."""

    __tablename__ = "analysis_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text)  # The system/role instructions
    user_prompt_template: Mapped[str] = mapped_column(Text)  # Template with {text} placeholder
    is_default: Mapped[bool] = mapped_column(default=False)
    is_builtin: Mapped[bool] = mapped_column(default=False)  # Ships with Scriptorium
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    analyses: Mapped[list["BookAnalysis"]] = relationship("BookAnalysis", back_populates="template")


class BookAnalysis(Base):
    """Stores LLM-generated analysis for a work."""

    __tablename__ = "book_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("analysis_templates.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255))  # e.g. "Literary Analysis", "Character Study"
    content: Mapped[str] = mapped_column(Text)  # The full analysis result (markdown)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g. "claude-sonnet-4-5-20250514"
    token_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="completed", index=True
    )  # pending, running, completed, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Optional esoteric (hidden-meaning) reading — only shown when work.esoteric_enabled
    esoteric_reading: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    work: Mapped["Work"] = relationship("Work", back_populates="analyses")
    template: Mapped[Optional["AnalysisTemplate"]] = relationship(
        "AnalysisTemplate", back_populates="analyses"
    )


class ComputationalAnalysis(Base):
    """Stores results from computational (non-LLM) analysis tools."""

    __tablename__ = "computational_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    analysis_type: Mapped[str] = mapped_column(String(50), index=True)  # loud_silence, contradiction, center, exoteric_esoteric, full
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Input config as JSON
    results_json: Mapped[str] = mapped_column(Text)  # Full results as JSON
    status: Mapped[str] = mapped_column(String(20), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    work: Mapped["Work"] = relationship("Work", back_populates="computational_analyses")


class BookPromptConfig(Base):
    """Per-work custom prompt overrides for analysis templates."""

    __tablename__ = "book_prompt_configs"
    __table_args__ = (UniqueConstraint("work_id", "template_id", name="uq_work_template_prompt"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("analysis_templates.id"), nullable=True)
    custom_system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    custom_user_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    work: Mapped["Work"] = relationship("Work", back_populates="prompt_configs")
    template: Mapped[Optional["AnalysisTemplate"]] = relationship("AnalysisTemplate")
