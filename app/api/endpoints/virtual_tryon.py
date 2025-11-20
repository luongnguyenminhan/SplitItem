"""
Virtual Try-On API endpoints for generating try-on visualizations.
"""
import json
import logging
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.jobs.tasks import upload_image_task
from app.schemas.virtual_tryon import (
    ClothingItemSchema,
    VirtualTryOnResponseSchema,
)
from app.services.virtual_tryon_service import (
    validate_clothing_items,
    validate_human_image,
)
from app.utils.image_workflow import generate_tryon_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix=settings.API_V1_STR, tags=["Virtual Try-On"])


@router.post(
    "/virtual-tryon/try-on",
    response_model=VirtualTryOnResponseSchema,
    status_code=200,
    summary="Generate Virtual Try-On Image",
    description="Generate a virtual try-on image with a human image and 1-3 clothing item URLs",
)
async def create_tryon_request(
    human_image: UploadFile = File(..., description="Full-body human image (JPEG, PNG, or WebP)"),
    clothing_urls: list[str] = None,
) -> VirtualTryOnResponseSchema:
    """
    Generate virtual try-on image synchronously.

    Args:
        human_image: Uploaded human image file
        clothing_urls: List of 1-3 clothing item URLs

    Returns:
        VirtualTryOnResponseSchema with result URL

    Raises:
        HTTPException: 400 if inputs invalid, 500 if generation fails
    """
    try:
        print("[create_tryon_request] Started")
        print(f"[create_tryon_request] Human image: {clothing_urls}")
        start_time = __import__('time').time()
        # Validate human image
        human_image_bytes = await human_image.read()
        if not human_image_bytes:
            raise ValueError("Human image file is empty")

        converted_image_bytes, mime_type = validate_human_image(human_image_bytes)
        print(f"[create_tryon_request] Human image validated: {len(converted_image_bytes)} bytes")
        clothing_urls = clothing_urls[0].split(",") if clothing_urls else []
        # Validate clothing URLs
        if not clothing_urls:
            raise ValueError("At least one clothing item URL is required")
        
        if len(clothing_urls) > 3:
            raise ValueError("Maximum 3 clothing items allowed")

        clothing_items = [ClothingItemSchema(image_url=url) for url in clothing_urls]
        validate_clothing_items(clothing_items)
        print(f"[create_tryon_request] Validated {len(clothing_items)} clothing items")

        # Generate try-on image
        task_id = str(uuid4())
        print(f"[create_tryon_request] Generating try-on image: {task_id}")
        
        import asyncio
        result = await generate_tryon_image(converted_image_bytes, clothing_urls, task_id)
        
        if not result["success"]:
            raise Exception(result.get("error", "Generation failed"))

        print(f"[create_tryon_request] Generated image: {len(result['image_bytes'])} bytes")

        # Upload to MinIO using Celery task
        file_name = f"tryon_{task_id}.jpg"
        print(f"[create_tryon_request] Uploading to MinIO: {file_name}")
        
        upload_task = upload_image_task.apply_async(
            args=[result["image_bytes"], file_name, settings.MINIO_PUBLIC_BUCKET_NAME],
            countdown=0,
        )
        
        upload_result = upload_task.get(timeout=120)
        print(f"[create_tryon_request] Upload result: {upload_result}")
        
        if not upload_result or not upload_result.get("success"):
            raise Exception("Failed to upload to MinIO")

        result_url = upload_result.get("url")
        print(f"[create_tryon_request] Generated URL: {result_url}")
        end_time = __import__('time').time()
        print(f"[split_image] Total processing time: {end_time - start_time:.2f} seconds")
        return VirtualTryOnResponseSchema(
            time=str(f"{end_time - start_time:.2f}"),
            url=result_url
        )

    except ValueError as e:
        print(f"[create_tryon_request] Validation error: {e}")
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except Exception as e:
        print(f"[create_tryon_request] Error: {e}")
        raise HTTPException(status_code=500, detail={"error": str(e)})
