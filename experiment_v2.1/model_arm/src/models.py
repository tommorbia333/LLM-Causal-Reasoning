"""
Central model registry for the experiment.

Each entry maps a short CLI-friendly key (e.g. "qwen7b") to a backend type and
that backend's model identifier plus any model-specific config. Adding a new
model = one new entry here. Adding a new infrastructure type (e.g. Ollama,
vLLM, Together) = a new backend class in src/model.py plus one branch in
make_conversation().

Backends:
  - "hf"        → HFConversation (transformers + MPS/CUDA/CPU)
  - "mlx"       → MLXConversation (mlx-lm, Apple Silicon native, supports 4-bit)
  - "openai"    → OpenAIConversation (chat.completions API)
  - "anthropic" → AnthropicConversation (messages API)
  - "mock"      → MockConversation (synthetic outputs, for plumbing tests)

API backends require env vars: OPENAI_API_KEY, ANTHROPIC_API_KEY.
"""

from __future__ import annotations

from typing import Any


# -----------------------------------------------------------------------------
# Registry. Add new models here.
# -----------------------------------------------------------------------------
# memory_gb is an approximate weight footprint at the listed dtype/quant.
# Use it for sanity-checking against your machine before running.

MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    # ---- HuggingFace transformers, fp16 (M5 24 GB RAM, MPS) ----
    "qwen7b": {
        "backend": "hf",
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "dtype": "float16",
        "memory_gb": 14,
        "notes": "Default. Fits comfortably on M5 24 GB at fp16.",
    },
    "qwen3-8b": {
        "backend": "hf",
        "model_id": "Qwen/Qwen3-8B",
        "dtype": "float16",
        "memory_gb": 16,
        "notes": (
            "Qwen3 generation; thinking-mode is OFF by default for Qwen3 "
            "(unlike Qwen3.5+), so the existing HFConversation works as-is."
        ),
    },
    "llama8b": {
        "backend": "hf",
        "model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "dtype": "float16",
        "memory_gb": 16,
        "notes": "Comparison point, similar size to Qwen 7B.",
    },
    "mistral7b": {
        "backend": "hf",
        "model_id": "mistralai/Mistral-7B-Instruct-v0.3",
        "dtype": "float16",
        "memory_gb": 14,
        "notes": "Comparison point.",
    },

    # ---- MLX, 4-bit quantised (Apple Silicon native, fits larger models) ----
    "qwen14b": {
        "backend": "mlx",
        "model_id": "mlx-community/Qwen2.5-14B-Instruct-4bit",
        "memory_gb": 9,
        "notes": "Qwen2.5 14B on M5 via MLX 4-bit. Use this id in configs, not Qwen/Qwen2.5-14B-Instruct.",
    },
    "qwen3-14b": {
        "backend": "mlx",
        "model_id": "mlx-community/Qwen3-14B-4bit",
        "memory_gb": 9,
        "notes": (
            "Qwen3 14B via MLX 4-bit (~8 GB). Qwen3 supports thinking/reasoning; "
            "if outputs include thinking blocks, disable thinking in the chat template "
            "or add response stripping in HFConversation/MLXConversation."
        ),
    },
    "qwen32b": {
        "backend": "mlx",
        "model_id": "mlx-community/Qwen2.5-32B-Instruct-4bit",
        "memory_gb": 18,
        "notes": "Tight on 24 GB; close other apps before running.",
    },

    # ---- API models ----
    "gpt4o": {
        "backend": "openai",
        "model_id": "gpt-4o",
        "memory_gb": 0,
        "notes": "Frontier reference. Needs OPENAI_API_KEY. ~$0.01–0.05 per call.",
    },
    "gpt4o-mini": {
        "backend": "openai",
        "model_id": "gpt-4o-mini",
        "memory_gb": 0,
        "notes": "Cheaper OpenAI option. Good for piloting API path.",
    },
    "claude-sonnet": {
        "backend": "anthropic",
        "model_id": "claude-sonnet-4-5-20250929",
        "memory_gb": 0,
        "notes": "Frontier reference. Needs ANTHROPIC_API_KEY.",
    },

    # ---- Mock (testing only) ----
    "mock": {
        "backend": "mock",
        "model_id": "mock",
        "memory_gb": 0,
        "notes": "Synthetic outputs for plumbing tests; no model loaded.",
    },
}


def list_models() -> list[str]:
    return list(MODEL_REGISTRY.keys())


def get_spec(model_key: str) -> dict[str, Any]:
    if model_key not in MODEL_REGISTRY:
        keys = ", ".join(sorted(MODEL_REGISTRY))
        raise KeyError(f"Unknown model key '{model_key}'. Available: {keys}")
    return dict(MODEL_REGISTRY[model_key])


def describe(model_key: str) -> str:
    spec = get_spec(model_key)
    return (f"{model_key}  ({spec['backend']})\n"
            f"  model_id : {spec['model_id']}\n"
            f"  memory   : ~{spec['memory_gb']} GB\n"
            f"  notes    : {spec['notes']}")


def registry_key_for_hf_model_id(model_id: str) -> str:
    """Map a Hugging Face / API `model_id` string to the short registry key.

    Configs can list standard IDs like ``Qwen/Qwen2.5-7B-Instruct``; this finds
    the matching ``MODEL_REGISTRY`` entry. Raises ``KeyError`` if unknown or ambiguous.
    """
    matches = [k for k, spec in MODEL_REGISTRY.items()
               if spec.get("model_id") == model_id]
    if len(matches) == 1:
        return matches[0]
    if len(matches) == 0:
        registered = "\n".join(
            f"  {k:16s} → {MODEL_REGISTRY[k]['model_id']}"
            for k in sorted(MODEL_REGISTRY)
        )
        raise KeyError(
            f"No MODEL_REGISTRY entry for model_id={model_id!r}. "
            f"Add one in models.py or fix the config.\n{registered}"
        )
    raise KeyError(
        f"Ambiguous model_id={model_id!r}: matches registry keys {matches}"
    )


# -----------------------------------------------------------------------------
# Factory: model_key → Conversation instance
# -----------------------------------------------------------------------------

def make_conversation(model_key: str, *, seed: int = 0,
                      temperature: float = 0.7, max_new_tokens: int = 80,
                      story=None, gold_graph=None) -> Any:
    """Resolve a registry key to a fresh Conversation object.

    Backend-specific imports are lazy so unused backends don't need their deps installed.
    """
    spec = get_spec(model_key)
    backend = spec["backend"]
    model_id = spec["model_id"]

    if backend == "hf":
        from .model import HFConversation
        return HFConversation(
            model_id=model_id,
            dtype=spec.get("dtype", "float16"),
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            seed=seed,
        )
    if backend == "mlx":
        from .model import MLXConversation
        return MLXConversation(
            model_id=model_id,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            seed=seed,
        )
    if backend == "openai":
        from .model import OpenAIConversation
        return OpenAIConversation(
            model_id=model_id,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            seed=seed,
        )
    if backend == "anthropic":
        from .model import AnthropicConversation
        return AnthropicConversation(
            model_id=model_id,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            seed=seed,
        )
    if backend == "mock":
        from .model import MockConversation
        if story is None:
            raise ValueError("mock backend requires `story` to be passed in")
        return MockConversation(story=story, gold_graph=gold_graph or {}, seed=seed)

    raise ValueError(f"Unknown backend '{backend}' for model '{model_key}'")
