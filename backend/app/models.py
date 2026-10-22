from pydantic import BaseModel


class Service(BaseModel):
    id: int
    name: str
    duration_minutes: int
    price_rand: int
