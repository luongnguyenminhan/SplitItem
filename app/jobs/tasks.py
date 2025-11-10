from app.jobs.celery_worker import celery_app
from app.utils.image_workflow import generate_image_from_bytes
from app.utils.minio import generate_presigned_url, upload_bytes_to_minio


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
        print(f"[Celery] generate_image_task started for category: {category}")

        # Call synchronous generate_image_from_bytes
        generated_image_bytes = generate_image_from_bytes(file_bytes, mime_type, category)

        if not generated_image_bytes:
            print(f"[Celery] ERROR: No image generated for category: {category}")
            return {"success": False, "category": category}

        print(f"[Celery] generate_image_task completed for {category}: {len(generated_image_bytes)} bytes")
        return {
            "success": True,
            "category": category,
            "image_bytes": generated_image_bytes,
        }
    except Exception as e:
        print(f"[Celery] ERROR in generate_image_task: {e}")
        self.retry(exc=e, countdown=5)



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
        print(f"[Celery] upload_image_task started for: {file_name}")

        # Upload to MinIO
        success = upload_bytes_to_minio(
            file_bytes=image_bytes,
            bucket_name=bucket_name,
            object_name=file_name,
            content_type="image/jpeg",
        )

        if success:
            print(f"[Celery] Successfully uploaded {file_name}")
            public_url = generate_presigned_url(bucket_name, file_name)
            print(f"[Celery] Generated URL: {public_url}")

            # Extract category from filename (e.g., "generated_Top_abc123.jpg")
            category = file_name.split("_")[1]

            return {
                "success": True,
                "category": category,
                "url": public_url,
                "filename": file_name,
            }
        else:
            print(f"[Celery] Failed to upload {file_name}")
            return {"success": False, "filename": file_name}

    except Exception as e:
        print(f"[Celery] ERROR in upload_image_task: {e}")
        self.retry(exc=e, countdown=5)

