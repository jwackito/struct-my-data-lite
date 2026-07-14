from fastapi import Depends, FastAPI, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Document
from app.storage import save_file

app = FastAPI(title="Struct My Data")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload(file: UploadFile, db: AsyncSession = Depends(get_db)):
    content = await file.read()
    if len(content) > settings.max_upload_size:
        raise HTTPException(status_code=413, detail="File exceeds maximum upload size")

    storage_path = save_file(file.filename or "unnamed", content)

    doc = Document(
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        storage_path=storage_path,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "content_type": doc.content_type,
        "file_size": doc.file_size,
        "storage_path": doc.storage_path,
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat(),
    }
