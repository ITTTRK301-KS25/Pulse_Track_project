from typing import Optional, Any
from fastapi import Request
from fastapi.responses import JSONResponse
from app.schemas.response import ResponseCreate
from datetime import datetime, timezone

def create_response(
        req: Request,
        status_code: int,
        message: str,
        data: Optional[Any],
        error: Optional[Any]
):
    return JSONResponse(
        status_code=status_code,
        content=ResponseCreate(
            status_code=status_code,
            message=message,
            data=data,
            error=error,
            timestamp=str(datetime.now(timezone.utc).isoformat()),
            path=req.url.path
        ).model_dump(mode="json")
    )