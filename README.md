# UG Python SDK

Python SDK for the UG AI Platform - enabling real-time conversational AI interactions with speech-to-text, text-to-speech, and LLM capabilities.

## Installation

```bash
pip install ug-python-sdk
```

Or with Poetry:

```bash
poetry add ug-python-sdk
```

**Requirements:** Python 3.12+

## Quick Start

```python
import asyncio
import logging
from pug_protocol.client import Client

async def main():
    # Create client and authenticate
    client = Client("https://pug.stg.uglabs.app", logging.getLogger())
    await client.login(api_key="your-api-key")

    # Start a session
    async with client.session() as session:
        # Configure the AI assistant
        await session.set_configuration(
            prompt="You are a helpful assistant.",
            temperature=0.7,
        )

        # Have a conversation
        with session.interact(text="Hello, how are you?") as stream:
            async for event in stream:
                if event.get("event") == "text":
                    print(event["text"], end="", flush=True)
                elif event.get("event") == "audio":
                    # Handle audio bytes
                    audio_data = event["audio"]

asyncio.run(main())
```

## Features

### Authentication

```python
# API key authentication
await client.login(api_key="your-api-key")

# API key with team context
await client.login(api_key="your-api-key", team_name="my-team")

# API key for a specific player
await client.login(api_key="your-api-key", federated_id="player-123")

# Google OAuth (opens browser)
await client.login_with_google()
```

### Session Configuration

Configure the AI behavior using prompts, voice profiles, and utilities:

```python
from pug_protocol.messages import VoiceProfile, Reference
from pug_protocol.utilities import Classify, Extract

await session.set_configuration(
    # System prompt (can be a string or Reference)
    prompt="You are a helpful customer service agent for Acme Corp.",

    # LLM temperature
    temperature=0.7,

    # Voice settings
    voice_profile=VoiceProfile(
        provider="elevenlabs",
        voice_id="your-voice-id",
        stability=0.5,
        similarity_boost=0.75,
    ),

    # Safety policy name
    safety_policy="default",

    # Utilities for classification/extraction
    utilities={
        "sentiment": Classify(
            classification_question="What is the user's sentiment?",
            answers=["positive", "neutral", "negative"],
        ),
        "topic": Extract(
            extract_prompt="Extract the main topic of discussion.",
        ),
    },
)
```

### Using References

Store configurations on the server and reference them by name:

```python
from pug_protocol.messages import Reference

# Reference a stored prompt
await session.set_configuration(
    prompt=Reference(reference="my_prompt@v1"),
)

# Load entire configuration from a reference
await session.set_configuration_ref(Reference(reference="production_config"))

# Merge multiple configurations
await session.merge_configuration([
    Reference(reference="base_config"),
    Reference(reference="voice_override"),
])
```

### Real-time Interactions

Stream conversations with audio and text:

```python
# Text interaction with audio output
with session.interact(text="Tell me a joke", audio_output=True) as stream:
    async for event in stream:
        match event.get("event"):
            case "interaction_started":
                print("Starting...")
            case "text":
                print(event["text"], end="")
            case "text_complete":
                print()
            case "audio":
                # Base64-encoded audio chunk
                audio_bytes = event["audio"]
            case "audio_complete":
                print("Audio finished")
            case "data":
                # Utility results
                print(f"Data: {event['data']}")
            case "interaction_complete":
                print("Done!")
```

### Audio Input

Send audio for speech-to-text:

```python
from pug_protocol.configs import AudioConfig

# Add audio data
await session.add_audio(
    audio=audio_bytes,
    config=AudioConfig(mime_type="audio/wav", sampling_rate=16000),
)

# Transcribe the audio
text = await session.transcribe(language_code="en")
print(f"Transcribed: {text}")

# Clear audio buffer
await session.clear_audio()
```

### Player Management

```python
# List players
players = await client.list_players()

# Create a player
player = await client.create_player(external_id="user-123")

# Get player details
player = await client.get_player(player_pk=1)

# Delete a player
await client.delete_player(player_pk=1)
```

## Voice Providers

### ElevenLabs

```python
VoiceProfile(
    provider="elevenlabs",
    voice_id="voice-id",
    speed=1.0,          # 0.7 - 1.2
    stability=0.5,      # 0.0 - 1.0
    similarity_boost=0.75,  # 0.0 - 1.0
)
```

### Deepdub

```python
VoiceProfile(
    provider="deepdub",
    voice_id="voice-prompt-id",
    deepdub_model="dd-etts-2.5",
    deepdub_tempo=1.0,      # 0.0 - 2.0
    deepdub_variance=0.5,   # 0.0 - 1.0
    deepdub_locale="en-US",
    deepdub_clean_audio=True,
    # Accent blending
    deepdub_accent_base_locale="en-US",
    deepdub_accent_locale="en-GB",
    deepdub_accent_ratio=0.5,
)
```

## Utilities

### Classify

Multiple-choice classification during interactions:

```python
Classify(
    classification_question="Is the user asking about billing, technical support, or general inquiry?",
    answers=["billing", "technical_support", "general"],
    additional_context="Consider the conversation history.",
)
```

### Extract

Free-form extraction during interactions:

```python
Extract(
    extract_prompt="Extract the user's order number if mentioned.",
    additional_context="Order numbers are 6 digits.",
)
```

Use utilities in interactions:

```python
with session.interact(
    text=user_input,
    on_input=["sentiment"],      # Run before response (blocking)
    on_output=["topic"],         # Run after response
    on_input_non_blocking=["log"],  # Run in background
) as stream:
    async for event in stream:
        if event.get("event") == "data":
            print(f"Utility results: {event['data']}")
```

## API Reference

### Client

| Method | Description |
|--------|-------------|
| `login(api_key, team_name?, federated_id?)` | Authenticate with API key |
| `login_with_google()` | OAuth authentication |
| `logout()` | Clear authentication |
| `check_health()` | Check server status |
| `session()` | Create interaction session |
| `list_teams()` | List available teams |
| `list_policies()` | List safety policies |
| `get_me()` | Get current user info |
| `list_players()` | List team players |
| `create_player(external_id)` | Create a player |

### Session

| Method | Description |
|--------|-------------|
| `set_configuration(...)` | Configure AI behavior |
| `set_configuration_ref(ref)` | Load config from reference |
| `get_configuration()` | Get current configuration |
| `merge_configuration(refs)` | Merge multiple configs |
| `interact(...)` | Start conversation stream |
| `add_audio(audio, config?)` | Add audio for STT |
| `transcribe(language_code)` | Transcribe audio buffer |
| `clear_audio()` | Clear audio buffer |
| `render_prompt(context)` | Render prompt template |
| `ping()` | Ping server |

## License

Proprietary - UG Labs
