from fastapi import APIRouter

from app.api.endpoints.image_splitter import router as image_splitter

api_router = APIRouter()

api_router.include_router(image_splitter)
