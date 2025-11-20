import io
import json
import logging
import mimetypes
from datetime import datetime

import google.genai as genai
from google.genai import types
from PIL import Image

from app.utils.image_workflow.prompt import CATEGORIES

logger = logging.getLogger(__name__)


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



async def generate_tryon_image(
    human_image_bytes: bytes,
    clothing_urls: list[str],
    task_id: str,
) -> dict:
    """
    Generate try-on image: download images -> convert to parts -> send to Gemini.

    Args:
        human_image_bytes: Human image bytes
        clothing_urls: List of clothing URLs
        task_id: Task ID

    Returns:
        Dict with success, image_bytes, or error
    """
    import aiohttp
    from app.utils.redis import get_redis_client
    
    try:
        print(f"[generate_tryon_image] Started: {task_id}")
        
        # Download all images
        print(f"[generate_tryon_image] Downloading {len(clothing_urls)} images")
        all_images = [human_image_bytes]
        
        for url in clothing_urls:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        raise Exception(f"Download failed: {url} - HTTP {resp.status}")
                    img_bytes = await resp.read()
                    all_images.append(img_bytes)
                    print(f"[generate_tryon_image] Downloaded: {len(img_bytes)} bytes")
        
        # Convert all images to parts
        print(f"[generate_tryon_image] Converting {len(all_images)} images to parts")
        contents = [types.Part.from_text(text="""Photorealistic virtual try-on result of the person from the input photo. 
Keep the person’s exact face, body proportions, pose, hairstyle, and lighting. 
Do not change facial features, gender, ethnicity, or age.

Always remove and replace any existing clothing on the person with the provided items if they cover the same body region. Do not preserve or reuse the original clothing under any circumstances.

Dress the person only with the provided clothing and accessories. 
Use only visible body areas for try-on:
- If legs are not visible, ignore pants and shoes.
- If feet are not visible, ignore footwear.
- If torso is visible, apply shirts/jackets appropriately.
- If multiple items cover the same area, pick the most visually complete one.

If the person is already wearing pants or shorts and the lower body is visible, remove the existing pants and replace them with the provided pants. Do not layer two pants together. 
Only replace clothing if the replacement area has real visible body reference beneath it. 

If the person is already wearing a shirt, t-shirt, or jacket and the torso area is visible, remove the existing top and replace it with the provided top. Do not layer two tops unless the provided item is explicitly a jacket or coat intended to be worn over another top.

If the provided item is a jacket or coat, layer it naturally over the existing or replaced top only if the chest and neck area are sufficiently visible to form a realistic inner clothing layer. If the body reference is not clear enough to generate a believable inner clothing layer, replace the top entirely instead of layering.

If a body region is not fully visible (such as covered by limbs, shadows, occlusion, or cropped), do not hallucinate anatomy or invent missing body parts. Instead, reconstruct the hidden area only to the minimal extent required to correctly fit the provided clothing without unrealistic body fabrication. The person’s real body shape must remain unchanged.

Fit clothing naturally to the body with realistic wrinkles and accurate fabric draping. 
Align patterns, logos, seams, buttons, and collars with the body as in real clothing. 
Do not invent new textures, colors, shapes, or outfit items.

No extra objects, no added models, no backgrounds changes. 
Preserve original photo background and lighting consistency.

Output: a single high-resolution photorealistic try-on image of the person wearing the provided outfit.

""")]
        
        for img_bytes in all_images:
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
        
        # Send to Gemini
        print(f"[generate_tryon_image] Sending to Gemini with {len(contents)} parts")
        client = _get_gemini_client()
        

        
        image_bytes = b""
        for chunk in client.models.generate_content_stream(
            model="gemini-2.5-flash-image",
            contents=contents,
        ):
            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                part = chunk.candidates[0].content.parts[0]
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    print(f"[generate_tryon_image] Received: {len(image_bytes)} bytes")
        
        if not image_bytes:
            raise Exception("No image data received from Gemini")
        
        print(f"[generate_tryon_image] Success: {len(image_bytes)} bytes")
        return {"success": True, "task_id": task_id, "image_bytes": image_bytes}
        
    except Exception as e:
        print(f"[generate_tryon_image] Error: {e}")
        try:
            redis_client = get_redis_client()
            redis_client.hset(f"tryon_task:{task_id}", mapping={
                "status": "failed",
                "error": str(e),
                "updated_at": datetime.utcnow().isoformat(),
            })
        except:
            pass
        return {"success": False, "task_id": task_id, "error": str(e)}
