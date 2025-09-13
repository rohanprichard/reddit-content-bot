from pydantic import BaseModel


class Story(BaseModel):
    story: str
    title: str