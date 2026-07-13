"""
backend/api/main.py

FastAPI Application Entry Point.
Sets up api routing, versioning boundary, and global health check endpoint.
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import attribution, decision, forecast

app = FastAPI(
    title="Vaeris API",
    description="AI-Powered Urban Air Quality Intelligence Platform API",
    version="1.0.0",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root/Health check route
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Service health check endpoint.
    """
    return {"status": "healthy", "service": "Vaeris API"}


# API Version 1 Router
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(forecast.router)
v1_router.include_router(attribution.router)
v1_router.include_router(decision.router)

# Register routers on app
app.include_router(v1_router)

