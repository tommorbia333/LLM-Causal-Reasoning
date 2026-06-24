"""
Generic sweep launcher. Loads a named config from `configs/` and runs it.

Usage:
    python run_pilot.py <config_name>

For example:
    python run_pilot.py smoke_test
    python run_pilot.py pilot_prompt_manipulation

Each config is a Python module under `configs/` exposing a CONFIG dict.

Optional CONFIG keys:
  tasks            — subset of behavioural tasks to run, e.g. ``["pair_scaling"]``.
                     Default: all four (comprehension, ordering, pair_scaling, counterfactual).
  prompt_variants  — pair-scaling prompt ids when pair_scaling is in tasks, e.g.
                     ``["v5_human_like"]``. See ``src/prompts.py`` (PAIR_SCALING_VARIANTS).

Configs list models by standard Hugging Face / API ids (e.g. ``Qwen/Qwen2.5-7B-Instruct``).
Those are mapped through ``MODEL_REGISTRY`` in ``src/models.py`` via
``registry_key_for_hf_model_id`` → ``make_conversation``.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from src.sweep import run_sweep
from src.sweep_config import resolve_sweep_settings
from src import stimuli_loader
from src import models
from src.stimuli_loader import StimulusBundle


# ---------------------------------------------------------------------------
# Model loading: HF/API id → registry key → make_conversation
# ---------------------------------------------------------------------------
# Backends that keep large tensors resident in GPU/unified memory between calls.
# When the sweep moves to a different model, these need explicit eviction or
# the previous model's weights linger until the Python process exits, which
# causes MPS OOM on M-series machines (24 GB unified memory).
_GPU_RESIDENT_BACKENDS = {"hf", "mlx"}


def _evict_resident_model(prev_id: str, prev_conv: object) -> None:
    """Best-effort release of an HF/MLX model from GPU/unified memory.

    Moves HF model tensors to CPU first, drops Python references, runs gc,
    then calls torch.mps.empty_cache() if available. MLX has no equivalent
    explicit cache; dropping references + gc is the most we can do.
    """
    import gc

    print(f"Evicting previous model: {prev_id}")

    try:
        model_attr = getattr(prev_conv, "model", None)
        if model_attr is not None and hasattr(model_attr, "to"):
            try:
                model_attr.to("cpu")
            except Exception:
                pass

        for attr in ("model", "tokenizer", "_torch"):
            if hasattr(prev_conv, attr):
                try:
                    setattr(prev_conv, attr, None)
                except Exception:
                    pass
    finally:
        del prev_conv
        gc.collect()

        try:
            import torch
            if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass


def build_conversation_factory(
    stimuli: StimulusBundle,
    *,
    temperature: float,
    max_new_tokens: int,
):
    """Returns ``conversation_factory_for_model(hf_model_id)`` for ``run_sweep``."""

    _cache: dict[str, object] = {}

    def conversation_factory_for_model(hf_model_id: str):
        key = models.registry_key_for_hf_model_id(hf_model_id)
        spec = models.get_spec(key)

        if spec["backend"] == "mock":

            def factory_mock(story, seed):
                gold = stimuli.get_author_intended_graph(story.story_id)
                return models.make_conversation(
                    key,
                    seed=seed,
                    temperature=temperature,
                    max_new_tokens=max_new_tokens,
                    story=story,
                    gold_graph=gold or {},
                )

            return factory_mock

        if hf_model_id not in _cache:
            # Evict any GPU-resident model from a previous cell before loading
            # the next one. The sweep runner processes cells strictly in
            # series, so we never need more than one weight set in memory.
            stale_ids = [
                mid for mid, conv in _cache.items()
                if models.get_spec(
                    models.registry_key_for_hf_model_id(mid)
                )["backend"] in _GPU_RESIDENT_BACKENDS
            ]
            for stale_id in stale_ids:
                _evict_resident_model(stale_id, _cache.pop(stale_id))

            print(f"Loading model: {hf_model_id}  →  registry[{key!r}]")
            base = models.make_conversation(
                key,
                seed=0,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
            )
            _cache[hf_model_id] = base
            print(f"Loaded on {getattr(base, 'device', 'unknown')}")

        base_conv = _cache[hf_model_id]

        def factory(story, seed):
            base_conv.history = []
            base_conv._history_snapshot = None
            base_conv._seed = seed
            if hasattr(base_conv, "_system_snapshot"):
                base_conv._system = None
                base_conv._system_snapshot = None
            return base_conv

        return factory

    return conversation_factory_for_model


# ---------------------------------------------------------------------------
# Launcher
# ---------------------------------------------------------------------------

def _load_stimuli_from_config(config: dict):
    """Path in config may be omitted, or point to stimuli.json or its parent folder."""
    raw = config.get("stimuli_path")
    if raw is None:
        return stimuli_loader.load()
    p = Path(raw)
    if p.is_dir():
        p = p / "stimuli.json"
    return stimuli_loader.load(p)


def _list_available_configs() -> list[str]:
    configs_dir = Path(__file__).parent / "configs"
    return sorted(
        p.stem for p in configs_dir.glob("*.py")
        if p.stem != "__init__"
    )


def main():
    if len(sys.argv) != 2:
        print("Usage: python run_pilot.py <config_name>")
        print()
        print("Available configs:")
        for name in _list_available_configs():
            print(f"  {name}")
        sys.exit(1)

    config_name = sys.argv[1]
    try:
        config_module = importlib.import_module(f"configs.{config_name}")
    except ImportError as e:
        print(f"ERROR: could not load config '{config_name}': {e}")
        print()
        print("Available configs:")
        for name in _list_available_configs():
            print(f"  {name}")
        sys.exit(1)

    config = config_module.CONFIG

    print()
    print(f"Loaded config: {config_name}")
    if hasattr(config_module, "DESCRIPTION"):
        print(f"Description:   {config_module.DESCRIPTION}")
    print()

    stimuli = _load_stimuli_from_config(config)

    conversation_factory_for_model = build_conversation_factory(
        stimuli,
        temperature=config.get("temperature", 0.7),
        max_new_tokens=config.get("max_new_tokens", 80),
    )

    tasks, prompt_variants = resolve_sweep_settings(config)

    run_sweep(
        sweep_id=config["sweep_id"],
        models=config["models"],
        prompt_variants=prompt_variants,
        story_ids=config["story_ids"],
        conditions=config["conditions"],
        seeds=config["seeds"],
        stimuli=stimuli,
        conversation_factory_for_model=conversation_factory_for_model,
        outputs_root=Path(config.get("outputs_root", "outputs")),
        temperature=config.get("temperature", 0.7),
        max_new_tokens=config.get("max_new_tokens", 80),
        skip_existing=config.get("skip_existing", False),
        tasks=tasks,
    )


if __name__ == "__main__":
    main()
