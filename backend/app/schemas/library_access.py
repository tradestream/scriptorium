from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LibraryAccessGrant(BaseModel):
    user_id: int
    access_level: str = "read"  # read | write


class LibraryAccessRead(BaseModel):
    id: int
    library_id: int
    user_id: int
    access_level: str
    granted_at: datetime
    model_config = ConfigDict(from_attributes=True)
