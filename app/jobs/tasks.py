import json
import logging
from datetime import datetime

from app.core.config import settings
from app.jobs.celery_worker import celery_app
from app.utils.image_workflow import generate_image_from_bytes, generate_tryon_image
from app.utils.minio import generate_presigned_url, upload_bytes_to_minio
from app.utils.redis import get_redis_client

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="generate_image_task")
def generate_image_task(self, file_bytes: bytes, mime_type: str, category: str):
    """
    Generate image for given category using Celery task (runs in background worker).

    Args:
        file_bytes: Image file bytes (already validated and converted)
        mime_type: MIME type of image
        category: Category name (Top or Bot)

    Returns:
        Dict with generated image data and metadata
    """
    try:
        logger.info(f"[generate_image_task] Started for category: {category}")

        # Call synchronous generate_image_from_bytes
        generated_image_bytes = generate_image_from_bytes(file_bytes, mime_type, category)

        if not generated_image_bytes:
            logger.error(f"[generate_image_task] No image generated for category: {category}")
            return {"success": False, "category": category}

        logger.info(f"[generate_image_task] Completed for {category}: {len(generated_image_bytes)} bytes")
        return {
            "success": True,
            "category": category,
            "image_bytes": generated_image_bytes,
        }
    except Exception as e:
        logger.error(f"[generate_image_task] ERROR: {e}")
        self.retry(exc=e, countdown=5, max_retries=2)


@celery_app.task(bind=True, name="upload_image_task")
def upload_image_task(self, image_bytes: bytes, file_name: str, bucket_name: str):
    """
    Upload generated image to MinIO using Celery task.

    Args:
        image_bytes: Image bytes to upload
        file_name: Filename in MinIO
        bucket_name: Bucket name

    Returns:
        Dict with upload result (url, filename, category)
    """
    try:
        logger.info(f"[upload_image_task] Started for: {file_name}")

        # Upload to MinIO
        success = upload_bytes_to_minio(
            file_bytes=image_bytes,
            bucket_name=bucket_name,
            object_name=file_name,
            content_type="image/jpeg",
        )

        if success:
            logger.info(f"[upload_image_task] Successfully uploaded {file_name}")
            public_url = generate_presigned_url(bucket_name, file_name)
            logger.info(f"[upload_image_task] Generated URL: {public_url}")

            # Extract category from filename (e.g., "generated_Top_abc123.jpg")
            category = file_name.split("_")[1]

            return {
                "success": True,
                "category": category,
                "url": public_url,
                "filename": file_name,
            }
        else:
            logger.error(f"[upload_image_task] Failed to upload {file_name}")
            return {"success": False, "filename": file_name}

    except Exception as e:
        logger.error(f"[upload_image_task] ERROR: {e}")
        self.retry(exc=e, countdown=5, max_retries=2)


@celery_app.task(bind=True, name="generate_tryon_image_task", time_limit=150)
def generate_tryon_image_task(
    self,
    human_image_bytes: bytes,
    clothing_urls_json: str,
    task_id: str,
) -> dict:
    """
    Generate try-on image using Gemini API with optimized prompt.

    Args:
        human_image_bytes: Raw human image bytes (JPEG)
        clothing_urls_json: JSON string of clothing URLs
        task_id: Unique task identifier

    Returns:
        Dict with generation result
    """
    try:
        logger.info(f"[generate_tryon_image_task] Started for task_id: {task_id}")

        # Parse clothing URLs
        clothing_urls = json.loads(clothing_urls_json)
        
        # Call async-compatible generation function
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            generate_tryon_image(
                human_image_bytes=human_image_bytes,
                clothing_urls=clothing_urls,
                task_id=task_id,
            )
        )
        loop.close()

        if result["success"]:
            logger.info(f"[generate_tryon_image_task] Generation completed for {task_id}")
            return result
        else:
            logger.error(f"[generate_tryon_image_task] Generation failed: {result.get('error')}")
            return result

    except Exception as e:
        logger.error(f"[generate_tryon_image_task] ERROR: {e}")
        try:
            redis_client = get_redis_client()
            redis_client.hset(f"tryon_task:{task_id}", mapping={
                "status": "failed",
                "error": str(e),
                "updated_at": datetime.utcnow().isoformat(),
            })
        except Exception as redis_err:
            logger.error(f"[generate_tryon_image_task] Failed to update Redis: {redis_err}")
        
        self.retry(exc=e, countdown=5, max_retries=2)
