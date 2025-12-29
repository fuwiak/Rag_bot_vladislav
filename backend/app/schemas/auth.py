"""
Схемы для авторизации
"""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Запрос на авторизацию"""
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)  # Zmieniono z 6 na 1, aby umożliwić hasło "admin"


class LoginResponse(BaseModel):
    """Ответ с токеном"""
    access_token: str
    token_type: str = "bearer"


class ResetPasswordRequest(BaseModel):
    """Запрос на сброс пароля"""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1, max_length=255)


class ResetPasswordResponse(BaseModel):
    """Ответ на сброс пароля"""
    message: str
    username: str

