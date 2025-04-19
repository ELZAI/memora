from typing import Any, Dict, List, Type, Union

from openai import AsyncOpenAI
from pydantic import BaseModel
from typing_extensions import override

from .base import BaseBackendLLM


class KlusterBackendLLM(BaseBackendLLM):
    """Backend LLM implementation for Kluster.ai API."""

    def __init__(
        self,
        api_key: str,
        model: str = "klusterai/Meta-Llama-3.1-8B-Instruct-Turbo",
        temperature: float = 0.7,
        top_p: float = 1,
        max_tokens: int = 1024,
        max_retries: int = 3,
    ):
        """
        Initialize the KlusterBackendLLM class with specific parameters.

        Args:
            api_key (str): The Kluster.ai API key
            model (str): The name of the Kluster.ai model to use
            temperature (float): The temperature to use for sampling
            top_p (float): The top_p value to use for sampling
            max_tokens (int): The maximum number of tokens to generate
            max_retries (int): The maximum number of retries to make if a request fails
        """
        self.openai_client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.kluster.ai/v1",
            max_retries=max_retries,
        )

        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens

    @override
    async def close(self) -> None:
        """Closes the LLM connection."""
        await self.openai_client.close()
        self.openai_client = None

    @override
    @property
    def get_model_kwargs(self) -> Dict[str, Any]:
        """Returns dictionary of model configuration parameters"""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }

    @override
    async def __call__(
        self,
        messages: List[Dict[str, str]],
        output_schema_model: Type[BaseModel] | None = None,
    ) -> Union[str, BaseModel]:
        """
        Process messages and generate response

        Args:
            messages (List[Dict[str, str]]): List of message dicts with role and content
            output_schema_model (Type[BaseModel] | None): Optional Pydantic base model for structured output

        Returns:
            Union[str, BaseModel]: Generated text response as a string, or an instance of the output schema model if specified
        """
        if output_schema_model:
            response = await self.openai_client.chat.completions.create(
                messages=messages,
                **self.get_model_kwargs,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return output_schema_model.model_validate_json(content)
        else:
            response = await self.openai_client.chat.completions.create(
                messages=messages,
                **self.get_model_kwargs,
            )
            return response.choices[0].message.content 