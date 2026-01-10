from typing import Any, Literal, Mapping

from pydantic import BaseModel, TypeAdapter


class Utility(BaseModel):
    type: str


class Classify(Utility):
    type: Literal["classify"] = "classify"
    # The questions is a template like the interaction prompt, and has access to
    # the context relevant to the stage when it's evaluated.
    classification_question: str
    additional_context: str | None = None
    answers: list[str]


class Extract(Utility):
    type: Literal["extract"] = "extract"
    extract_prompt: str
    additional_context: str | None = None


# Note that for deserialization purposes classes that have a utility field
# should use this type instead of the Utility base-class, otherwise the
# deserialization will only load the fields of the base class.
type AnyUtility = Classify | Extract


def get_utility(message: Mapping[str, Any]) -> AnyUtility:
    return TypeAdapter(AnyUtility).validate_python(message)
