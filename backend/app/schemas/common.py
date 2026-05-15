from pydantic import BaseModel


class PageParams(BaseModel):
    page: int = 1
    page_size: int = 20


class PageResult(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class MessageResponse(BaseModel):
    message: str
