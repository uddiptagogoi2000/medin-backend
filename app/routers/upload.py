from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.auth import verify_token
import cloudinary.uploader

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    payload=Depends(verify_token),
):
    try:
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file.file,
            folder="medin_posts",
            resource_type="image"
        )

        return {
            "url": result["secure_url"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
