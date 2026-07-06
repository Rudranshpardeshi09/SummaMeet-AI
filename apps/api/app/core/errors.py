from fastapi import HTTPException

class AppError(HTTPException):
    """Base class for all application errors."""
    def __init__(self, status_code: int, type: str, title: str, detail: str, instance: str | None = None):
        super().__init__(status_code=status_code, detail=detail)
        self.type = type
        self.title = title
        self.instance = instance

class NotFoundError(AppError):
    def __init__(self, detail: str, instance: str | None = None):
        super().__init__(
            status_code=404,
            type="https://api.notetaker.local/errors/not-found",
            title="Resource Not Found",
            detail=detail,
            instance=instance,
        )

class ValidationError(AppError):
    def __init__(self, detail: str, instance: str | None = None):
        super().__init__(
            status_code=400,
            type="https://api.notetaker.local/errors/validation-error",
            title="Validation Error",
            detail=detail,
            instance=instance,
        )

class ConflictError(AppError):
    def __init__(self, detail: str, instance: str | None = None):
        super().__init__(
            status_code=409,
            type="https://api.notetaker.local/errors/conflict",
            title="Resource Conflict",
            detail=detail,
            instance=instance,
        )

class ForbiddenError(AppError):
    def __init__(self, detail: str, instance: str | None = None):
        super().__init__(
            status_code=403,
            type="https://api.notetaker.local/errors/forbidden",
            title="Forbidden",
            detail=detail,
            instance=instance,
        )
