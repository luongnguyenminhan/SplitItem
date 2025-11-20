"""
Virtual Try-On request/response schemas for API validation.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ClothingItemSchema(BaseModel):
    """Schema for a clothing item."""
    image_url: str = Field(..., description="URL to the clothing item image")

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, v: str) -> str:
        """Validate that image_url is not empty."""
        if not v or not v.strip():
            raise ValueError("image_url cannot be empty")
        return v


class VirtualTryOnRequestSchema(BaseModel):
    """Schema for virtual try-on request."""
    human_image: bytes = Field(..., description="Full-body human image file (JPEG, PNG, or WebP)")
    clothing_items: list[ClothingItemSchema] = Field(
        ..., 
        description="List of clothing item URLs (minimum 1, maximum 3)",
        min_items=1,
        max_items=3
    )


class VirtualTryOnResponseSchema(BaseModel):
    """Schema for virtual try-on response (202 Accepted)."""
    time: str = Field(..., description="Unique identifier for the try-on task")
    url: str = Field(..., description="Current task status")


class TryOnStatusSchema(BaseModel):
    """Schema for try-on status response."""
    task_id: str = Field(..., description="Unique identifier for the try-on task")
    status: str = Field(..., description="Current status: pending, processing, completed, or failed")
    result_url: Optional[str] = Field(None, description="URL to the generated try-on image (when completed)")
    error: Optional[str] = Field(None, description="Error message if the task failed")
    created_at: datetime = Field(..., description="Timestamp when the task was created")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when the task completed")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "result_url": "http://minio:9000/sop/tryon_550e8400-e29b-41d4-a716-446655440000_2024-01-01T00-00-00.jpg",
                "error": None,
                "created_at": "2024-01-01T00:00:00",
                "completed_at": "2024-01-01T00:05:00"
            }
        }
