import asyncio
import uuid

from fastapi import UploadFile

from app.jobs.tasks import upload_image_task
from app.utils.image_workflow import generate_image
from app.utils.image_workflow.prompt import CATEGORIES


async def generate_and_upload_images(
    image_file: UploadFile,
    bucket_name: str,
) -> list[dict]:
    """
    Generate images for each category in parallel and upload to MinIO using Celery.

    Args:
        image_file: Uploaded image file
        bucket_name: MinIO bucket name

    Returns:
        List of dicts with generated image info
    """
    print(f"[generate_and_upload_images] Starting image generation for bucket: {bucket_name}")

    generated_items = []
    tasks = []

    # Phase 1: Generate images for all categories in parallel
    print(f"[generate_and_upload_images] Creating generation tasks for {len(CATEGORIES)} categories")

    for category_name in CATEGORIES.keys():
        await image_file.seek(0)
        tasks.append(generate_image(image_file, category_name))

    # Execute all generation tasks in parallel
    print("[generate_and_upload_images] Running generation tasks in parallel...")
    generated_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Phase 2: Upload all generated images in parallel using Celery
    print("[generate_and_upload_images] Submitting upload tasks to Celery...")
    upload_tasks = []

    for category_name, generated_image_bytes in zip(CATEGORIES.keys(), generated_results, strict=True):
        # Handle exceptions from generation
        if isinstance(generated_image_bytes, Exception):
            print(f"[generate_and_upload_images] ERROR generating {category_name}: {generated_image_bytes}")
            continue

        if not generated_image_bytes:
            print(f"[generate_and_upload_images] No image generated for {category_name}, skipping...")
            continue

        print(f"[generate_and_upload_images] Generated image for {category_name}: {len(generated_image_bytes)} bytes")

        # Create filename
        file_name = f"generated_{category_name}_{uuid.uuid4().hex[:8]}.jpg"
        print(f"[generate_and_upload_images] Submitting upload task for: {file_name}")

        # Submit upload task to Celery (non-blocking)
        celery_task = upload_image_task.apply_async(
            args=[generated_image_bytes, file_name, bucket_name],
            countdown=0,
        )
        upload_tasks.append(celery_task)

    # Wait for all upload tasks to complete
    print(f"[generate_and_upload_images] Waiting for {len(upload_tasks)} upload tasks to complete...")
    for idx, task in enumerate(upload_tasks):
        try:
            # Wait for task with timeout
            result = task.get(timeout=60)
            if result and result.get("success"):
                print(f"[generate_and_upload_images] Upload task {idx + 1} completed successfully")
                generated_items.append(result)
            else:
                print(f"[generate_and_upload_images] Upload task {idx + 1} failed")
        except Exception as e:
            print(f"[generate_and_upload_images] ERROR waiting for upload task {idx + 1}: {e}")
            continue

    print(f"[generate_and_upload_images] Completed - Generated and uploaded {len(generated_items)} images")
    return generated_items


