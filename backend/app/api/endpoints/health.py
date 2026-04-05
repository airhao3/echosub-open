from fastapi import APIRouter

router = APIRouter()

@router.get("", tags=["Health"])
@router.get("/", tags=["Health"])
async def health_check():
    """Health check endpoint used to verify API is running"""
    return {"status": "ok"}
