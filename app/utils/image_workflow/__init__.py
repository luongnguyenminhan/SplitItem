import io
import mimetypes

import google.genai as genai
from google.genai import types
from PIL import Image

from app.utils.image_workflow.prompt import CATEGORIES


def _get_gemini_client() -> genai.Client:
    """Initialize and return Gemini API client."""
    from app.core.config import settings

    api_key = settings.GOOGLE_API_KEY
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not configured in settings")

    return genai.Client(api_key=api_key)


def _get_mime_type(filename: str) -> str:
    """Detect MIME type from filename."""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def _validate_and_convert_image(file_content: bytes) -> tuple[bytes, str]:
    """
    Validate image format and convert to JPEG for maximum compatibility with Gemini API.

    Args:
        file_content: Raw image bytes

    Returns:
        Tuple of (converted_image_bytes, mime_type)
    """
    try:
        print(f"[_validate_and_convert_image] Input file size: {len(file_content)} bytes")

        # Open and validate image
        img = Image.open(io.BytesIO(file_content))
        print(f"[_validate_and_convert_image] Image format: {img.format}, mode: {img.mode}, size: {img.size}")

        # Check image dimensions
        if img.size[0] < 100 or img.size[1] < 100:
            print(f"[_validate_and_convert_image] WARNING: Small image detected {img.size}, may not work well")

        # Convert RGBA to RGB
        if img.mode == "RGBA":
            print("[_validate_and_convert_image] Converting RGBA to RGB...")
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])
            img = rgb_img
        elif img.mode not in ("RGB", "L"):
            print(f"[_validate_and_convert_image] Converting {img.mode} to RGB...")
            img = img.convert("RGB")

        # Convert to JPEG for maximum compatibility
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=95)
        converted_bytes = output.getvalue()

        print(f"[_validate_and_convert_image] Converted to JPEG: {len(converted_bytes)} bytes")
        return converted_bytes, "image/jpeg"

    except Exception as e:
        print(f"[_validate_and_convert_image] ERROR during validation: {str(e)}")
        # Return original if conversion fails, but still try
        return file_content, "image/jpeg"


def generate_image_from_bytes(file_bytes: bytes, mime_type: str, category: str = "Top") -> bytes:
    """
    Generate a new image based on category prompt using Gemini API.

    Args:
        file_bytes: Image file bytes (already validated and converted)
        mime_type: MIME type of image (e.g., "image/jpeg")
        category: Category key from CATEGORIES (Top or Bot)

    Returns:
        Generated image as bytes
    """
    try:
        print(f"[generate_image] Starting image generation for category: {category}")

        # Get prompt from category
        prompt = CATEGORIES.get(category, CATEGORIES["Top"])
        print(f"[generate_image_from_bytes] Using prompt for category: {category}")

        # Initialize Gemini client
        client = _get_gemini_client()
        print("[generate_image] Gemini client initialized")

        # Create image part from converted bytes
        image_part = types.Part.from_bytes(
            data=file_bytes,
            mime_type=mime_type,
        )

        # Configure content generation for image output
        generate_content_config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio="1:1",
                image_size="1K",
            ),
        )

        # Generate image content
        image_bytes = b""
        print("[generate_image] Starting content stream generation...")

        for chunk in client.models.generate_content_stream(
            model="gemini-2.5-flash-image",
            contents=[
                types.Part.from_text(text=prompt),
                image_part,
            ],
            config=generate_content_config,
        ):
            # Extract image data from chunks
            if chunk.candidates is None or chunk.candidates[0].content is None or chunk.candidates[0].content.parts is None:
                continue

            if chunk.candidates[0].content.parts[0].inline_data and chunk.candidates[0].content.parts[0].inline_data.data:
                inline_data = chunk.candidates[0].content.parts[0].inline_data
                image_bytes = inline_data.data
                print(f"[generate_image] Received image data: {len(image_bytes)} bytes")

        print(f"[generate_image] Image generation completed, total bytes: {len(image_bytes)}")
        return image_bytes if image_bytes else b""

    except Exception as e:
        print(f"[generate_image] ERROR: {e}")
        return b""
