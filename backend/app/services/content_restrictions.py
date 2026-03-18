"""Content restriction enforcement — filters books by age rating per user."""

from typing import Optional

from sqlalchemy import or_
from sqlalchemy.sql import Select

# Age rating hierarchy (lower index = less restrictive)
AGE_RATINGS = ["everyone", "teen", "mature", "adult"]
AGE_RATING_RANK = {r: i for i, r in enumerate(AGE_RATINGS)}


def apply_age_filter(stmt: Select, max_age_rating: Optional[str], work_column) -> Select:
    """Add a WHERE clause to filter out works above the user's max age rating.

    Args:
        stmt: The current SQLAlchemy select statement
        max_age_rating: The user's max allowed rating (None = unrestricted)
        work_column: The column reference to Work.age_rating (pass from the query context)

    Returns:
        The modified select statement
    """
    if not max_age_rating or max_age_rating not in AGE_RATING_RANK:
        return stmt  # Unrestricted

    rank = AGE_RATING_RANK[max_age_rating]
    allowed = AGE_RATINGS[:rank + 1]

    # Allow books with no rating (assume safe) or rating within allowed set
    return stmt.where(
        or_(
            work_column.is_(None),
            work_column == "",
            work_column.in_(allowed),
        )
    )


def user_can_view(age_rating: Optional[str], max_age_rating: Optional[str]) -> bool:
    """Check if a user with max_age_rating can view content with age_rating."""
    if not max_age_rating:
        return True  # Unrestricted
    if not age_rating:
        return True  # Unrated content is allowed
    user_rank = AGE_RATING_RANK.get(max_age_rating, len(AGE_RATINGS))
    content_rank = AGE_RATING_RANK.get(age_rating, 0)
    return content_rank <= user_rank
