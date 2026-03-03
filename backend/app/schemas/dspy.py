from pydantic import BaseModel


class TraceCommentUpdate(BaseModel):
    comment: str
