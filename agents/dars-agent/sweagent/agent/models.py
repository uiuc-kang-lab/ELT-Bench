from __future__ import annotations
import json
from abc import ABC, abstractmethod
import logging
import os
from dataclasses import dataclass, fields
from pathlib import Path
from litellm import completion
from simple_parsing.helpers.serialization.serializable import FrozenSerializable, Serializable
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)
from typing import Optional, List, Dict, Any, Tuple
from sweagent.agent.commands import Command
from sweagent.utils.config import keys_config
from sweagent.utils.log import get_logger
import litellm
import google.generativeai as genai
from google.generativeai import caching
import datetime


litellm.set_verbose = False

logger = get_logger("api_models")

_MAX_RETRIES = keys_config.get("SWE_AGENT_MODEL_MAX_RETRIES", 10)

@dataclass(frozen=True)
class ModelArguments(FrozenSerializable):
    """Arguments configuring the model and its behavior."""
    model_name: str
    per_instance_cost_limit: float = 0.0
    total_cost_limit: float = 0.0
    temperature: float = 1.0
    top_p: float = 1.0
    replay_path: str | None = None
    host_url: str = "localhost:11434"

@dataclass
class APIStats(Serializable):
    total_cost: float = 0
    instance_cost: float = 0
    tokens_sent: int = 0
    tokens_received: int = 0
    api_calls: int = 0

    def __add__(self, other):
        if not isinstance(other, APIStats):
            msg = "Can only add APIStats with APIStats"
            raise TypeError(msg)

        return APIStats(
            **{field.name: getattr(self, field.name) + getattr(other, field.name) for field in fields(self)},
        )

    def replace(self, other):
        if not isinstance(other, APIStats):
            msg = "Can only replace APIStats with APIStats"
            raise TypeError(msg)

        return APIStats(**{field.name: getattr(other, field.name) for field in fields(self)})

class ContextWindowExceededError(Exception):
    pass

class CostLimitExceededError(Exception):
    pass


class AbstractModelBase(ABC):
    """Abstract base class for LLM implementations"""

    MODELS: Dict[str, Dict[str, Any]] = {}
    SHORTCUTS: Dict[str, str] = {}

    def __init__(self, args: ModelArguments, commands: List[Any]):
        self.args = args
        self.commands = commands
        self.stats = APIStats()

        # Map model_name to API-compatible name
        self.api_model = (
            self.SHORTCUTS[self.args.model_name] 
            if self.args.model_name in self.SHORTCUTS 
            else self.args.model_name
        )

        # Set up model metadata
        MODELS = {
            **{dest: self.MODELS[src] for dest, src in self.SHORTCUTS.items()},
            **self.MODELS,
        }

        if args.model_name in MODELS:
            self.model_metadata = MODELS[args.model_name]
        else:
            msg = f"Unregistered model ({args.model_name}). Add model name to MODELS metadata"
            raise ValueError(msg)

    def reset_stats(self, other: APIStats | None = None) -> None:
        """Reset or update statistics"""
        if other is None:
            self.stats = APIStats(total_cost=self.stats.total_cost)
            logger.info("Resetting model stats")
        else:
            self.stats = other

    def update_stats(self, input_tokens: int, output_tokens: int, external_cost_calc: Optional[float] = None) -> float:
        """Update usage statistics and check limits"""
        if "pricing_tiers" in self.model_metadata:
            tier = ("extended" 
                   if input_tokens > self.model_metadata["pricing_tiers"]["standard"]["max_tokens"] 
                   else "standard")
            cost = (
                self.model_metadata["pricing_tiers"][tier]["cost_per_input_token"] * input_tokens +
                self.model_metadata["pricing_tiers"][tier]["cost_per_output_token"] * output_tokens
            )
        else:
            cost = (
                self.model_metadata["cost_per_input_token"] * input_tokens +
                self.model_metadata["cost_per_output_token"] * output_tokens
            )

        if external_cost_calc is not None:
            cost = external_cost_calc

        self.stats.total_cost += cost
        self.stats.instance_cost += cost
        self.stats.tokens_sent += input_tokens
        self.stats.tokens_received += output_tokens
        self.stats.api_calls += 1

        logger.info(
            f"input_tokens={input_tokens:,}, "
            f"output_tokens={output_tokens:,}, "
            f"instance_cost={self.stats.instance_cost:.4f}, "
            f"cost={cost:.4f}",
        )
        logger.info(
            f"total_tokens_sent={self.stats.tokens_sent:,}, "
            f"total_tokens_received={self.stats.tokens_received:,}, "
            f"total_cost={self.stats.total_cost:.4f}, "
            f"total_api_calls={self.stats.api_calls:,}",
        )

        if 0 < self.args.total_cost_limit <= self.stats.total_cost:
            logger.warning(f"Cost {self.stats.total_cost:.4f} exceeds limit {self.args.total_cost_limit:.4f}")
            raise CostLimitExceededError("Total cost limit exceeded")

        if 0 < self.args.per_instance_cost_limit <= self.stats.instance_cost:
            logger.warning(f"Cost {self.stats.instance_cost:.4f} exceeds limit {self.args.per_instance_cost_limit:.4f}")
            raise CostLimitExceededError("Instance cost limit exceeded")

        return cost

    @abstractmethod
    def history_to_messages(
        self,
        history: List[Dict[str, str]],
        is_demonstration: bool = False,
    ) -> List[Dict[str, str]] | str:
        """Convert chat history to provider-specific message format"""
        pass

    @abstractmethod
    def query(
        self, 
        history: List[Dict[str, str]], 
        temperature: Optional[float] = None
    ) -> str | tuple[list, list]:
        """Query the language model"""
        pass


