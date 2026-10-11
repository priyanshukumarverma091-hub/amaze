from openai import OpenAI, APIError, APIConnectionError, RateLimitError
from typing import Optional


class OpenRouterProvider:
    """
    OpenRouter LLM provider.

    Compatible with LLMReasoner:
        provider(prompt) -> str
    """

    def __init__(
        self,
        api_key: Optional[str] = "",
        model: str = "openrouter/free",
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.model = model

        if (
            not self.api_key
            or self.api_key == "PASTE_YOUR_API_KEY_HERE"
        ):
            raise ValueError(
                "Please paste your OpenRouter API key in the code."
            )

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

    def __call__(self, prompt: str) -> str:
        """
        Send a prompt to OpenRouter and return the response.
        """

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt.strip(),
                    }
                ],
            )

            if not response.choices:
                raise RuntimeError(
                    "OpenRouter returned no response choices."
                )

            content = response.choices[0].message.content

            if not content or not content.strip():
                raise RuntimeError(
                    "OpenRouter returned an empty response."
                )

            return content.strip()

        except RateLimitError as exc:
            raise RuntimeError(
                "OpenRouter rate limit reached. "
                "Check your quota and model availability."
            ) from exc

        except APIConnectionError as exc:
            raise RuntimeError(
                "Cannot connect to OpenRouter. "
                "Check your internet connection."
            ) from exc

        except APIError as exc:
            raise RuntimeError(
                f"OpenRouter API error: {exc}"
            ) from exc
