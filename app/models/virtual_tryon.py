"""
Virtual Try-On data models for database persistence.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, String, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class VirtualTryOnTask(Base):
    """
    Database model for storing virtual try-on task information.
    
    Attributes:
        task_id: Unique identifier for the try-on task
        status: Current status (pending, processing, completed, failed)
        human_image_url: URL or path to the uploaded human image
        clothing_items: JSON array of clothing items with names and URLs
        result_url: URL to the generated try-on image (when completed)
        error_message: Error details if the task failed
        created_at: Timestamp when the task was created
        completed_at: Timestamp when the task completed (success or failure)
    """
    __tablename__ = "virtual_tryon_tasks"

    task_id = Column(String(36), primary_key=True, index=True)
    status = Column(String(20), default="pending", index=True)  # pending, processing, completed, failed
    human_image_url = Column(String(500))
    clothing_items = Column(JSON)  # Array of {name, image_url}
    result_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<VirtualTryOnTask(task_id={self.task_id}, status={self.status})>"
