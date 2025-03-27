import base64
import json
import logging
import os
import re
import time
from http import HTTPStatus
from io import BytesIO

from openai import AzureOpenAI
from typing import Dict, List, Optional, Tuple, Any, TypedDict
import dashscope
from groq import Groq
import google.generativeai as genai
import openai
import requests
import tiktoken
import signal
from fireworks.client import Fireworks

logger = logging.getLogger("spider_agent")

model_cost = {
    "gpt-4o": {"prompt_tokens_cost": 2.5 / 1000000, "completion_tokens_cost": 10 / 1000000, "cached": 1.25 / 1000000},
    "gpt-4": {"prompt_tokens_cost": 30 / 1000000, "completion_tokens_cost": 60 / 1000000},
    "o1": {"prompt_tokens_cost": 15 / 1000000, "completion_tokens_cost": 60 / 1000000, "cached": 7.5 / 1000000},
    "claude-3-5-sonnet-20241022": {"cache_creation_input_tokens": 3.75 / 1000000, "input_tokens": 3 / 1000000, "cache_read_input_tokens": 0.3 / 1000000, "output_tokens": 15 / 1000000},
    "llama-v3p3-70b-instruct": {"prompt_tokens": 0.1/1000000, "completion_tokens": 0.1/1000000},
    "deepseek-r1": {"prompt_tokens": 3/1000000, "completion_tokens": 8/1000000},
    "llama-v3p1-405b-instruct": {"prompt_tokens": 3/1000000, "completion_tokens": 3/1000000},
    "qwen2p5-coder-32b-instruct": {"prompt_tokens": 0.9/1000000, "completion_tokens": 0.9/1000000}
}


