from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.core.enums import Role


class UserOut(BaseModel):
    """A user as the API shows them. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: Role
    hourly_rate: Decimal
    is_active: bool
