"""
Virtual Try-On service layer with core business logic.

This module handles validation, prompt construction, and file persistence
for the virtual try-on feature.
"""
import base64
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image

from app.schemas.virtual_tryon import ClothingItemSchema


def validate_human_image(file_bytes: bytes) -> tuple[bytes, str]:
    """
    Validate image format and convert to JPEG for maximum compatibility.

    Validates that the image is in a supported format (JPEG, PNG, or WebP),
    converts it to JPEG, and handles RGBA to RGB conversion.

    Args:
        file_bytes: Raw image bytes from uploaded file

    Returns:
        Tuple of (converted_image_bytes, mime_type)

    Raises:
        ValueError: If image format is invalid or image cannot be processed
    """
    try:
        # Open and validate image
        img = Image.open(io.BytesIO(file_bytes))

        # Check supported formats
        supported_formats = {"JPEG", "PNG", "WEBP"}
        if img.format and img.format.upper() not in supported_formats:
            raise ValueError(
                f"Unsupported image format: {img.format}. "
                f"Supported formats: {', '.join(supported_formats)}"
            )

        # Check minimum image dimensions
        if img.size[0] < 100 or img.size[1] < 100:
            raise ValueError(
                f"Image dimensions too small: {img.size}. "
                f"Minimum required: 100x100 pixels"
            )

        # Convert RGBA to RGB
        if img.mode == "RGBA":
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])
            img = rgb_img
        elif img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # Convert to JPEG for maximum compatibility
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=95)
        converted_bytes = output.getvalue()

        return converted_bytes, "image/jpeg"

    except Image.UnidentifiedImageError as e:
        raise ValueError(f"Invalid image file: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error processing image: {str(e)}")


def validate_clothing_items(clothing_items: list[ClothingItemSchema]) -> bool:
    """
    Validate that 1-3 clothing items are provided with valid URLs.

    Validates:
    - 1-3 items are provided
    - Each item has a valid image URL

    Args:
        clothing_items: List of ClothingItemSchema objects

    Returns:
        True if validation passes

    Raises:
        ValueError: If validation fails
    """
    if not clothing_items:
        raise ValueError("At least one clothing item is required")

    if len(clothing_items) > 3:
        raise ValueError(
            f"Maximum 3 clothing items allowed, got {len(clothing_items)}"
        )

    # Validate each item has a URL
    for idx, item in enumerate(clothing_items, 1):
        if not item.image_url or not item.image_url.strip():
            raise ValueError(f"Clothing item {idx} has empty image URL")

    return True
