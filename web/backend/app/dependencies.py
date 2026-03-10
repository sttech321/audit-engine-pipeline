"""
FastAPI dependency injection providers.
"""
from typing import Annotated

from fastapi import Depends

from app.config import Settings, get_settings


# Type alias for settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]
