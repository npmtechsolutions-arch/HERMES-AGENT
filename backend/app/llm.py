"""
Local LLM integration via Ollama (the spec's local-first inference runtime).

Implements complexity-based routing (LC-03/LC-04): simple tasks → a small fast
model, complex reasoning → a larger model. Everything degrades gracefully: if
Ollama is unreachable, callers fall back to deterministic logic so the product
never breaks.

Privacy: Ollama runs entirely on localhost — no inference leaves the machine,
honoring the privacy pillar.
"""
import json
import os
import urllib.error
import urllib.request

OLLAMA_URL = os.getenv("HERMUS_OLLAMA_URL", "http://127.0.0.1:11434")
MODEL_FAST = os.getenv("HERMUS_MODEL_FAST", "llama3.2:3b")      # LC-03 small/fast
MODEL_SMART = os.getenv("HERMUS_MODEL_SMART", "qwen2.5:7b")     # LC-04 capable
MODEL_EMBED = os.getenv("HERMUS_MODEL_EMBED", "nomic-embed-text")

_available_cache = None


def available() -> bool:
    """Is the local LLM runtime reachable? Cached after first probe."""
    global _available_cache
    if _available_cache is not None:
        return _available_cache
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as r:
            json.load(r)
        _available_cache = True
    except Exception:
        _available_cache = False
    return _available_cache


def list_models() -> list[dict]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as r:
            data = json.load(r)
        return [{"name": m["name"],
                 "family": m.get("details", {}).get("family"),
                 "size": m.get("details", {}).get("parameter_size"),
                 "quant": m.get("details", {}).get("quantization_level")}
                for m in data.get("models", [])]
    except Exception:
        return []


def chat(prompt: str, *, system: str | None = None, smart: bool = False,
         json_mode: bool = False, timeout: int = 60,
         num_predict: int | None = None, model: str | None = None,
         temperature: float | None = None, num_ctx: int | None = None) -> str | None:
    """Single-turn generation. Returns text, or None if the runtime is down.

    The per-tenant Hermes agent config can override model/temperature/limits."""
    if not available():
        return None
    model = model or (MODEL_SMART if smart else MODEL_FAST)
    options = {"temperature": 0.3 if temperature is None else float(temperature)}
    if num_predict:
        options["num_predict"] = num_predict
    if num_ctx:
        options["num_ctx"] = num_ctx
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": options,
    }
    if system:
        payload["system"] = system
    if json_mode:
        payload["format"] = "json"
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r).get("response", "").strip()
    except Exception:
        return None


def chat_json(prompt: str, *, system: str | None = None, smart: bool = False,
              timeout: int = 150, num_predict: int | None = 320) -> dict | None:
    """Generation constrained to JSON; returns a parsed dict or None."""
    raw = chat(prompt, system=system, smart=smart, json_mode=True, timeout=timeout,
               num_predict=num_predict)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        # try to salvage a JSON object from within the text
        try:
            start, end = raw.index("{"), raw.rindex("}") + 1
            return json.loads(raw[start:end])
        except Exception:
            return None


def embed(text: str) -> list[float] | None:
    """Embedding vector via nomic-embed-text, or None if unavailable."""
    if not available():
        return None
    try:
        data = json.dumps({"model": MODEL_EMBED, "prompt": text}).encode()
        req = urllib.request.Request(f"{OLLAMA_URL}/api/embeddings", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r).get("embedding")
    except Exception:
        return None


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0
