from pydantic import BaseModel


class AudioConfig(BaseModel):
    mime_type: str
    sampling_rate: int | None = None
