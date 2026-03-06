from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_config import logger
from app.routers import mint, upload, report, chunked_upload
from app.services.abuse_protection import setup_rate_limiter
from app.services.worker_executor import shutdown_executor

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    # Log feature flags status
    logger.info(f"Feature flags: extension_validation={settings.validate_file_extension}, "
                f"mime_validation={settings.validate_mime_type}, "
                f"metadata_parsing={settings.parse_metadata}, "
                f"signature_verification={settings.verify_signatures}, "
                f"rate_limiting={settings.enable_rate_limiting}, "
                f"deduplication={settings.enable_deduplication}")
    
    yield
    
    # Cleanup: shutdown worker executor
    logger.info("Shutting down worker executor...")
    shutdown_executor()
    logger.info(f"Shutting down {settings.app_name}")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# Configure CORS from settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Setup rate limiting (additive feature)
if settings.enable_rate_limiting:
    setup_rate_limiter(app)

app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(chunked_upload.router, prefix="/api", tags=["chunked-upload"])
app.include_router(mint.router, prefix="/api/mint", tags=["mint"])
app.include_router(report.router, prefix="/api", tags=["report"])


@app.get("/")
def read_root():
    return {"message": f"{settings.app_name} is running!"}