class LiteLLMModel(AbstractModelBase):
    """LiteLLM implementation for unified LLM interface"""
    
    MODELS = {
        "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0": {
            "max_context": 128_000,
            "cost_per_input_token": 3e-06,
            "cost_per_output_token": 15e-06,
        },
        "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0": {
            "max_context": 128_000,
            "cost_per_input_token": 3e-06,
            "cost_per_output_token": 15e-06,
        },
        "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0": {
            "max_context": 128_000,
            "cost_per_input_token": 8e-07,
            "cost_per_output_token": 4e-06,
        },
        "vertex_ai/gemini-2.0-flash-exp": {
            "max_context": 128_000,
            "cost_per_input_token": 7.5e-08,
            "cost_per_output_token": 3e-07,
        },
        "vertex_ai/gemini-1.5-pro-002": {
            "max_context": 128_000,
            "cost_per_input_token": 7.5e-08,
            "cost_per_output_token": 3e-07,
        },
    }

    SHORTCUTS = {
        "bedrock/claude-3-5-sonnet-20240620": "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
        "bedrock/claude-3-5-haiku-20241022": "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0",
        "bedrock/claude-3-5-sonnet-20241022": "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "vertex_ai/gemini-2.0-flash": "vertex_ai/gemini-2.0-flash-exp",
        "vertex_ai/gemini-1.5-pro": "vertex_ai/gemini-1.5-pro-002",
    }

    def __init__(self, args: ModelArguments, commands: List[Any]):
        super().__init__(args, commands)
        self._setup_api_config()

    def _setup_api_config(self) -> None:
        """Configure API keys and endpoints for different providers"""
        os.environ["OPENAI_API_KEY"] = keys_config.get("OPENAI_API_KEY", "")
        os.environ["ANTHROPIC_API_KEY"] = keys_config.get("ANTHROPIC_API_KEY", "")
        os.environ["GOOGLE_API_KEY"] = keys_config.get("GOOGLE_API_KEY", "")
        os.environ["AWS_ACCESS_KEY_ID"] = keys_config.get("AWS_ACCESS_KEY_ID", "")
        os.environ["AWS_SECRET_ACCESS_KEY"] = keys_config.get("AWS_SECRET_ACCESS", "")
        os.environ["AWS_DEFAULT_REGION"] = keys_config.get("AWS_DEFAULT_REGION", "")
        logging.getLogger("litellm").setLevel(logging.WARNING)

    def history_to_messages(
        self,
        history: list[dict[str, str]],
        is_demonstration: bool = False,
    ) -> str | list[dict[str, str]]:
        """
        Create `messages` by filtering out all keys except for role/content per `history` turn
        """
        if is_demonstration:
            history = [entry for entry in history if entry["role"] != "system"]
            return "\n".join([entry["content"] for entry in history])

        return [{k: v for k, v in entry.items() if k in ["role", "content"]} for entry in history]

    @retry(
        wait=wait_random_exponential(min=1, max=15),
        reraise=True,
        stop=stop_after_attempt(_MAX_RETRIES),
        retry=retry_if_not_exception_type((CostLimitExceededError, RuntimeError)),
    )
    def query(
        self, 
        history: List[Dict[str, str]], 
        temperature: Optional[float] = None
    ) -> Tuple[list, list]:
        """Query LLM using LiteLLM's unified interface"""
        messages = self.history_to_messages(history)
        
        try:
            model_params = {
                "model": self.api_model,
                "messages": messages,
                "temperature": temperature if temperature is not None else self.args.temperature,
                "top_p": self.args.top_p,
            }

            response = completion(**model_params)
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens

            self.update_stats(input_tokens, output_tokens)

            return response.choices[0].message.content

        except Exception as e:
            if any(error in str(e).lower() for error in ["context length", "maximum context", "too long"]):
                raise ContextWindowExceededError(
                    f"Context window ({self.model_metadata['max_context']} tokens) exceeded"
                )
            raise


