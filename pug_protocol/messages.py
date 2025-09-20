from __future__ import annotations

from typing import Any, Literal, Mapping, Self

from pydantic import AwareDatetime, BaseModel, Field

from .configs import AudioConfig
from .types import Base64
from .utilities import AnyUtility


class Request(BaseModel):
    kind: str
    client_start_time: AwareDatetime | None = None
    server_start_time: AwareDatetime | None = None


class Response(BaseModel):
    kind: str
    client_start_time: AwareDatetime | None = None
    server_start_time: AwareDatetime | None = None
    server_end_time: AwareDatetime | None = None

    @classmethod
    def from_request(cls, request: Request, **kwargs: Any) -> Self:
        return cls(
            client_start_time=request.client_start_time,
            server_start_time=request.server_start_time,
            **kwargs,
        )


class ErrorResponse(Response):
    kind: Literal["error"] = "error"
    error: str


class AuthenticateRequest(Request):
    kind: Literal["authenticate"] = "authenticate"
    access_token: str


class AuthenticateResponse(Response):
    kind: Literal["authenticate"] = "authenticate"


class PingRequest(Request):
    kind: Literal["ping"] = "ping"


class PingResponse(Response):
    kind: Literal["ping"] = "ping"


class SetServiceProfileRequest(Request):
    kind: Literal["set_service_profile"] = "set_service_profile"
    service_profile: str


class SetServiceProfileResponse(Response):
    kind: Literal["set_service_profile"] = "set_service_profile"


class AddAudioRequest(Request):
    kind: Literal["add_audio"] = "add_audio"
    audio: Base64
    config: AudioConfig | None = None


class AddAudioResponse(Response):
    kind: Literal["add_audio"] = "add_audio"


class ClearAudioRequest(Request):
    kind: Literal["clear_audio"] = "clear_audio"


class ClearAudioResponse(Response):
    kind: Literal["clear_audio"] = "clear_audio"


class CheckTurnRequest(Request):
    kind: Literal["check_turn"] = "check_turn"


class CheckTurnResponse(Response):
    kind: Literal["check_turn"] = "check_turn"
    is_user_still_speaking: bool


class TranscribeRequest(Request):
    kind: Literal["transcribe"] = "transcribe"
    language_code: str = "en"


class TranscribeResponse(Response):
    kind: Literal["transcribe"] = "transcribe"
    text: str


class AddKeywordsRequest(Request):
    kind: Literal["add_keywords"] = "add_keywords"
    keywords: list[str]


class AddKeywordsResponse(Response):
    kind: Literal["add_keywords"] = "add_keywords"


class RemoveKeywordsRequest(Request):
    kind: Literal["remove_keywords"] = "remove_keywords"
    keywords: list[str]


class RemoveKeywordsResponse(Response):
    kind: Literal["remove_keywords"] = "remove_keywords"


class DetectKeywordsRequest(Request):
    kind: Literal["detect_keywords"] = "detect_keywords"


class DetectKeywordsResponse(Response):
    kind: Literal["detect_keywords"] = "detect_keywords"
    keywords: list[str]


class AddSpeakerRequest(Request):
    kind: Literal["add_speaker"] = "add_speaker"
    speaker: str
    audio: Base64


class AddSpeakersResponse(Response):
    kind: Literal["add_speaker"] = "add_speaker"


class RemoveSpeakersRequest(Request):
    kind: Literal["remove_speakers"] = "remove_speakers"
    speakers: list[str]


class RemoveSpeakersResponse(Response):
    kind: Literal["remove_speakers"] = "remove_speakers"


class DetectSpeakersRequest(Request):
    kind: Literal["detect_speakers"] = "detect_speakers"


class DetectSpeakersResponse(Response):
    kind: Literal["detect_speakers"] = "detect_speakers"
    speakers: list[str]


class SetConfigurationRequest(Request):
    kind: Literal["set_configuration"] = "set_configuration"
    config: Configuration


class SetConfigurationResponse(Response):
    kind: Literal["set_configuration"] = "set_configuration"


class MergeConfigurationRequest(Request):
    kind: Literal["merge_configuration"] = "merge_configuration"
    references: list[Reference] = Field(default_factory=list)


class MergeConfigurationResponse(Response):
    kind: Literal["merge_configuration"] = "merge_configuration"
    utilities: list[str]


class GetConfigurationRequest(Request):
    kind: Literal["get_configuration"] = "get_configuration"


class GetConfigurationResponse(Response):
    kind: Literal["get_configuration"] = "get_configuration"
    config: Configuration


class RenderPromptRequest(Request):
    kind: Literal["render_prompt"] = "render_prompt"
    context: dict[str, Any] = Field(default_factory=dict)


