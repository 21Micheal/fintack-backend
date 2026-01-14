from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from app.api.routes import transaction_routes, webhook_routes
from app.api.routes.bank import router as bank_router 
from app.api.routes import goals 
from app.api.routes import ai_routes
from app.api.routes import alerts
from app.api.routes import insights
from app.api.routes import user_routes
from app.api.routes import auth_routes
from app.api.routes import advisor
from app.config import settings
import uvicorn
import logging
import time
import os
from contextlib import asynccontextmanager


# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# -------------------- Lifespan Manager --------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting Finance Tracker API...")
    yield
    # Shutdown
    logger.info("🛑 Shutting down Finance Tracker API...")

# -------------------- App Initialization --------------------
app = FastAPI(
    title="Finance Tracker API",
    version="1.0.0",
    description="Backend for financial insights, trends, and AI-driven analytics.",
    # docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    # redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    # lifespan=lifespan
)

# -------------------- CORS Setup --------------------
# More comprehensive origins list
origins = [
    "http://localhost:5173",   # Vite dev server
    "http://127.0.0.1:5173",   # Vite dev server alternative
    "http://localhost:3000",   # Create React App dev server
    "http://127.0.0.1:3000", 
    "http://localhost:8081",   # Expo web
    "http://127.0.0.1:8081",   # Alternate Expo web
    "http://localhost:19006",  # Expo old web port
    "http://127.0.0.1:19006",  # Alternate
    "http://localhost:8000",   # In case of same-port testing
    "http://127.0.0.1:8000", 
    "http://localhost",
    "http://127.0.0.1", # CRA alternative
    "https://your-frontend-domain.com",  # production
    # Add more as needed
]

# Allow all origins in development for flexibility
if os.getenv("ENVIRONMENT") == "development":
    origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development, restrict in production
    #allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# -------------------- Enhanced Logging Middleware --------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request
    logger.info(f"➡️  {request.method} {request.url} - Client: {request.client.host if request.client else 'Unknown'}")
    
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        
        # Log response with timing
        logger.info(f"⬅️  {response.status_code} for {request.method} {request.url} - {process_time:.2f}ms")
        
        # Add timing header
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        return response
        
    except Exception as exc:
        process_time = (time.time() - start_time) * 1000
        logger.error(f"❌ Error processing {request.method} {request.url} - {process_time:.2f}ms: {str(exc)}")
        raise

# -------------------- Security Headers Middleware --------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Remove server info for security
    if "server" in response.headers:
        del response.headers["server"]
        
    return response

# -------------------- Routers --------------------
app.include_router(bank_router, prefix="/api")
app.include_router(transaction_routes.router, prefix="/api", tags=["Transactions"])
app.include_router(webhook_routes.router)
app.include_router(ai_routes.router)
app.include_router(alerts.router)
app.include_router(insights.router)
app.include_router(goals.router)
app.include_router(auth_routes.router)
app.include_router(user_routes.router)
app.include_router(advisor.router)

# Conditionally include M-Pesa routes if configured
# if getattr(settings, 'MPESA_ENABLED', False):
#     app.include_router(mpesa_routes.router, prefix="/api")
#     logger.info("✅ M-Pesa routes enabled")
# else:
#     logger.info("ℹ️  M-Pesa routes disabled")

# -------------------- Basic Routes --------------------
@app.get("/")
async def root():
    return {
        "message": "Finance Tracker API is live 🚀",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "environment": getattr(settings, 'ENVIRONMENT', 'development')
    }

@app.get("/info")
async def api_info():
    """API information endpoint"""
    return {
        "name": "Finance Tracker API",
        "version": "1.0.0",
        "description": "Backend for financial insights, trends, and AI-driven analytics",
        "environment": getattr(settings, 'ENVIRONMENT', 'development'),
        "docs": "/docs" if settings.ENVIRONMENT != "production" else "Disabled in production"
    }

# -------------------- Enhanced Error Handling --------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    logger.warning(f"Validation error for {request.method} {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "details": jsonable_encoder(exc.errors()),
            "body": jsonable_encoder(exc.body)
        },
    )

@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: Exception):
    """Handle 404 errors"""
    logger.info(f"404 Not Found: {request.method} {request.url}")
    return JSONResponse(
        status_code=404,
        content={"error": "Resource not found", "path": str(request.url)},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled error for {request.method} {request.url}: {str(exc)}", exc_info=True)
    
    # Don't expose internal errors in production
    if getattr(settings, 'ENVIRONMENT', 'development') == 'production':
        detail = "Internal server error"
    else:
        detail = str(exc)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "details": detail,
            "request_id": getattr(request.state, 'request_id', 'unknown')
        },
    )

# -------------------- Startup Event (deprecated, use lifespan instead) --------------------
# @app.on_event("startup")
# async def startup_event():
#     logger.info("🚀 FastAPI Finance Tracker backend started successfully!")

# -------------------- Run (for local dev) --------------------
if __name__ == "__main__":
    # Get port from environment or default to 8000 (standard FastAPI port)
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development",
        log_level="info",
        access_log=True
    )