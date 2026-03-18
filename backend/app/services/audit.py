"""Audit logging service — lightweight helper for recording actions."""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    action: str,
    *,
    user_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    detail: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Record an audit event. Non-blocking — silently swallows errors."""
    try:
        from app.models.audit import AuditLog
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail,
            ip_address=ip_address,
        )
        db.add(entry)
        # Don't commit here — caller's transaction will include it
    except Exception as exc:
        logger.debug("Audit log failed: %s", exc)
