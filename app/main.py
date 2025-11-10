from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRouter

from app.api import api_router
from app.core.config import settings


def custom_generate_unique_id(route: APIRouter) -> str:
    """
    Custom function to generate unique operation IDs for OpenAPI schema.
    This creates cleaner method names for generated client code.
    """
    if route.tags:
        # Use first tag + operation name for better organization
        return f"{route.tags[0]}_{route.name}"
    return route.name


def custom_openapi():
    """
    Custom OpenAPI schema generator with additional metadata and extensions.
    """
    if app.openapi_schema:
        return app.openapi_schema

    # Generate base OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add custom extensions
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png",
        "altText": "ISplitter API Logo",
    }

    # Add custom servers for different environments
    openapi_schema["servers"] = [
        {"url": "http://localhost:8081/be", "description": "Development server"},
        {"url": "https://isplitter.wc504.io.vn/be", "description": "Production server"},
    ]

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT Authorization header using the Bearer scheme.",
        }
    }

    # Apply security globally
    openapi_schema["security"] = [{"BearerAuth": []}]

    # Cache the schema
    app.openapi_schema = openapi_schema
    return openapi_schema


app = FastAPI(
    title="ISplitterBE",
    version="1.0.0",
    contact={
        "name": "ISplitter Team",
        "email": "support@ISplitter.com",
    },
    license_info={
        "name": "MIT",
    },
    root_path="/be",
    # Custom operation ID generation for better client code
    generate_unique_id_function=custom_generate_unique_id,
)
@app.middleware("http")
async def log_requests(request, call_next):
    print(f"[REQUEST] {request.method} {request.url}")
    response = await call_next(request)
    print(f"\033[92m[RESPONSE]\033[0m {response.__class__.__name__}({response.status_code if hasattr(response, 'status_code') else 'streaming'}, {getattr(response, 'media_type', 'unknown')})")

    try:
        if hasattr(response, 'body'):
            body_content = response.body.decode('utf-8', errors='ignore')
            # Limit body size to avoid flooding logs
            if len(body_content) > 500:
                body_content = body_content[:500] + "..."
            print(f"\033[93m[RESPONSE BODY]\033[0m {body_content}")
        elif hasattr(response, 'content') and response.content:
            body_content = response.content.decode('utf-8', errors='ignore')
            if len(body_content) > 500:
                body_content = body_content[:500] + "..."
            print(f"\033[93m[RESPONSE BODY]\033[0m {body_content}")
    except Exception as e:
        print(f"\033[91m[BODY LOG ERROR]\033[0m Could not read response body: {e}")

    return response
app = FastAPI(
    title="ISplitterBE",
    version="1.0.0",
    contact={
        "name": "ISplitter Team",
        "email": "support@ISplitter.com",
    },
    license_info={
        "name": "MIT",
    },
    root_path="/be",
    # Custom operation ID generation for better client code
    generate_unique_id_function=custom_generate_unique_id,
)
app.openapi = custom_openapi
app.add_middleware(
    CORSMiddleware,
    allow_origins=(["*"]),
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "OPTIONS",
    ],  # Explicitly allow methods
    allow_headers=["*"],  # Allow all headers including Authorization
    expose_headers=["*"],  # Expose all headers for EventSource
)
app.include_router(api_router)
@app.get("/")
def root():
    return {"message": "Welcome to SplitCloth API"}
@app.get("/health/minio")
def health_minio() -> Dict[str, Any]:
    """
    MinIO health check endpoint
    """
    try:
        from app.utils.minio import get_minio_client

        # Test connection by listing buckets
        minio_client = get_minio_client()
        try:
            buckets = minio_client.list_buckets()
            bucket_names = [bucket.name for bucket in buckets]

            # Check if our buckets exist
            main_bucket_exists = settings.MINIO_BUCKET_NAME in bucket_names
            public_bucket_exists = settings.MINIO_PUBLIC_BUCKET_NAME in bucket_names

            return {
                "status": "connected",
                "endpoint": settings.MINIO_ENDPOINT,
                "secure": settings.MINIO_SECURE,
                "main_bucket": {
                    "name": settings.MINIO_BUCKET_NAME,
                    "exists": main_bucket_exists,
                },
                "public_bucket": {
                    "name": settings.MINIO_PUBLIC_BUCKET_NAME,
                    "exists": public_bucket_exists,
                },
                "total_buckets": len(bucket_names),
                "bucket_names": bucket_names[:10],  # Limit to first 10 for brevity
            }
        except Exception as bucket_error:
            return {
                "status": "connected",
                "endpoint": settings.MINIO_ENDPOINT,
                "secure": settings.MINIO_SECURE,
                "bucket_check_error": str(bucket_error),
            }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "disconnected",
                "error": str(e),
                "endpoint": settings.MINIO_ENDPOINT,
                "secure": settings.MINIO_SECURE,
            },
        )
