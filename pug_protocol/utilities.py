from typing import Literal

from pydantic import BaseModel


class Utility(BaseModel):
    type: str


class Classify(Utility):
    type: Literal["classify"] = "classify"


class Extract(Utility):
    type: Literal["extract"] = "extract"
