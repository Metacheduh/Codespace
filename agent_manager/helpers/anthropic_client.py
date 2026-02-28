"""
Anthropic API client for LLM helper features.

Provides a callable interface for memo generation, classification, and parser repair.
Respects the NEVER_MODIFY constraint: LLM outputs go only to advisory columns.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AnthropicClient:
    """Wrapper for Anthropic API with fallback to deterministic mode."""

    def __init__(self, api_key: str | None = None, model: str = "claude-opus-4-6") -> None:
        self.api_key = api_key
        self.model = model
        self.enabled = api_key is not None

        if self.enabled:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                logger.warning("anthropic library not installed, LLM helpers disabled")
                self.enabled = False
            except Exception as e:
                logger.warning("Failed to initialize Anthropic client: %s, LLM helpers disabled", e)
                self.enabled = False

    def __call__(self, prompt: str, max_tokens: int = 1024) -> str:
        """Call the LLM and return response text.

        Args:
            prompt: The prompt to send to the LLM.
            max_tokens: Maximum tokens in the response.

        Returns:
            The LLM response text.
        """
        if not self.enabled:
            return "[LLM disabled - would call Claude with prompt]"

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )
            return message.content[0].text
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            raise


def create_llm_client(config: dict[str, Any]) -> AnthropicClient | None:
    """Create an Anthropic client from config.

    Config expected format:
    ```yaml
    llm_helpers:
      enabled: true
      api_key: "sk-..."  # or set via ANTHROPIC_API_KEY env var
      model: "claude-opus-4-6"
    ```

    Args:
        config: Configuration dict with 'enabled', 'api_key', 'model' keys.

    Returns:
        AnthropicClient if enabled, None otherwise.
    """
    if not config.get("enabled", False):
        return None

    api_key = config.get("api_key") or None
    model = config.get("model", "claude-opus-4-6")

    client = AnthropicClient(api_key=api_key, model=model)
    if client.enabled:
        logger.info("LLM client initialized with model: %s", model)
    return client if client.enabled else None