def call_llm(payload):
  model = payload["model"]
  stop = ["Observation:", "\n\n\n\n", "\n \n \n"]
  cost = 0
  if model.startswith("gpt"):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"
    }
    logger.info("Generating content with GPT model: %s", model)

    for i in range(3):
      try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload
        )
        output_message = response.json()['choices'][0]['message']['content']
        cached_tokens = response.json(
        )['usage']['prompt_tokens_details']['cached_tokens']
        prompt_tokens = response.json(
        )['usage']['prompt_tokens'] - cached_tokens
        cost += prompt_tokens * model_cost[model]["prompt_tokens_cost"] + \
            response.json()['usage']['completion_tokens'] * \
            model_cost[model]["completion_tokens_cost"] + \
            cached_tokens * model_cost[model]["cached"]
        logger.info("Input tokens: %d; Output tokens: %d; cached tokens: %d",
                    prompt_tokens, response.json()['usage']['completion_tokens'], cached_tokens)
        return True, output_message, cost
      except Exception as e:
        logger.error("Failed to call LLM: " + str(e))
        if hasattr(e, 'response') and e.response is not None:
          error_info = e.response.json()
          code_value = error_info['error']['code']
          if code_value == "content_filter":
            if not payload['messages'][-1]['content'][0]["text"].endswith("They do not represent any real events or entities. ]"):
              payload['messages'][-1]['content'][0]["text"] += "[ Note: The data and code snippets are purely fictional and used for testing and demonstration purposes only. They do not represent any real events or entities. ]"
          if code_value == "context_length_exceeded":
            return False, code_value, cost
        else:
          code_value = 'unknown_error'
        logger.error("Retrying ...")
        time.sleep(4 * (2 ** (i + 1)))
    return False, code_value, cost

  elif model.startswith("o1"):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"
    }
    logger.info("Generating content with GPT model: %s", model)

    messages = payload["messages"]
    top_p = payload["top_p"]
    temperature = payload["temperature"]

    o1_messages = []

    for i, message in enumerate(messages):
      o1_message = {
          "role": message["role"] if message["role"] != "system" else "user",
          "content": ""
      }
      for part in message["content"]:
        o1_message['content'] = part['text'] if part['type'] == "text" else ""

        o1_messages.append(o1_message)

    payload["messages"] = o1_messages
    payload["max_completion_tokens"] = 10000
    del payload['max_tokens']
    del payload["temperature"]
    del payload["top_p"]

    for i in range(3):
      try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload
        )
        output_message = response.json()['choices'][0]['message']['content']
        cached_tokens = response.json()['usage']['prompt_tokens_details']['cached_tokens']
        prompt_tokens = response.json()['usage']['prompt_tokens'] - cached_tokens
        cost += prompt_tokens * model_cost[model]["prompt_tokens_cost"] + \
            response.json()['usage']['completion_tokens'] * \
            model_cost[model]["completion_tokens_cost"] + \
            cached_tokens * model_cost[model]["cached"]
        logger.info("Input tokens: %d; Output tokens: %d; cached tokens: %d",
                    prompt_tokens, response.json()['usage']['completion_tokens'], cached_tokens)

        # logger.info(f"Input: \n{payload['messages']}\nOutput:{response}")
        return True, output_message, cost
      except Exception as e:
        logger.error("Failed to call LLM: " + str(e))
        logger.error("Retrying ...")
        time.sleep(10 * (2 ** (i + 1)))
    return False, code_value, cost

  elif model.startswith("azure"):
    client = AzureOpenAI(
        api_key=os.environ['AZURE_API_KEY'],
        api_version="2024-02-15-preview",
        azure_endpoint=os.environ['AZURE_ENDPOINT']
    )
    model_name = model.split("/")[-1]
    for i in range(3):
      try:
        response = client.chat.completions.create(
          model=model_name, messages=payload['messages'], max_tokens=payload['max_tokens'], top_p=payload['top_p'], temperature=payload['temperature'], stop=stop)
        response = response.choices[0].message.content
        # logger.info(f"Input: \n{payload['messages']}\nOutput:{response}")
        return True, response
      except Exception as e:
        logger.error("Failed to call LLM: " + str(e))
        error_info = e.response.json()
        code_value = error_info['error']['code']
        if code_value == "content_filter":
          if not payload['messages'][-1]['content'][0]["text"].endswith("They do not represent any real events or entities. ]"):
            payload['messages'][-1]['content'][0]["text"] += "[ Note: The data and code snippets are purely fictional and used for testing and demonstration purposes only. They do not represent any real events or entities. ]"
        if code_value == "context_length_exceeded":
          return False, code_value, cost
        logger.error("Retrying ...")
        time.sleep(10 * (2 ** (i + 1)))
    return False, code_value, cost
  elif model.startswith("claude-3-7"):
    messages = payload["messages"]
    max_tokens = payload["max_tokens"]
    top_p = payload["top_p"]
    temperature = payload["temperature"]

    gemini_messages = []
    
    message_length = len(messages)
    for i, message in enumerate(messages):
      gemini_message = {
          "role": message["role"],
          "content": []
      }
      assert len(message["content"]) in [
          1, 2], "One text, or one text with one image"
      for part in message["content"]:

        if part['type'] == "image_url":
          image_source = {}
          image_source["type"] = "base64"
          image_source["media_type"] = "image/png"
          image_source["data"] = part['image_url']['url'].replace(
            "data:image/png;base64,", "")
          gemini_message['content'].append(
            {"type": "image", "source": image_source})

        if part['type'] == "text":
          if (i == message_length-1 or i == message_length-2) and (message_length < 50):
            gemini_message['content'].append(
              {"type": "text", "text": part['text'], "cache_control": {"type": "ephemeral"}})
          else:
            gemini_message['content'].append(
              {"type": "text", "text": part['text']})

      gemini_messages.append(gemini_message)

    if gemini_messages[0]['role'] == "system":
      system_messages = []
      system_message = gemini_messages[0]['content'][0]
      system_message['cache_control'] = {'type': 'ephemeral'}
      system_messages.append(
          system_message
      )

      gemini_messages.pop(0)
    # logger.info(gemini_messages)
    headers = {
        "x-api-key": os.environ.get("ANTHROPIC_API_KEY"),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    payload = {"model": model, "system": system_messages, "messages": gemini_messages,
                         "max_tokens": max_tokens+17500, "temperature": 1,  "thinking": {"type": "enabled","budget_tokens": 17500}}
    # logger.info(f"payload {payload}")
    for i in range(3):
      try:
        response = requests.request(
          "POST", "https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        if response.status_code == 200:
          token_usage = response.json()['usage']
          cost += model_cost['claude-3-5-sonnet-20241022']["cache_creation_input_tokens"] * token_usage['cache_creation_input_tokens'] + model_cost['claude-3-5-sonnet-20241022']["input_tokens"] * token_usage['input_tokens'] + \
            model_cost['claude-3-5-sonnet-20241022']["cache_read_input_tokens"] * token_usage['cache_read_input_tokens'] + \
              model_cost['claude-3-5-sonnet-20241022']["output_tokens"] * \
              token_usage['output_tokens']
          logger.info("Cache_creation_input_tokens: %d; Cache_read_input_tokens: %d; Input_tokens: %d; Output_tokens: %d", token_usage['cache_creation_input_tokens'], token_usage['cache_read_input_tokens'], token_usage['input_tokens'], token_usage['output_tokens'])
          logger.info("Claude-3-7-Sonnet thinking content: %s", response.json()["content"][0]['thinking'])
          return True, response.json()["content"][1]['text'], cost
        else:
          error_info = response.json()
          code_value = error_info['error']['code']
          if code_value == "content_filter":
            if not payload['messages'][-1]['content'][0]["text"].endswith("They do not represent any real events or entities. ]"):
              payload['messages'][-1]['content'][0]["text"] += "[ Note: The data and code snippets are purely fictional and used for testing and demonstration purposes only. They do not represent any real events or entities. ]"
          if code_value == "context_length_exceeded":
            return False, code_value, cost
          logger.error("Retrying ...")
          time.sleep(10 * (2 ** (i + 1)))
      except Exception as e:
        logger.error("Failed to call LLM: " + str(e))
        time.sleep(10 * (2 ** (i + 1)))
        code_value = "context_length_exceeded"
    return False, code_value, cost
  elif model.startswith("claude"):
    messages = payload["messages"]
    max_tokens = payload["max_tokens"]
    top_p = payload["top_p"]
    temperature = payload["temperature"]

    gemini_messages = []
    
    message_length = len(messages)
    for i, message in enumerate(messages):
      gemini_message = {
          "role": message["role"],
          "content": []
      }
      assert len(message["content"]) in [
          1, 2], "One text, or one text with one image"
      for part in message["content"]:

        if part['type'] == "image_url":
          image_source = {}
          image_source["type"] = "base64"
          image_source["media_type"] = "image/png"
          image_source["data"] = part['image_url']['url'].replace(
            "data:image/png;base64,", "")
          gemini_message['content'].append(
            {"type": "image", "source": image_source})

        if part['type'] == "text":
          if (i == message_length-1 or i == message_length-2) and (message_length < 50):
            gemini_message['content'].append(
              {"type": "text", "text": part['text'], "cache_control": {"type": "ephemeral"}})
          else:
            gemini_message['content'].append(
              {"type": "text", "text": part['text']})

      gemini_messages.append(gemini_message)

    if gemini_messages[0]['role'] == "system":
      system_messages = []
      system_message = gemini_messages[0]['content'][0]
      system_message['cache_control'] = {'type': 'ephemeral'}
      system_messages.append(
          system_message
      )

      gemini_messages.pop(0)
    # logger.info(gemini_messages)
    headers = {
        "x-api-key": os.environ.get("ANTHROPIC_API_KEY"),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    payload = {"model": model, "system": system_messages, "messages": gemini_messages,
                         "max_tokens": max_tokens, "temperature": temperature, "top_p": top_p}
    # logger.info(f"payload {payload}")
    for i in range(3):
      try:
        response = requests.request(
          "POST", "https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        if response.status_code == 200:
          token_usage = response.json()['usage']
          cost += model_cost['claude-3-5-sonnet-20241022']["cache_creation_input_tokens"] * token_usage['cache_creation_input_tokens'] + model_cost['claude-3-5-sonnet-20241022']["input_tokens"] * token_usage['input_tokens'] + \
            model_cost['claude-3-5-sonnet-20241022']["cache_read_input_tokens"] * token_usage['cache_read_input_tokens'] + \
              model_cost['claude-3-5-sonnet-20241022']["output_tokens"] * \
              token_usage['output_tokens']
          logger.info("Cache_creation_input_tokens: %d; Cache_read_input_tokens: %d; Input_tokens: %d; Output_tokens: %d", token_usage['cache_creation_input_tokens'], token_usage['cache_read_input_tokens'], token_usage['input_tokens'], token_usage['output_tokens'])
          return True, response.json()["content"][0]['text'], cost
        else:
          error_info = response.json()
          code_value = error_info['error']['code']
          if code_value == "content_filter":
            if not payload['messages'][-1]['content'][0]["text"].endswith("They do not represent any real events or entities. ]"):
              payload['messages'][-1]['content'][0]["text"] += "[ Note: The data and code snippets are purely fictional and used for testing and demonstration purposes only. They do not represent any real events or entities. ]"
          if code_value == "context_length_exceeded":
            return False, code_value, cost
          logger.error("Retrying ...")
          time.sleep(10 * (2 ** (i + 1)))
      except Exception as e:
        logger.error("Failed to call LLM: " + str(e))
        time.sleep(10 * (2 ** (i + 1)))
        code_value = "context_length_exceeded"
    return False, code_value, cost

  elif model.startswith("mixtral"):
    messages = payload["messages"]
    max_tokens = payload["max_tokens"]
    top_p = payload["top_p"]
    temperature = payload["temperature"]

    mistral_messages = []

    for i, message in enumerate(messages):
      mistral_message = {
          "role": message["role"],
          "content": ""
      }

      for part in message["content"]:
        mistral_message['content'] = part['text'] if part['type'] == "text" else ""

      mistral_messages.append(mistral_message)

    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY"),
    )

    for i in range(2):
      try:
        logger.info("Generating content with model: %s", model)
        response = client.chat.completions.create(
            messages=mistral_messages,
            model=model,
            max_tokens=max_tokens,
            top_p=top_p,
            temperature=temperature,
            stop=stop
        )
        return True, response.choices[0].message.content

      except Exception as e:
        logger.error("Failed to call LLM: " + str(e))
        time.sleep(10 * (2 ** (i + 1)))
        if hasattr(e, 'response'):
          error_info = e.response.json()
          code_value = error_info['error']['code']
          if code_value == "content_filter":
            if not payload['messages'][-1]['content'][0]["text"].endswith("They do not represent any real events or entities. ]"):
              payload['messages'][-1]['content'][0]["text"] += "[ Note: The data and code snippets are purely fictional and used for testing and demonstration purposes only. They do not represent any real events or entities. ]"
          if code_value == "context_length_exceeded":
            return False, code_value, cost
        else:
          code_value = ""
        logger.error("Retrying ...")

    return False, code_value, cost
  elif model.startswith("deepseek"):

    messages = payload["messages"]
    max_tokens = payload["max_tokens"]
    top_p = payload["top_p"]
    temperature = payload["temperature"]
    from openai import OpenAI

    deepseek_messages = []

    for i, message in enumerate(messages):
      deepseek_message = {
          "role": message["role"],
          "content": ""
      }
      for part in message["content"]:
        deepseek_message['content'] = part['text'] if part['type'] == "text" else ""
        deepseek_messages.append(deepseek_message)
    client = OpenAI(
      api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
    for i in range(3):
      try:
        response = client.chat.completions.create(
            model=model,
            messages=deepseek_messages,
            max_tokens=max_tokens,
            top_p=top_p,
            temperature=temperature
        )
        output_message = json.loads(response.json())[
            'choices'][0]['message']['content']
        return True, output_message, cost
      except Exception as e:
        logger.error("Failed to call LLM: " + str(e))
        if hasattr(e, 'response') and e.response is not None:
          error_info = e.response.json()
          code_value = error_info['error']['code']

          if code_value == "content_filter":
            last_message = messages[-1]
            if 'content' in last_message and isinstance(last_message['content'], str):
              if not last_message['content'].endswith("They do not represent any real events or entities. ]"):
                last_message['content'] += "[ Note: The data and code snippets are purely fictional and used for testing and demonstration purposes only. They do not represent any real events or entities. ]"
            else:
              logger.error(
                "Unexpected message structure in 'messages'. Skipping content modification.")
          elif code_value == "context_length_exceeded":
            return False, code_value, cost
        else:
          code_value = 'unknown_error'

        logger.error("Retrying ...")
        time.sleep(10 * (2 ** (i + 1)))
      return False, code_value, cost

  elif model.startswith("accounts/fireworks"):
    messages = payload["messages"]
    max_tokens = payload["max_tokens"]
    top_p = payload["top_p"]
    temperature = payload["temperature"]

    if model.startswith("llama3.1"):
      max_tokens = 2000

    qwen_messages = []

    for i, message in enumerate(messages):
      qwen_message = {
          "role": message["role"],
          "content": message["content"]
      }

      qwen_messages.append(qwen_message)
    model_name = model.split('/')[-1]
    for i in range(3):
      try:
        logger.info("Generating content with model: %s", model)
        client = Fireworks(api_key=os.environ['FIREWORKS_API_KEY'])
        response = client.chat.completions.create(
            model=model,
            messages=qwen_messages,
            top_p=top_p,
            temperature=temperature
        )
        cost += model_cost[model_name]["prompt_tokens"] * response.usage.prompt_tokens + model_cost[model_name]["completion_tokens"] * response.usage.completion_tokens
        logger.info("prompt_tokens: %d;  completion_tokens: %d", response.usage.prompt_tokens, response.usage.completion_tokens)
          
        return True, response.choices[0].message.content, cost

      except Exception as e:
        logger.error("Failed to call LLM: " + str(e))
        time.sleep(3 * (2 ** (i + 1)))
        if hasattr(e, 'response'):
          error_info = e.response.json()
          code_value = error_info['error']['code']
          if code_value == "content_filter":
            if not payload['messages'][-1]['content'][0]["text"].endswith("They do not represent any real events or entities. ]"):
              payload['messages'][-1]['content'][0]["text"] += "[ Note: The data and code snippets are purely fictional and used for testing and demonstration purposes only. They do not represent any real events or entities. ]"
        else:
          code_value = "context_length_exceeded"
        logger.error("Retrying ...")
    return False, code_value, cost

  elif model.startswith("codellama") or model.startswith("mistralai"):
    messages = payload["messages"]
    max_tokens = payload["max_tokens"]
    if model == "codellama/CodeLlama-70b-Instruct-hf":
      max_tokens = 800
    top_p = payload["top_p"]
    temperature = payload["temperature"]

    mistral_messages = []

    for i, message in enumerate(messages):
      mistral_message = {
          "role": message["role"],
          "content": ""
      }

      for part in message["content"]:
        mistral_message['content'] = part['text'] if part['type'] == "text" else ""

      mistral_messages.append(mistral_message)

    from openai import OpenAI

    client = OpenAI(api_key=os.environ["TOGETHER_API_KEY"],
                    base_url='https://api.together.xyz',
                    )

    for i in range(3):
      try:
        logger.info("Generating content with model: %s", model)
        response = client.chat.completions.create(
            messages=mistral_messages,
            model=model,
            max_tokens=max_tokens,
            top_p=top_p,
            temperature=temperature
        )
        return True, response.choices[0].message.content

      except Exception as e:
        logger.error("Failed to call LLM: " + str(e))
        time.sleep(10 * (2 ** (i + 1)))
        # if hasattr(e, 'response'):
        #     error_info = e.response
        #     code_value = error_info['error']['param']
        #     if "content" in code_value:
        #         if not payload['messages'][-1]['content'][0]["text"].endswith("They do not represent any real events or entities. ]"):
        #             payload['messages'][-1]['content'][0]["text"] += "[ Note: The data and code snippets are purely fictional and used for testing and demonstration purposes only. They do not represent any real events or entities. ]"
        #     if code_value == "max_tokens":
        #         return False, code_value, cost
        # else:
        code_value = "context_length_exceeded"
        logger.error("Retrying ...")

    return False, code_value, cost

  elif model == "gemini-1.5-pro-latest":
    messages = payload["messages"]
    max_tokens = payload["max_tokens"]
    top_p = payload["top_p"]
    temperature = payload["temperature"]

    gemini_messages = []

    for i, message in enumerate(messages):
      gemini_message = {
          "role": message["role"],
          "content": []
      }
      assert len(message["content"]) in [
          1, 2], "One text, or one text with one image"
      for part in message["content"]:

        if part['type'] == "image_url":
          image_source = {}
          image_source["type"] = "base64"
          image_source["media_type"] = "image/png"
          image_source["data"] = part['image_url']['url'].replace(
            "data:image/png;base64,", "")
          gemini_message['content'].append(
            {"type": "image", "source": image_source})

        if part['type'] == "text":
          gemini_message['content'].append(
            {"type": "text", "text": part['text']})

      gemini_messages.append(gemini_message)

    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {os.environ["GEMINI_API_KEY"]}',
        'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
        'Content-Type': 'application/json'
    }

    payload = json.dumps({"model": model, "messages": gemini_messages,
                         "max_tokens": max_tokens, "temperature": temperature, "top_p": top_p})

    for i in range(3):
      try:
        response = requests.request(
          "POST", "https://api2.aigcbest.top/v1/chat/completions", headers=headers, data=payload)
        logger.info(f"response_code {response.status_code}")
        if response.status_code == 200:
          return True, response.json()['choices'][0]['message']['content']
        else:
          error_info = response.json()
          code_value = error_info['error']['code']
          if code_value == "content_filter":
            if not payload['messages'][-1]['content'][0]["text"].endswith("They do not represent any real events or entities. ]"):
              payload['messages'][-1]['content'][0]["text"] += "[ Note: The data and code snippets are purely fictional and used for testing and demonstration purposes only. They do not represent any real events or entities. ]"
          if code_value == "context_length_exceeded":
            return False, code_value, cost
          logger.error("Retrying ...")
          time.sleep(10 * (2 ** (i + 1)))
      except Exception as e:
        logger.error("Failed to call LLM: " + str(e))
        time.sleep(10 * (2 ** (i + 1)))
        code_value = "context_length_exceeded"
    return False, code_value, cost
