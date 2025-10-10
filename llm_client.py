import json
import os
import time
from typing import Any, Dict, List, Optional


class LLMClient:
    """Thin wrapper around an LLM provider (OpenAI-compatible) for JSON outputs.

    - Uses environment variables:
      - OPENAI_API_KEY
      - OPENAI_BASE_URL (optional)
      - LLM_MODEL (default: gpt-5)
    - Supports JSON-only responses with retry on malformed JSON.
    - No network calls occur unless methods are invoked.
    """

    def __init__(self, model: Optional[str] = None, temperature: float = 0.0, seed: Optional[int] = None):
        self.model = model or os.getenv("LLM_MODEL", "gpt-5")
        self.temperature = float(temperature)
        self.seed = seed
        self._client = None
        self._last_io: Optional[Dict[str, Any]] = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set; cannot use LLM client.")
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("openai package not installed. Run 'pip install openai'.") from e
        base_url = os.getenv("OPENAI_BASE_URL")
        if base_url:
            self._client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self._client = OpenAI(api_key=api_key)
        return self._client

    def complete_json(self, system_prompt: str, user_json: Dict[str, Any], json_schema: Optional[Dict[str, Any]] = None, max_retries: int = 1) -> Dict[str, Any]:
        """Get a JSON object from the model using chat.completions with json_object formatting.

        If json_schema is provided, we include it as a guideline in the user message; for strict schema enforcement, use external validation.
        """
        client = self._ensure_client()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_json, separators=(",", ":"))},
        ]
        response_format = {"type": "json_object"}
        last_err = None
        tried_without_temp = False

        def _call(with_temp: bool):
            params: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "response_format": response_format,
            }
            if with_temp and self.temperature is not None:
                params["temperature"] = self.temperature
            if self.seed is not None:
                params["seed"] = self.seed
            return client.chat.completions.create(**params), params

        attempts = max_retries + 1
        for _ in range(attempts + 1):  # allow one extra attempt without temperature when needed
            try:
                resp, used_params = _call(with_temp=not tried_without_temp)
            except Exception as e:
                estr = str(e)
                last_err = e
                # Fallback: some models reject explicit temperature; retry omitting it once
                if (not tried_without_temp) and ("unsupported" in estr.lower() and "temperature" in estr.lower()):
                    tried_without_temp = True
                    continue
                raise
            txt = resp.choices[0].message.content or "{}"
            # Record last raw IO for debugging
            self._last_io = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "model": self.model,
                "temperature": self.temperature,
                "used_temperature": used_params.get("temperature", None),
                "seed": self.seed,
                "system_prompt": system_prompt,
                "user_json": user_json,
                "response_text": txt,
            }
            try:
                return json.loads(txt)
            except Exception as e:
                last_err = e
                # Ask the model to reformat strictly as JSON
                messages.append({"role": "system", "content": "Return strictly valid JSON object only."})
        if last_err:
            raise last_err
        return {}
