from fastapi import APIRouter
from app.api.v1 import chat, images, design, sketch

api_router = APIRouter()

api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(images.router, prefix="/images", tags=["images"])
api_router.include_router(design.router, prefix="/design", tags=["design"])
api_router.include_router(sketch.router, prefix="/sketch", tags=["sketch"])
