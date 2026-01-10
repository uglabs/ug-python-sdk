import base64
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer


def _accept_base64str_or_bytes(value: bytes | str) -> bytes:
    match value:
        case bytes():
            return value
        case str():
            return base64.decodebytes(value.encode())


def _serialize_base64(value: bytes) -> str:
    return base64.encodebytes(value).decode()


type Base64 = Annotated[
    bytes,
    BeforeValidator(_accept_base64str_or_bytes),
    PlainSerializer(_serialize_base64),
]
