from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
from app.auth.jwt_handler import verify_password, get_password_hash, create_access_token, decode_token

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

# Demo accounts matching the frontend. Persistence remains in-memory by design.
USERS: Dict[str, Dict[str, Any]] = {}

def _make_user(**kwargs: Any) -> Dict[str, Any]:
    return {**kwargs, "hashed_password": get_password_hash(kwargs.pop("password"))}

USERS["OFF-8849-DL"] = {
    "id": "OFF-8849-DL",
    "name": "Officer Rajesh Kumar",
    "email": "officer@labelsetu.gov.in",
    "role": "Officer",
    "designation": "Enforcement Official",
    "department": "Legal Metrology Department",
    "zone": "North Zone - Delhi HQ",
    "badgeNumber": "LM-ENF-2026-894",
    "avatarUrl": None,
    "hashed_password": get_password_hash("password123"),
}
USERS["CUST-2026-001"] = {
    "id": "CUST-2026-001",
    "name": "Authorized Business Representative",
    "email": "customer@labelsetu.gov.in",
    "role": "Customer",
    "designation": "Registered Manufacturer / Packer",
    "department": "Customer Compliance Portal",
    "zone": "Corporate Unit",
    "badgeNumber": "LM-CUST-2026",
    "avatarUrl": None,
    "hashed_password": get_password_hash("customer123"),
    "company": "ABC Consumer Packaged Goods Ltd.",
    "registrationNo": "REG-LM-2026-9812",
}

EMAIL_INDEX = {u["email"].lower(): uid for uid, u in USERS.items()}


def get_clean_user(user: Dict[str, Any]) -> Dict[str, Any]:
    clean = {k: v for k, v in user.items() if k != "hashed_password"}
    return clean


class LoginRequest(BaseModel):
    email: str
    password: str
    role: Optional[str] = None

class CustomerRegisterRequest(BaseModel):
    customerName: str
    email: str
    mobile: str
    password: str


class OfficerRegisterRequest(BaseModel):
    name: str
    email: str
    officerId: str
    department: str
    office: str
    mobile: str
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    user = USERS.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_clean_user(user)


def require_role(*roles: str):
    allowed = {r.lower() for r in roles}

    def dependency(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if user.get("role", "").lower() not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency


@router.post("/login")
async def login(request: LoginRequest):
    email = request.email.strip().lower()
    user_id = EMAIL_INDEX.get(email)
    user = USERS.get(user_id) if user_id else None

    requested_role = request.role.strip().lower() if request.role else None
    if user and requested_role and user["role"].lower() != requested_role:
        user = None

    if user and user.get("status") != "PENDING_APPROVAL" and verify_password(request.password, user["hashed_password"]):
        token = create_access_token({"sub": user["id"], "role": user["role"]})
        return {"token": token, "token_type": "bearer", "user": get_clean_user(user)}

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_customer(request: CustomerRegisterRequest):
    email = request.email.strip().lower()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )

    if len(request.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )

    if email in EMAIL_INDEX:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists"
        )

    user_id = f"CUST-{2026}-{len(USERS) + 1:03d}"

    user = {
        "id": user_id,
        "name": request.customerName.strip(),
        "email": email,
        "role": "Customer",
        "designation": "Registered Manufacturer / Packer",
        "department": "Customer Compliance Portal",
        "zone": "Corporate Unit",
        "badgeNumber": f"LM-CUST-{2026}-{len(USERS) + 1:03d}",
        "avatarUrl": None,
        "hashed_password": get_password_hash(request.password),
        "mobile": request.mobile.strip(),
    }

    USERS[user_id] = user
    EMAIL_INDEX[email] = user_id

    return {
        "message": "Customer account created successfully",
        "user": get_clean_user(user)
    }

@router.post("/officer/register", status_code=status.HTTP_201_CREATED)
async def register_officer(request: OfficerRegisterRequest):
    email = request.email.strip().lower()
    officer_id = request.officerId.strip()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )

    if not officer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Officer ID is required"
        )

    if len(request.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )

    if email in EMAIL_INDEX:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists"
        )

    if officer_id in USERS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Officer ID is already registered"
        )

    user = {
        "id": officer_id,
        "name": request.name.strip(),
        "email": email,
        "role": "Officer",
        "designation": "Enforcement Official",
        "department": request.department.strip(),
        "office": request.office.strip(),
        "mobile": request.mobile.strip(),
        "zone": request.office.strip(),
        "badgeNumber": officer_id,
        "avatarUrl": None,
        "status": "PENDING_APPROVAL",
        "hashed_password": get_password_hash(request.password),
    }

    USERS[officer_id] = user
    EMAIL_INDEX[email] = officer_id

    return {
        "message": "Officer registration submitted for approval",
        "user": get_clean_user(user)
    }

@router.get("/me")
async def read_users_me(user: Dict[str, Any] = Depends(get_current_user)):
    return user


@router.put("/password")
async def change_password(request: ChangePasswordRequest, user: Dict[str, Any] = Depends(get_current_user)):
    record = USERS.get(user["id"])
    if not record or not verify_password(request.current_password, record["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if len(request.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be at least 6 characters long")
    record["hashed_password"] = get_password_hash(request.new_password)
    return {"message": "Password updated successfully"}
