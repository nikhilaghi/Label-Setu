from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.auth.router import router as auth_router
from app.inspections.router import router as inspections_router
from app.dashboard.router import router as dashboard_router
from app.review.router import router as review_router
from app.settings.router import router as settings_router
from app.complaints.router import router as complaints_router
from app.customer.router import router as customer_router

app = FastAPI(
    title="Label Setu Backend",
    description="AI-Assisted Legal Metrology Compliance Verification API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint per requirement 2
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Label Setu API", "version": "1.0.0"}

# Include Feature Routers
app.include_router(auth_router)
app.include_router(inspections_router)
app.include_router(dashboard_router)
app.include_router(review_router)
app.include_router(settings_router)
app.include_router(complaints_router)
app.include_router(customer_router)
