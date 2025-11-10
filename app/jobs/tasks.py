from app.jobs.celery_worker import celery_app
from app.utils.minio import generate_presigned_url, upload_bytes_to_minio


@celery_app.task(bind=True, name="generate_image_task")
def generate_image_task(self, category: str):
    """
    Generate image for given category using Celery task.

    Args:
        category: Category name (Top or Bot)

    Returns:
        Status message
    """
    try:
        print(f"[Celery] generate_image_task started for category: {category}")
        print(f"[Celery] generate_image_task completed for category: {category}")
        return {"status": "completed", "category": category}
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

