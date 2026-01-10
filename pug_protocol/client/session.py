from __future__ import annotations

import contextlib
import datetime
import logging
from types import TracebackType
from typing import TYPE_CHECKING, Any, AsyncIterator, Iterable, Iterator, Mapping, Self

from pug_protocol import messages, rpc, utilities
from pug_protocol.configs import AudioConfig
from pydantic import BaseModel

if TYPE_CHECKING:
    from .client import Client


class Session:

    def __init__(self, access_token: str | None, channel: rpc.Channel, logger: logging.Logger) -> None:
        self.access_token: str | None = access_token
        self.rpc = rpc.RPC("server", channel, logger)
        self.started: bool = False
        self.exit_stack = contextlib.AsyncExitStack()

    @staticmethod
    def create_default_channel(client: Client, logger: logging.Logger) -> rpc.WebsocketClientChannel:
        # The websocket channel will fix the HTTP/WS protocol in the URL.
        return rpc.WebsocketClientChannel(f"{client.url}/interact", name="client-session", logger=logger)

    @classmethod
    def from_client(cls, client: Client, logger: logging.Logger) -> Self:
        return cls(client.access_token, cls.create_default_channel(client, logger), logger)

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exception: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.stop()

    async def start(self) -> None:
        await self.exit_stack.enter_async_context(self.rpc)
        if self.access_token:
            # No need to explicitly wait for the auth request to complete, it'll
            # be processed on the server side anyhow before everything else.
            self.authenticate()
        self.started = True

    async def stop(self) -> None:
        self.started = False
        await self.exit_stack.aclose()

    def _make_request(self, request: messages.Request) -> rpc.ResponseFuture[dict[str, Any]]:
        request.client_start_time = datetime.datetime.now(datetime.UTC)
        return self.rpc.make_request(request.kind, self._serialize(request))

    def _send_on_stream(self, stream: rpc.RPC.Stream, request: messages.Request) -> None:
        request.client_start_time = datetime.datetime.now(datetime.UTC)
        return stream.send(request.kind, self._serialize(request))

    def authenticate(self) -> rpc.ResponseFuture[None]:
        if not self.access_token:
            raise ValueError("access token is required")
        return self._make_request(
            messages.AuthenticateRequest(access_token=self.access_token),
        ).transform(self._no_response)

    def ping(self) -> rpc.ResponseFuture[None]:
        return self._make_request(
            messages.PingRequest(),
        ).transform(self._no_response)

    def set_configuration(
        self,
        *,
        prompt: str | messages.Reference | None = None,
        temperature: float | None = None,
        utilities: Mapping[str, utilities.AnyUtility | messages.Reference | None] | None = None,
        safety_policy: str | messages.Reference | None = None,
        voice_profile: messages.VoiceProfile | messages.Reference | None = None,
        debug: bool = False,
    ) -> rpc.ResponseFuture[None]:
        return self._make_request(
            messages.SetConfigurationRequest(
                config=messages.Configuration(
                    prompt=prompt,
                    temperature=temperature,
                    utilities=dict(utilities or {}),
                    safety_policy=safety_policy,
                    voice_profile=voice_profile,
                    debug=debug,
                )
            ),
        ).transform(self._no_response)

    def set_configuration_ref(self, reference: messages.Reference) -> rpc.ResponseFuture[None]:
        """Set configuration from a stored reference.

        Instead of passing individual configuration fields, pass a Reference
        to a stored Configuration object. The reference is resolved server-side.

        Example:
            await session.set_configuration_ref(Reference(reference="my_config@v1"))
        """
        return self._make_request(
            messages.SetConfigurationRequest(config=reference),
        ).transform(self._no_response)

    def get_configuration(self) -> rpc.ResponseFuture[messages.Configuration]:
        return self._make_request(
            messages.GetConfigurationRequest(),
        ).transform(self._on_get_configuration)

    def merge_configuration(self, references: list[messages.Reference]) -> rpc.ResponseFuture[list[str]]:
        return self._make_request(
            messages.MergeConfigurationRequest(references=references),
        ).transform(self._on_merge_configuration)

    def render_prompt(self, *, context: dict[str, Any]) -> rpc.ResponseFuture[str]:
        return self._make_request(
            messages.RenderPromptRequest(context=context),
        ).transform(self._on_render_prompt)

    def set_service_profile(self, service_profile: str) -> rpc.ResponseFuture[None]:
        return self._make_request(
            messages.SetServiceProfileRequest(service_profile=service_profile),
        ).transform(self._no_response)

    def add_audio(self, audio: bytes, config: AudioConfig | None = None) -> rpc.ResponseFuture[None]:
        return self._make_request(
            messages.AddAudioRequest(audio=audio, config=config),
        ).transform(self._no_response)

    def clear_audio(self) -> rpc.ResponseFuture[None]:
        return self._make_request(
            messages.ClearAudioRequest(),
        ).transform(self._no_response)

    def check_turn(self) -> rpc.ResponseFuture[bool]:
        return self._make_request(
            messages.CheckTurnRequest(),
        ).transform(self._on_check_turn)

    def transcribe(self, language_code: str) -> rpc.ResponseFuture[str]:
        return self._make_request(
            messages.TranscribeRequest(language_code=language_code),
        ).transform(self._on_transcribe)

    def add_keywords(self, keywords: list[str]) -> rpc.ResponseFuture[None]:
        return self._make_request(
            messages.AddKeywordsRequest(keywords=keywords),
        ).transform(self._no_response)

    def remove_keywords(self, keywords: list[str]) -> rpc.ResponseFuture[None]:
        return self._make_request(
            messages.RemoveKeywordsRequest(keywords=keywords),
        ).transform(self._no_response)

    def detect_keywords(self) -> rpc.ResponseFuture[list[str]]:
        return self._make_request(
            messages.DetectKeywordsRequest(),
        ).transform(self._on_detect_keywords)

    def add_speaker(self, speaker: str, audio: bytes) -> rpc.ResponseFuture[None]:
        return self._make_request(
            messages.AddSpeakerRequest(speaker=speaker, audio=audio),
        ).transform(self._no_response)

    def remove_speakers(self, speakers: list[str]) -> rpc.ResponseFuture[None]:
        return self._make_request(
            messages.RemoveSpeakersRequest(speakers=speakers),
        ).transform(self._no_response)

    def detect_speakers(self) -> rpc.ResponseFuture[list[str]]:
        return self._make_request(
            messages.DetectSpeakersRequest(),
        ).transform(self._on_detect_speakers)

    @contextlib.contextmanager
    def interact(
        self,
        *,
        audio_output: bool = True,
        text: str = "",
        context: dict[str, Any] = {},
        on_input: Iterable[str] = (),
        on_output: Iterable[str] = (),
        on_input_non_blocking: Iterable[str] = (),
    ) -> Iterator[AsyncIterator[dict[str, Any]]]:
        with self.rpc.open_stream() as stream:
            self._send_on_stream(
                stream,
                messages.InteractRequest(
                    audio_output=audio_output,
                    text=text,
                    context=context,
                    on_input=list(on_input),
                    on_output=list(on_output),
                    on_input_non_blocking=list(on_input_non_blocking),
                ),
            )
            yield aiter(stream)

    def _no_response(self, response: dict[str, Any]) -> None:
        return None

    def _on_check_turn(self, response: dict[str, Any]) -> bool:
        return messages.CheckTurnResponse.model_validate(response).is_user_still_speaking

    def _on_transcribe(self, response: dict[str, Any]) -> str:
        return messages.TranscribeResponse.model_validate(response).text

    def _on_detect_keywords(self, response: dict[str, Any]) -> list[str]:
        return messages.DetectKeywordsResponse.model_validate(response).keywords

    def _on_detect_speakers(self, response: dict[str, Any]) -> list[str]:
        return messages.DetectSpeakersResponse.model_validate(response).speakers

    def _on_render_prompt(self, response: dict[str, Any]) -> str:
        return messages.RenderPromptResponse.model_validate(response).prompt

    def _on_get_configuration(self, response: dict[str, Any]) -> messages.Configuration:
        return messages.GetConfigurationResponse.model_validate(response).config

    def _on_merge_configuration(self, response: dict[str, Any]) -> list[str]:
        return messages.MergeConfigurationResponse.model_validate(response).utilities

    def _serialize(self, data: BaseModel | None) -> dict[str, Any] | None:
        if data is None:
            return None
        return data.model_dump(mode="json", exclude_none=True)