class LiteLLMCacheModel(AbstractModelBase):
    """LiteLLM implementation for unified LLM interface with caching"""
    
    MODELS = {
        "gpt-4o-2024-05-13": {
            "max_context": 128_000,
            "cost_per_input_token": 2.5e-06,
            "cost_per_output_token": 1e-05,
        },
        "gpt-4o-mini": {
            "max_context": 128_000,
            "cost_per_input_token": 1.5e-07,
            "cost_per_output_token": 6e-07,
        },
        "gpt-4o-mini-2024-07-18": {
            "max_context": 128_000,
            "cost_per_input_token": 1.5e-07,
            "cost_per_output_token": 6e-07,
        },
        "gpt-4o-2024-08-06": {
            "max_context": 128_000,
            "cost_per_input_token": 2.5e-06,
            "cost_per_output_token": 1e-05,
        },
        "gpt-4o-2024-05-13": {
            "max_context": 128_000,
            "cost_per_input_token": 2.5e-06,
            "cost_per_output_token": 1e-05,
        },
        "gpt-4o": {
            "max_context": 128_000,
            "cost_per_input_token": 2.5e-06,
            "cost_per_output_token": 1e-05,
        },
        "claude-3-5-sonnet-20240620": {
            "max_context": 128_000,
            "cost_per_input_token": 3e-06,
            "cost_per_output_token": 15e-06,
        },
        "claude-3-5-sonnet-20241022": {
            "max_context": 128_000,
            "cost_per_input_token": 3e-06,
            "cost_per_output_token": 15e-06,
        },
        "claude-3-5-haiku-20241022": {
            "max_context": 128_000,
            "cost_per_input_token": 8e-7,
            "cost_per_output_token": 4e-6,
        },
        "azure/gpt-4o": {
            "max_context": 128_000,
            "cost_per_input_token": 2.5e-06,
            "cost_per_output_token": 1e-05,
        },
        "hosted_vllm/Qwen/Qwen2.5-Coder-32B-Instruct": {
            "max_context": 32_000,
            "cost_per_input_token": 2.5e-06,
            "cost_per_output_token": 1e-05,
        },
    }

    SHORTCUTS = {
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "claude-3-5-sonnet-20240620": "claude-3-5-sonnet-20240620",
        "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022": "claude-3-5-haiku-20241022",
        "azure/gpt-4o": "azure/gpt-4o",
        "qwen-2.5-coder": "hosted_vllm/Qwen/Qwen2.5-Coder-32B-Instruct"
    }

    def __init__(self, args: ModelArguments, commands: List[Any]):
        super().__init__(args, commands)
        self._setup_api_config()

    def _setup_api_config(self) -> None:
        """Configure API keys and endpoints for different providers"""
        os.environ["OPENAI_API_KEY"] = keys_config.get("OPENAI_API_KEY", "")
        os.environ["ANTHROPIC_API_KEY"] = keys_config.get("ANTHROPIC_API_KEY", "")
        os.environ["GOOGLE_API_KEY"] = keys_config.get("GOOGLE_API_KEY", "")
        os.environ["AWS_ACCESS_KEY_ID"] = keys_config.get("AWS_ACCESS_KEY_ID", "")
        os.environ["AWS_SECRET_ACCESS_KEY"] = keys_config.get("AWS_SECRET_ACCESS", "")
        os.environ["AWS_DEFAULT_REGION"] = keys_config.get("AWS_DEFAULT_REGION", "")
        os.environ["AZURE_API_KEY"] = keys_config.get("AZURE_API_KEY", "")
        os.environ["AZURE_API_BASE"] = keys_config.get("AZURE_API_BASE", "")
        logging.getLogger("litellm").setLevel(logging.WARNING)

    def history_to_messages(
        self,
        history: list[dict[str, str | list | dict]],
        is_demonstration: bool = False,
    ) -> str | list[dict[str, str]]:
        """
        Create `messages` by processing structured content and cache control
        """
        if is_demonstration:
            history = [entry for entry in history if entry["role"] != "system"]
            return "\n".join([entry["content"] for entry in history])

        processed_messages = []
        for entry in history:
            message = {"role": entry["role"]}
            assert "content" in entry, "Content field is required"
            content = entry["content"]
            message["content"] = [{"type": "text", "text": content}]
            processed_messages.append(message)

        processed_messages[-1]["content"][0]['cache_control'] = {"type": "ephemeral"}
        processed_messages[-2]["content"][0]['cache_control'] = {"type": "ephemeral"}

        return processed_messages

    @retry(
        wait=wait_random_exponential(min=1, max=15),
        reraise=True,
        stop=stop_after_attempt(_MAX_RETRIES),
        retry=retry_if_not_exception_type((CostLimitExceededError, RuntimeError)),
    )
    def query(
        self, 
        history: List[Dict[str, str]], 
        temperature: Optional[float] = None
    ) -> Tuple[list, list]:
        """Query LLM using LiteLLM's unified interface"""
        messages = self.history_to_messages(history)
        
        try:
            model_params = {
                "model": self.api_model,
                "messages": messages,
                "temperature": temperature if temperature is not None else self.args.temperature,
                "top_p": self.args.top_p,
                "api_base": keys_config.get("LITELLM_API_BASE", ""),
            }

            response = completion(**model_params)
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            cost = response._hidden_params["response_cost"]
            self.update_stats(input_tokens, output_tokens, cost)

            return response.choices[0].message.content

        except Exception as e:
            if any(error in str(e).lower() for error in ["context length", "maximum context", "too long"]):
                raise ContextWindowExceededError(
                    f"Context window ({self.model_metadata['max_context']} tokens) exceeded"
                )
            raise

