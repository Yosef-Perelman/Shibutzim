from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
)

from app.core.enums import Role
from app.core.security import BCRYPT_MAX_BYTES


class UserOut(BaseModel):
    """A user as the API shows them. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: Role
    hourly_rate: Decimal
    is_active: bool


EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PASSWORD_MIN_LENGTH = 8


class UserCreate(BaseModel):
    """A manager adds a person. The password is the initial one and is never returned."""

    email: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=255, pattern=EMAIL_PATTERN)
    ]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    role: Role = Role.employee
    hourly_rate: Annotated[Decimal, Field(gt=0, le=10_000, decimal_places=2)]
    password: Annotated[str, Field(min_length=PASSWORD_MIN_LENGTH)]

    @field_validator("password")
    @classmethod
    def check_password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode()) > BCRYPT_MAX_BYTES:
            raise ValueError(f"password must be at most {BCRYPT_MAX_BYTES} bytes")
        return value


class UserStatusUpdate(BaseModel):
    """Deactivate or reactivate. Nothing else about a user changes through the API."""

    model_config = ConfigDict(extra="forbid")

    is_active: StrictBool
