from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application exception following RFC 7807 problem details."""

    def __init__(
        self,
        code: str,
        title: str,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        meta: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(detail)
        self.code = code
        self.title = title
        self.detail = detail
        self.status_code = status_code
        self.meta = meta or {}

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "type": "about:blank",
            "title": self.title,
            "status": self.status_code,
            "detail": self.detail,
            "code": self.code,
        }
        if self.meta:
            result["meta"] = self.meta
        return result


class NotFoundError(AppError):
    def __init__(self, detail: str = "Resource not found", code: str = "RESOURCE_NOT_FOUND"):
        super().__init__(
            code=code,
            title="Not Found",
            detail=detail,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Invalid credentials", code: str = "UNAUTHORIZED"):
        super().__init__(
            code=code,
            title="Unauthorized",
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(AppError):
    def __init__(self, detail: str = "You do not have permission to perform this action", code: str = "FORBIDDEN"):
        super().__init__(
            code=code,
            title="Forbidden",
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ConflictError(AppError):
    def __init__(self, detail: str = "Resource conflict", code: str = "CONFLICT"):
        super().__init__(
            code=code,
            title="Conflict",
            detail=detail,
            status_code=status.HTTP_409_CONFLICT,
        )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", []))
            errors.append({"field": loc, "message": err.get("msg", "Validation error")})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "type": "about:blank",
                "title": "Validation Error",
                "status": 422,
                "detail": "The request body or parameters failed validation.",
                "code": "VALIDATION_ERROR",
                "errors": errors,
            },
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Never expose raw stack traces or internal errors to users
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "type": "about:blank",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred. Please try again later.",
                "code": "INTERNAL_SERVER_ERROR",
            },
            media_type="application/problem+json",
        )
