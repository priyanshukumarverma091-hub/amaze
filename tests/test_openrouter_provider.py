from unittest.mock import MagicMock, patch

import pytest

from backend.reasoning.openrouter_provider import (
    OpenRouterProvider,
)


def test_provider_requires_api_key():

    with patch.dict(
        "os.environ",
        {},
        clear=True,
    ):
        with pytest.raises(ValueError):
            OpenRouterProvider()


def test_provider_uses_environment_variables():

    with patch.dict(
        "os.environ",
        {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_MODEL": "test/model",
        },
        clear=True,
    ):
        provider = OpenRouterProvider()

        assert provider.api_key == "test-key"
        assert provider.model == "test/model"


def test_provider_calls_openrouter():

    with patch.dict(
        "os.environ",
        {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_MODEL": "test/model",
        },
        clear=True,
    ):

        provider = OpenRouterProvider()

        fake_response = MagicMock()

        fake_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="Hello from OpenRouter"
                )
            )
        ]

        provider.client.chat.completions.create = MagicMock(
            return_value=fake_response
        )

        result = provider("Say hello")

        assert result == "Hello from OpenRouter"

        provider.client.chat.completions.create.assert_called_once()

        call_kwargs = (
            provider
            .client
            .chat
            .completions
            .create
            .call_args.kwargs
        )

        assert call_kwargs["model"] == "test/model"

        assert call_kwargs["messages"] == [
            {
                "role": "user",
                "content": "Say hello",
            }
        ]


def test_provider_rejects_empty_prompt():

    with patch.dict(
        "os.environ",
        {
            "OPENROUTER_API_KEY": "test-key",
        },
        clear=True,
    ):

        provider = OpenRouterProvider()

        with pytest.raises(ValueError):
            provider("")


def test_provider_handles_empty_response():

    with patch.dict(
        "os.environ",
        {
            "OPENROUTER_API_KEY": "test-key",
        },
        clear=True,
    ):

        provider = OpenRouterProvider()

        fake_response = MagicMock()
        fake_response.choices = []

        provider.client.chat.completions.create = MagicMock(
            return_value=fake_response
        )

        with pytest.raises(RuntimeError):
            provider("Hello")