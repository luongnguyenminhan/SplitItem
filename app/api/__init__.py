from fastapi import APIRouter

from app.api.endpoints.image_splitter import router as image_splitter
from app.api.endpoints.virtual_tryon import router as virtual_tryon

api_router = APIRouter()

api_router.include_router(image_splitter)
api_router.include_router(virtual_tryon)
