from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.services.image_splitter import generate_and_upload_images

router = APIRouter(prefix=settings.API_V1_STR, tags=["Image Splitter"])


@router.post("/split-image/")
async def split_image(image_file: UploadFile = File(...)) -> dict:
    """
    Generate images from uploaded image and upload to MinIO.

    Args:
        image_file: Uploaded image file

    Returns:
        JSON with generated images and their URLs
    """
    try:
        print(f"[split_image] Received request with file: {image_file.filename}")

        # Call service layer to handle all business logic
        generated_items = await generate_and_upload_images(
            image_file=image_file,
            bucket_name=settings.MINIO_PUBLIC_BUCKET_NAME,
        )

        print(f"[split_image] Successfully processed {len(generated_items)} items")

        return {
            "success": True,
            "message": f"Successfully generated {len(generated_items)} images",
            "items": generated_items,
        }

    except Exception as e:
        print(f"[split_image] ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))
