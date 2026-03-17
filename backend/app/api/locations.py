"""Location CRUD — hierarchical physical locations for book tracking."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.location import Location
from app.models.user import User

from .auth import get_current_user

router = APIRouter(prefix="/locations")


# ── Schemas ──────────────────────────────────────────────────────────────────

class LocationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None


class LocationRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    tree_path: str = ""

    class Config:
        from_attributes = True


class LocationTreeNode(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    children: list["LocationTreeNode"] = []

    class Config:
        from_attributes = True


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[LocationRead])
async def list_locations(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List all locations as a flat list with tree_path breadcrumbs."""
    # Load all locations with parents for tree_path computation
    result = await db.execute(
        select(Location).options(selectinload(Location.parent))
    )
    locations = result.scalars().all()

    # Build parent lookup for tree_path
    by_id = {loc.id: loc for loc in locations}

    def build_path(loc: Location) -> str:
        parts = [loc.name]
        pid = loc.parent_id
        while pid and pid in by_id:
            parts.append(by_id[pid].name)
            pid = by_id[pid].parent_id
        parts.reverse()
        return " > ".join(parts)

    return [
        LocationRead(
            id=loc.id,
            name=loc.name,
            description=loc.description,
            parent_id=loc.parent_id,
            tree_path=build_path(loc),
        )
        for loc in sorted(locations, key=lambda l: build_path(l))
    ]


@router.get("/tree", response_model=list[LocationTreeNode])
async def get_location_tree(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get locations as a nested tree structure."""
    result = await db.execute(select(Location))
    locations = result.scalars().all()

    by_id = {loc.id: loc for loc in locations}
    nodes: dict[int, dict] = {}

    for loc in locations:
        nodes[loc.id] = {
            "id": loc.id,
            "name": loc.name,
            "description": loc.description,
            "children": [],
        }

    roots = []
    for loc in locations:
        node = nodes[loc.id]
        if loc.parent_id and loc.parent_id in nodes:
            nodes[loc.parent_id]["children"].append(node)
        else:
            roots.append(node)

    # Sort children alphabetically at each level
    def sort_tree(items: list):
        items.sort(key=lambda x: x["name"])
        for item in items:
            sort_tree(item["children"])

    sort_tree(roots)
    return roots


@router.post("", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
async def create_location(
    data: LocationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new location."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    if data.parent_id:
        parent = await db.get(Location, data.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent location not found")

    loc = Location(name=data.name, description=data.description, parent_id=data.parent_id)
    db.add(loc)
    await db.commit()
    await db.refresh(loc)

    return LocationRead(
        id=loc.id, name=loc.name, description=loc.description,
        parent_id=loc.parent_id, tree_path=loc.name,
    )


@router.put("/{location_id}", response_model=LocationRead)
async def update_location(
    location_id: int,
    data: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a location."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    loc = await db.get(Location, location_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    if data.name is not None:
        loc.name = data.name
    if data.description is not None:
        loc.description = data.description
    if data.parent_id is not None:
        # Prevent circular reference
        if data.parent_id == location_id:
            raise HTTPException(status_code=400, detail="Cannot be own parent")
        loc.parent_id = data.parent_id if data.parent_id != 0 else None

    await db.commit()
    return LocationRead(
        id=loc.id, name=loc.name, description=loc.description,
        parent_id=loc.parent_id, tree_path=loc.name,
    )


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a location and its children."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    loc = await db.get(Location, location_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    await db.delete(loc)
    await db.commit()
