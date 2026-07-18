from fastapi import HTTPException, status

class PropertySystemException(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class AuthenticationError(PropertySystemException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)

class PermissionDeniedError(PropertySystemException):
    def __init__(self, message: str = "Permission denied for this operation"):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)

class ResourceNotFoundError(PropertySystemException):
    def __init__(self, message: str = "Requested resource not found"):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)