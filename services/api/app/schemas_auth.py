from typing import Literal

from pydantic import Field

from app.schemas import Schema

Role = Literal["shop_manager", "canteen_manager", "campus_admin", "safety_officer", "owner", "venue_manager"]


class Me(Schema):
    id: str
    email: str
    display_name: str
    role: Role
    canteen_ids: list[str]
    shop_ids: list[str]


class LoginIn(Schema):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class Session(Schema):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int
    user: Me
