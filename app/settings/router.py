from fastapi import APIRouter, Depends
from typing import Dict
from app.auth.router import get_current_user
from .models import SettingsModel

router = APIRouter(prefix="/api/settings", tags=["settings"])
settings_by_user: Dict[str, SettingsModel] = {}

@router.get("", response_model=SettingsModel)
async def get_settings(user: dict = Depends(get_current_user)):
    if user["id"] not in settings_by_user:
        defaults = SettingsModel()
        defaults.profile.fullName = user.get("name", defaults.profile.fullName)
        defaults.profile.role = user.get("role", defaults.profile.role)
        defaults.profile.email = user.get("email", defaults.profile.email)
        defaults.profile.department = user.get("department", defaults.profile.department)
        defaults.profile.employeeId = user.get("id", defaults.profile.employeeId)
        settings_by_user[user["id"]] = defaults
    return settings_by_user[user["id"]]

@router.put("", response_model=SettingsModel)
async def update_settings(new_settings: SettingsModel, user: dict = Depends(get_current_user)):
    settings_by_user[user["id"]] = new_settings
    return new_settings
