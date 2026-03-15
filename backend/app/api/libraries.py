from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Edition, Library, User
from app.models.library import LibraryAccess
from app.schemas.library import LibraryCreate, LibraryRead, LibraryUpdate
from app.schemas.library_access import LibraryAccessGrant, LibraryAccessRead
from app.services.scanner import scan_library

from .auth import get_current_user

router = APIRouter(prefix="/libraries")


@router.get("", response_model=list[LibraryRead])
async def list_libraries(
    include_hidden: bool = False,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all libraries. By default, hidden libraries are excluded from results.
    Pass include_hidden=true to include them (sidebar always does this)."""
    stmt = select(Library)
    if not include_hidden:
        stmt = stmt.where(Library.is_hidden == False)
    stmt = stmt.order_by(Library.sort_order.asc(), Library.id.asc())
    result = await db.execute(stmt)
    libraries = result.scalars().all()

    # Add book counts
    library_list = []
    for lib in libraries:
        lib_read = LibraryRead.model_validate(lib)
        # Get book count
        count_stmt = select(func.count(Edition.id)).where(Edition.library_id == lib.id)
        count = await db.scalar(count_stmt)
        lib_read.book_count = count or 0
        library_list.append(lib_read)

    return library_list


@router.get("/{library_id}", response_model=LibraryRead)
async def get_library(
    library_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get a specific library by ID."""
    stmt = select(Library).where(Library.id == library_id)
    result = await db.execute(stmt)
    library = result.scalar_one_or_none()

    if not library:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library not found",
        )

    lib_read = LibraryRead.model_validate(library)

    # Get book count
    count_stmt = select(func.count(Edition.id)).where(Edition.library_id == library.id)
    count = await db.scalar(count_stmt)
    lib_read.book_count = count or 0

    return lib_read


@router.post("", response_model=LibraryRead, status_code=status.HTTP_201_CREATED)
async def create_library(
    library_data: LibraryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new library."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create libraries",
        )

    # Check if name already exists
    stmt = select(Library).where(Library.name == library_data.name)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Library with this name already exists",
        )

    # Check if path already exists
    stmt = select(Library).where(Library.path == library_data.path)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Library with this path already exists",
        )

    library = Library(
        name=library_data.name,
        description=library_data.description,
        path=library_data.path,
        is_active=True,
    )

    db.add(library)
    await db.commit()
    await db.refresh(library)

    lib_read = LibraryRead.model_validate(library)
    lib_read.book_count = 0

    return lib_read


@router.put("/{library_id}", response_model=LibraryRead)
async def update_library(
    library_id: int,
    library_data: LibraryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a library."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update libraries",
        )

    stmt = select(Library).where(Library.id == library_id)
    result = await db.execute(stmt)
    library = result.scalar_one_or_none()

    if not library:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library not found",
        )

    if library_data.name is not None:
        # Check for duplicates
        stmt = select(Library).where(
            Library.name == library_data.name, Library.id != library_id
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Library with this name already exists",
            )
        library.name = library_data.name

    if library_data.description is not None:
        library.description = library_data.description

    if library_data.path is not None:
        # Check for duplicates
        stmt = select(Library).where(
            Library.path == library_data.path, Library.id != library_id
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Library with this path already exists",
            )
        library.path = library_data.path

    if library_data.is_active is not None:
        library.is_active = library_data.is_active

    if library_data.is_hidden is not None:
        library.is_hidden = library_data.is_hidden

    # naming_pattern uses explicit None sentinel: only update when key is present in payload
    # Pydantic model_fields_set lets us distinguish "not sent" from "sent as null"
    if "naming_pattern" in library_data.model_fields_set:
        library.naming_pattern = library_data.naming_pattern

    await db.commit()
    await db.refresh(library)

    lib_read = LibraryRead.model_validate(library)

    # Get book count
    count_stmt = select(func.count(Edition.id)).where(Edition.library_id == library.id)
    count = await db.scalar(count_stmt)
    lib_read.book_count = count or 0

    return lib_read


@router.delete("/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_library(
    library_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a library and all its books."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete libraries",
        )

    stmt = select(Library).where(Library.id == library_id)
    result = await db.execute(stmt)
    library = result.scalar_one_or_none()

    if not library:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library not found",
        )

    await db.delete(library)
    await db.commit()


@router.post("/{library_id}/scan")
async def trigger_scan(
    library_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a library scan for new books in the background."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can scan libraries",
        )

    stmt = select(Library).where(Library.id == library_id)
    result = await db.execute(stmt)
    library = result.scalar_one_or_none()

    if not library:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library not found",
        )

    async def _run_scan():
        from app.database import get_session_factory
        factory = get_session_factory()
        async with factory() as scan_db:
            # Re-fetch library in new session
            stmt2 = select(Library).where(Library.id == library_id)
            r = await scan_db.execute(stmt2)
            lib = r.scalar_one_or_none()
            if lib:
                await scan_library(lib, scan_db)

    background_tasks.add_task(_run_scan)

    return {
        "status": "scanning",
        "library_id": library_id,
        "message": f"Scan started for library '{library.name}'",
    }


class LibraryReorderRequest(BaseModel):
    library_ids: list[int]


@router.patch("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_libraries(
    body: LibraryReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set the display order of libraries by providing an ordered list of IDs."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can reorder libraries")

    for position, library_id in enumerate(body.library_ids):
        result = await db.execute(select(Library).where(Library.id == library_id))
        library = result.scalar_one_or_none()
        if library:
            library.sort_order = position

    await db.commit()


# ── Per-library access control ────────────────────────────────────────────────

@router.get("/{library_id}/access", response_model=list[LibraryAccessRead])
async def list_library_access(
    library_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List per-user access grants for a library (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    result = await db.execute(
        select(LibraryAccess).where(LibraryAccess.library_id == library_id)
    )
    return result.scalars().all()


@router.post("/{library_id}/access", response_model=LibraryAccessRead, status_code=status.HTTP_201_CREATED)
async def grant_library_access(
    library_id: int,
    data: LibraryAccessGrant,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Grant a user access to a library (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    # Check for existing grant
    existing = await db.execute(
        select(LibraryAccess).where(
            LibraryAccess.library_id == library_id,
            LibraryAccess.user_id == data.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Access already granted")
    grant = LibraryAccess(
        library_id=library_id,
        user_id=data.user_id,
        access_level=data.access_level,
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return grant


@router.delete("/{library_id}/access/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_library_access(
    library_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke a user's access to a library (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    result = await db.execute(
        select(LibraryAccess).where(
            LibraryAccess.library_id == library_id,
            LibraryAccess.user_id == user_id,
        )
    )
    grant = result.scalar_one_or_none()
    if not grant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access grant not found")
    await db.delete(grant)
    await db.commit()
