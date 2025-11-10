import uuid

from fastapi import UploadFile

from app.jobs.tasks import generate_image_task, upload_image_task
from app.utils.image_workflow import _validate_and_convert_image
from app.utils.image_workflow.prompt import CATEGORIES


async def generate_and_upload_images(
    image_file: UploadFile,
    bucket_name: str,
) -> list[dict]:
    """
    Generate images for each category in parallel using Celery and upload to MinIO.

    Args:
        image_file: Uploaded image file
        bucket_name: MinIO bucket name

    Returns:
        List of dicts with generated image info
    """
    print(f"[generate_and_upload_images] Starting image generation for bucket: {bucket_name}")

    generated_items = []

    # Read file content ONCE
    print("[generate_and_upload_images] Reading image file content...")
    file_content = await image_file.read()
    print(f"[generate_and_upload_images] File content read: {len(file_content)} bytes")

    # Validate and convert image to JPEG
    print("[generate_and_upload_images] Validating and converting image...")
    converted_bytes, mime_type = _validate_and_convert_image(file_content)
    print(f"[generate_and_upload_images] Image validated: {len(converted_bytes)} bytes, MIME: {mime_type}")

    # Phase 1: Submit generation tasks to Celery for PARALLEL execution
    print(f"[generate_and_upload_images] Submitting {len(CATEGORIES)} generation tasks to Celery...")
    generation_tasks = []

    for category_name in CATEGORIES.keys():
        # Submit task to Celery (runs in background worker)
        celery_task = generate_image_task.apply_async(
            args=[converted_bytes, mime_type, category_name],
            countdown=0,
        )
        generation_tasks.append((category_name, celery_task))
        print(f"[generate_and_upload_images] Submitted generation task for {category_name}: {celery_task.id}")

    # Wait for all generation tasks to complete
    print(f"[generate_and_upload_images] Waiting for {len(generation_tasks)} generation tasks...")
    generated_results = {}

    for category_name, celery_task in generation_tasks:
        try:
            result = celery_task.get(timeout=120)  # 2 minute timeout for generation
            print(f"[generate_and_upload_images] Generation task for {category_name} completed")

            if result and result.get("success"):
                generated_results[category_name] = result
            else:
                print(f"[generate_and_upload_images] Generation failed for {category_name}: {result}")
        except Exception as e:
            print(f"[generate_and_upload_images] ERROR waiting for {category_name} generation: {e}")
            continue

    # Phase 2: Submit upload tasks to Celery for PARALLEL upload
    print(f"[generate_and_upload_images] Submitting {len(generated_results)} upload tasks to Celery...")
    upload_tasks = []

    for category_name, gen_result in generated_results.items():
        image_bytes = gen_result.get("image_bytes")
        if not image_bytes:
            print(f"[generate_and_upload_images] No image bytes for {category_name}, skipping upload...")
            continue

        file_name = f"generated_{category_name}_{uuid.uuid4().hex[:8]}.jpg"
        print(f"[generate_and_upload_images] Submitting upload task: {file_name}")

        celery_task = upload_image_task.apply_async(
            args=[image_bytes, file_name, bucket_name],
            countdown=0,
        )
        upload_tasks.append((category_name, celery_task))

    # Wait for all upload tasks to complete
    print(f"[generate_and_upload_images] Waiting for {len(upload_tasks)} upload tasks...")
    for category_name, celery_task in upload_tasks:
        try:
            result = celery_task.get(timeout=120)  # 2 minute timeout for upload
            print(f"[generate_and_upload_images] Upload task for {category_name} completed")

            if result and result.get("success"):
                generated_items.append(result)
            else:
                print(f"[generate_and_upload_images] Upload failed for {category_name}: {result}")
        except Exception as e:
            print(f"[generate_and_upload_images] ERROR waiting for {category_name} upload: {e}")
            continue

    print(f"[generate_and_upload_images] Completed - Generated and uploaded {len(generated_items)} images")
    return generated_items