class GeminiModel(AbstractModelBase):
    MODELS = {
        "gemini-1.5-pro-002": {
            "max_context": 128_000,
            "cost_per_input_token": 1.25e-06,
            "cost_per_cached_input_token": 3.125e-07,
            "cost_for_caching_input_token_per_min": 7.5e-08,
            "cost_per_output_token": 5e-06,
            "max_tokens": 8192,
        },
        "gemini-1.5-flash-002": {
            "max_context": 128_000,
            "cost_per_input_token": 7.5e-08,
            "cost_per_cached_input_token": 1.875e-08,
            "cost_for_caching_input_token_per_min": 1.67e-08,
            "cost_per_output_token": 3e-07,
            "max_tokens": 8192,

        },
        "gemini-exp-1114": {
            "max_context": 128_000,
            "cost_per_input_token": 1.25e-06,
            "cost_per_cached_input_token": 3.125e-07,
            "cost_for_caching_input_token_per_min": 7.5e-08,
            "cost_per_output_token": 5e-06,
            "max_tokens": 8192,
        }
    }
    
    SHORTCUTS = {
        "gemini-1.5-pro": "gemini-1.5-pro-002",
        "gemini-1.5-flash": "gemini-1.5-flash-002",
        "gemini-exp": "gemini-exp-1114"
    }

    def __init__(self, args: ModelArguments, commands: List[Any]):
        super().__init__(args, commands)
        self._setup_api_config()

    def _setup_api_config(self) -> None:
        """Configure Gemini API keys and endpoints"""
        genai.configure(api_key=keys_config.get("GEMINI_API_KEY", ""))
        logging.getLogger("litellm").setLevel(logging.WARNING)

    def history_to_messages(
        self,
        history: List[Dict[str, str]],
        is_demonstration: bool = False,
    ) -> List[Dict[str, str]]:
        if is_demonstration:
            return [{"parts": [{"text": entry["content"]}]} for entry in history if entry["role"] != "system"]
        
        messages = []
        for entry in history:
            role = entry["role"] if entry["role"] != "assistant" else "model"
            content = entry["content"]
            messages.append({"role": role, "parts": [{"text": content}]})
        return messages

    @retry(
        wait=wait_random_exponential(min=1, max=15),
        reraise=True,
        stop=stop_after_attempt(_MAX_RETRIES),
        retry=retry_if_not_exception_type((CostLimitExceededError, RuntimeError)),
    )
    def query(self, history: List[Dict[str, str]], temperature: Optional[float] = None) -> str:
        messages = self.history_to_messages(history)
        try:
            temperature_current = temperature if temperature is not None else self.args.temperature
            
            cache = caching.CachedContent.create(
                model=self.api_model,
                display_name="test",
                system_instruction=history[0]["content"],
                contents=messages[1:-1],
                ttl=datetime.timedelta(minutes=2),
            )
            
            self.model = genai.GenerativeModel.from_cached_content(cached_content=cache)
            
            response = self.model.generate_content(
                history[-1]["content"],
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature_current,
                    top_p=self.args.top_p,
                    max_output_tokens=self.model_metadata["max_tokens"],
                )
            )
            
            usage_metadata = response.usage_metadata
            self.update_stats(
                input_tokens=usage_metadata.prompt_token_count,
                output_tokens=usage_metadata.candidates_token_count,
                cached_tokens=usage_metadata.cached_content_token_count
            )
            
            return response.text
        except Exception as e:
            if "exceeded maximum context length" in str(e):
                raise CostLimitExceededError(f"Context window ({self.model_metadata['max_context']} tokens) exceeded")
            raise

    def update_stats(self, input_tokens: int, output_tokens: int, cached_tokens: int) -> float:
        cache_minutes = 2
        cost = (
            self.model_metadata["cost_per_input_token"] * (input_tokens - cached_tokens) +
            self.model_metadata["cost_per_cached_input_token"] * cached_tokens +
            self.model_metadata["cost_for_caching_input_token_per_min"] * cached_tokens * cache_minutes +
            self.model_metadata["cost_per_output_token"] * output_tokens
        )

        self.stats.total_cost += cost
        self.stats.instance_cost += cost
        self.stats.tokens_sent += input_tokens
        self.stats.tokens_received += output_tokens
        self.stats.api_calls += 1

        logger.info(
            f"input_tokens={input_tokens:,}, "
            f"cached_tokens={cached_tokens:,}, "
            f"output_tokens={output_tokens:,}, "
            f"cache_minutes={cache_minutes}, "
            f"instance_cost={self.stats.instance_cost:.4f}, "
            f"cost={cost:.4f}"
        )
        logger.info(
            f"total_tokens_sent={self.stats.tokens_sent:,}, "
            f"total_tokens_received={self.stats.tokens_received:,}, "
            f"total_cost={self.stats.total_cost:.4f}, "
            f"total_api_calls={self.stats.api_calls:,}"
        )

        if 0 < self.args.total_cost_limit <= self.stats.total_cost:
            logger.warning(f"Cost {self.stats.total_cost:.4f} exceeds limit {self.args.total_cost_limit:.4f}")
            raise CostLimitExceededError("Total cost limit exceeded")

        if 0 < self.args.per_instance_cost_limit <= self.stats.instance_cost:
            logger.warning(f"Cost {self.stats.instance_cost:.4f} exceeds limit {self.args.per_instance_cost_limit:.4f}")
            raise CostLimitExceededError("Instance cost limit exceeded")

        return cost