class RenderPromptResponse(Response):
    kind: Literal["render_prompt"] = "render_prompt"
    prompt: str


class InteractRequest(Request):
    kind: Literal["interact"] = "interact"
    text: str = ""
    speakers: list[str] = Field(default_factory=list)
    # A mapping of parameters that will be made available in the prompt template.
    context: dict[str, Any] = Field(default_factory=dict)
    # A list of utility names that should be called when user input is available.
    # Evaluation of these utilities happens before the prompt is rendered, so that
    # their values can be used in the prompt.
    # Note: Use with caution, as this delays the assistant output and everything
    # that follows (audio output, output utilities, etc.).
    on_input: list[str] = Field(default_factory=list)
    # A list of utility names that should be called when user input is available.
    # Unlike the `on_input` utilities, these are *non-blocking* and their outputs
    # will not be available in the context for the prompt.
    on_input_non_blocking: list[str] = Field(default_factory=list)
    # A list of utility names that should be called when assistant output is
    # available.
    on_output: list[str] = Field(default_factory=list)
    audio_output: bool = True
    language_code: str = "en"


class InteractResponse(Response):
    kind: Literal["interact"] = "interact"
    event: str


class InteractionStartedEvent(InteractResponse):
    event: Literal["interaction_started"] = "interaction_started"


class TextEvent(InteractResponse):
    event: Literal["text"] = "text"
    text: str


class SafetyPolicyEvent(InteractResponse):
    event: Literal["safety_policy"] = "safety_policy"


class TextCompleteEvent(InteractResponse):
    event: Literal["text_complete"] = "text_complete"


class AudioEvent(InteractResponse):
    event: Literal["audio"] = "audio"
    audio: Base64


class AudioCompleteEvent(InteractResponse):
    event: Literal["audio_complete"] = "audio_complete"


class DataEvent(InteractResponse):
    event: Literal["data"] = "data"
    data: dict[str, Any]


class InteractionErrorEvent(InteractResponse):
    event: Literal["interaction_error"] = "interaction_error"
    error: str


class InteractionCompleteEvent(InteractResponse):
    event: Literal["interaction_complete"] = "interaction_complete"


class InterruptRequest(Request):
    kind: Literal["interrupt"] = "interrupt"
    # While we only allow one interaction at a time due to conversation history
    # management, the purpose of this field is to verify that the interrupt is
    # intended on the right interaction.
    target_uid: str
    at_character: int | None = None


class InterruptResponse(Response):
    kind: Literal["interrupt"] = "interrupt"


class RunRequest(Request):
    kind: Literal["run"] = "run"
    utilities: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    bindings: dict[str, str] = Field(default_factory=dict)


class RunResponse(Response):
    kind: Literal["run"] = "run"


class Configuration(BaseModel):
    prompt: str | Reference | None = None
    temperature: float | None = None
    utilities: dict[str, AnyUtility | Reference | None] = Field(default_factory=dict)
    safety_policy: str | Reference | None = None


class Reference(BaseModel):
    reference: str


def _get_subclasses_recursive[T](cls: type[T]) -> list[type[T]]:
    result = [cls]
    for subclass in cls.__subclasses__():
        result.extend(_get_subclasses_recursive(subclass))
    return result


_missing_field_default = "N/A"


type KindAndEvent = tuple[str, str]


def _get_field_default(cls: type[BaseModel], field: str) -> str:
    field_spec = cls.model_fields.get(field)
    if not field_spec:
        return _missing_field_default
    return field_spec.default


def _get_kind_and_event_defaults(cls: type[BaseModel]) -> KindAndEvent:
    return _get_field_default(cls, "kind"), _get_field_default(cls, "event")


_request_by_kind_and_event = {_get_kind_and_event_defaults(cls): cls for cls in _get_subclasses_recursive(Request)}


_response_by_kind_and_event = {_get_kind_and_event_defaults(cls): cls for cls in _get_subclasses_recursive(Response)}


def _get_by_kind_and_event[T: BaseModel](index: Mapping[KindAndEvent, type[T]], message: dict[str, Any]) -> T:
    kind = message.get("kind")
    if not kind:
        raise ValueError("missing 'kind' field")
    event = message.get("event", _missing_field_default)
    kind_and_event = (kind, event)
    if kind_and_event not in index:
        raise ValueError(
            f"invalid 'kind'/'event' combination {kind_and_event!r} "
            f"(expected one of {', '.join(repr(key) for key in index)})"
        )
    return index[kind_and_event].model_validate(message)


def get_request(message: dict[str, Any]) -> Request:
    return _get_by_kind_and_event(_request_by_kind_and_event, message)


def get_response(message: dict[str, Any]) -> Response:
    return _get_by_kind_and_event(_response_by_kind_and_event, message)
