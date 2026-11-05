from fastapi import FastAPI, Request, HTTPException, status
from app.services.response import create_response
from fastapi.exceptions import RequestValidationError

def register_exception_handler(app: FastAPI):

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(req: Request, exc: RequestValidationError):
        return create_response(req=req, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, message="Lỗi dữ liệu đầu vào không hợp lệ!", data=None, error=exc.errors())

    @app.exception_handler(HTTPException)
    async def exception_client(req: Request, exc: HTTPException):
        return create_response(req=req, status_code=exc.status_code, message=exc.detail, data=None, error="Client error message")

    @app.exception_handler(Exception)
    async def global_exception_handler(req: Request, exc: Exception):
        return create_response(req=req, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Lỗi hệ thống nội bộ! Vui lòng thử lại sau!", data=None, error=str(exc))