class GeminiExperimentalModel(AbstractModelBase):
    MODELS = {
        "gemini-1.5-pro-002": {
            "max_context": 128_000,
            "cost_per_input_token": 1.25e-06,
            "cost_per_output_token": 5e-06,
            "max_tokens": 8192,
        },
        "gemini-1.5-flash-002": {
            "max_context": 128_000,
            "cost_per_input_token": 7.5e-08,
            "cost_per_output_token": 3e-07,
            "max_tokens": 8192,
        },
        "gemini-exp-1114": {
            "max_context": 128_000,
            "cost_per_input_token": 1.25e-06,
            "cost_per_output_token": 5e-06,
            "max_tokens": 8192,
        },
        "gemini-2.0-flash-exp": {
            "max_context": 128_000,
            "cost_per_input_token": 7.5e-08,
            "cost_per_output_token": 3e-07,
            "max_tokens": 8192,
        }
    }
    
    SHORTCUTS = {
        "gemini-2.0-flash": "gemini-2.0-flash-exp"
    }

    def __init__(self, args: ModelArguments, commands: List[Any]):
        super().__init__(args, commands)
        self._setup_api_config()
        
    def _setup_api_config(self) -> None:
        """Configure Gemini API keys and endpoints"""
        genai.configure(api_key=keys_config.get("GEMINI_API_KEY", ""))
        logging.getLogger("litellm").setLevel(logging.WARNING)

    def history_to_messages(
        self,
        history: List[Dict[str, str]],
        is_demonstration: bool = False,
    ) -> tuple[List[Dict[str, str]], Optional[str]]:
        """
        Convert history to messages and extract system prompt if present.
        Returns a tuple of (messages, system_prompt).
        """
        messages = []
        system_prompt = None
        
        if history and history[0]["role"] == "system":
            system_prompt = history[0]["content"]
            history = history[1:]
        
        for entry in history:
            role = "model" if entry["role"] == "assistant" else entry["role"]
            messages.append({"role": role, "parts": entry["content"]})
            
        return messages, system_prompt

    @retry(
        wait=wait_random_exponential(min=1, max=15),
        reraise=True,
        stop=stop_after_attempt(_MAX_RETRIES),
        retry=retry_if_not_exception_type((CostLimitExceededError, RuntimeError)),
    )
    def query(self, history: List[Dict[str, str]], temperature: Optional[float] = None) -> str:
        try:
            temperature_current = temperature if temperature is not None else self.args.temperature

            chat_history, system_prompt = self.history_to_messages(history[:-1])  # Exclude last message

            generation_config = genai.types.GenerationConfig(
                temperature=temperature_current,
                top_p=self.args.top_p,
                max_output_tokens=self.model_metadata["max_tokens"],
            )

            model_kwargs = {
                "model_name": self.api_model,
                "generation_config": generation_config,
            }
            if system_prompt:
                model_kwargs["system_instruction"] = system_prompt

            model = genai.GenerativeModel(**model_kwargs)
            chat = model.start_chat(history=chat_history)

            response = chat.send_message(
                {
                    "role": "model" if history[-1]["role"] == "assistant" else history[-1]["role"],
                    "parts": history[-1]["content"]
                }
            )

            usage_metadata = response.usage_metadata
            self.update_stats(
                input_tokens=usage_metadata.prompt_token_count,
                output_tokens=usage_metadata.candidates_token_count
            )

            return response.text
            
        except Exception as e:
            if "exceeded maximum context length" in str(e):
                raise CostLimitExceededError(f"Context window ({self.model_metadata['max_context']} tokens) exceeded")
            raise

    def update_stats(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on input and output tokens only, no caching costs"""
        cost = (
            self.model_metadata["cost_per_input_token"] * input_tokens +
            self.model_metadata["cost_per_output_token"] * output_tokens
        )

        self.stats.total_cost += cost
        self.stats.instance_cost += cost
        self.stats.tokens_sent += input_tokens
        self.stats.tokens_received += output_tokens
        self.stats.api_calls += 1

        logger.info(
            f"input_tokens={input_tokens:,}, "
            f"output_tokens={output_tokens:,}, "
            f"instance_cost={self.stats.instance_cost:.4f}, "
            f"cost={cost:.4f}"
        )
        logger.info(
            f"total_tokens_sent={self.stats.tokens_sent:,}, "
            f"total_tokens_received={self.stats.tokens_received:,}, "
            f"total_cost={self.stats.total_cost:.4f}, "
            f"total_api_calls={self.stats.api_calls:,}"
        )

        if 0 < self.args.total_cost_limit <= self.stats.total_cost:
            logger.warning(f"Cost {self.stats.total_cost:.4f} exceeds limit {self.args.total_cost_limit:.4f}")
            raise CostLimitExceededError("Total cost limit exceeded")

        if 0 < self.args.per_instance_cost_limit <= self.stats.instance_cost:
            logger.warning(f"Cost {self.stats.instance_cost:.4f} exceeds limit {self.args.per_instance_cost_limit:.4f}")
            raise CostLimitExceededError("Instance cost limit exceeded")

        return cost


class HumanModel(AbstractModelBase):
    MODELS = {"human": {}}

    def __init__(self, args: ModelArguments, commands: list[Command]):
        super().__init__(args, commands)

        # Determine which commands require multi-line input
        self.multi_line_command_endings = {
            command.name: command.end_name for command in commands if command.end_name is not None
        }

    def history_to_messages(
        self,
        history: list[dict[str, str]],
        is_demonstration: bool = False,
    ) -> str | list[dict[str, str]]:
        """
        Create `messages` by filtering out all keys except for role/content per `history` turn
        """
        # Remove system messages if it is a demonstration
        if is_demonstration:
            history = [entry for entry in history if entry["role"] != "system"]
            return "\n".join([entry["content"] for entry in history])
        # Return history components with just role, content fields
        return [{k: v for k, v in entry.items() if k in ["role", "content"]} for entry in history]

    def query(self, history: list[dict[str, str]], action_prompt: str = "> ", temperature: Optional[float] = None) -> str:
        """
        Logic for handling user input to pass to SWEEnv
        """
        action = input(action_prompt)
        command_name = action.split()[0] if action else ""

        # Special handling for multi-line input actions (i.e. edit)
        if command_name in self.multi_line_command_endings:
            buffer = [action]
            end_keyword = self.multi_line_command_endings[command_name]
            while True:
                action = input("... ")
                buffer.append(action)
                if action.rstrip() == end_keyword:
                    # Continue reading input until terminating keyword inputted
                    break
            action = "\n".join(buffer)
        elif action.strip() == "start_multiline_command":  # do arbitrary multi-line input
            buffer = []
            while True:
                action = input("... ")
                if action.rstrip() == "end_multiline_command":
                    break
                buffer.append(action)
            action = "\n".join(buffer)
        return action


class HumanThoughtModel(HumanModel):
    MODELS = {"human_thought": {}}

    def query(self, history: list[dict[str, str]], temperature: Optional[float] = None) -> str:
        """
        Logic for handling user input (both thought + action) to pass to SWEEnv
        """
        thought_all = ""
        thought = input("Thought (end w/ END_THOUGHT): ")
        while True:
            if "END_THOUGHT" in thought:
                thought = thought.split("END_THOUGHT")[0]
                thought_all += thought
                break
            thought_all += thought
            thought = input("... ")

        action = super().query(history, action_prompt="Action: ")

        return f"{thought_all}\n```\n{action}\n```"


class ReplayModel(AbstractModelBase):
    MODELS = {"replay": {}}

    def __init__(self, args: ModelArguments, commands: list[Command]):
        super().__init__(args, commands)

        if self.args.replay_path is None or not os.path.exists(self.args.replay_path):
            msg = "--replay_path must point to a file that exists to run a replay policy"
            raise ValueError(msg)

        self.replays = [
            list(json.loads(x).values())[0] for x in Path(self.args.replay_path).read_text().splitlines(keepends=True)
        ]
        self.replay_idx = 0
        self.action_idx = 0

    def _next_replay(self) -> None:
        """Called after last action"""
        self.replay_idx += 1
        self.action_idx = 0

    def query(self, history: list[dict[str, str]]) -> str:
        """
        Logic for tracking which replay action to pass to SWEEnv
        """
        actions = self.replays[self.replay_idx]
        try:
            action = actions[self.action_idx]
        except IndexError:
            msg = (
                "This seems to be an incomplete trajectory. "
                "We reached the end of it, but `submit` was not called. "
                "Calling it now."
            )
            logger.warning(msg)
            action = "```\nsubmit\n```"

        self.action_idx += 1

        # Assuming `submit` is always last action of replay trajectory
        if action == "submit":
            self._next_replay()

        return action
    
    def history_to_messages(
        self,
        history: list[dict[str, str]],
        is_demonstration: bool = False,
    ) -> str | list[dict[str, str]]:
        """
        Create `messages` by filtering out all keys except for role/content per `history` turn
        """
        pass


class InstantEmptySubmitTestModel(AbstractModelBase):
    MODELS = {"instant_empty_submit": {}}

    def __init__(self, args: ModelArguments, commands: list[Command]):
        """This model immediately submits. Useful for testing purposes"""
        super().__init__(args, commands)
        self._action_idx = 0

    def query(self, history: list[dict[str, str]]) -> str:
        # Need to at least do _something_ to submit
        if self._action_idx == 0:
            self._action_idx = 1
            action = "DISCUSSION\nLet's reproduce the bug by creating a `reproduce.py` file.\n\n```\ncreate reproduce.py\n```\n"
        elif self._action_idx == 1:
            self._action_idx = 0
            action = "DISCUSSION\nThe task should be resolved, so let's submit the patch.\n\n```\nsubmit\n```\n"
        return action
    
    def history_to_messages(
        self,
        history: list[dict[str, str]],
        is_demonstration: bool = False,
    ) -> str | list[dict[str, str]]:
        """
        Create `messages` by filtering out all keys except for role/content per `history` turn
        """
        pass


def get_model(args: ModelArguments, commands: list[Command] | None = None) -> AbstractModelBase:
    """
    Returns correct model object given arguments and commands
    """
    if commands is None:
        commands = []
    if args.model_name == "instant_empty_submit":
        return InstantEmptySubmitTestModel(args, commands)
    if args.model_name == "human":
        return HumanModel(args, commands)
    if args.model_name == "human_thought":
        return HumanThoughtModel(args, commands)
    if args.model_name == "replay":
        return ReplayModel(args, commands)
    if args.model_name == "gemini-2.0-flash":
        return GeminiExperimentalModel(args, commands)
    if args.model_name.startswith("gemini"):
        return GeminiModel(args, commands)
    elif args.model_name.startswith("bedrock") or args.model_name.startswith("vertex"):
        return LiteLLMModel(args, commands)
    else:
        return LiteLLMCacheModel(args, commands)