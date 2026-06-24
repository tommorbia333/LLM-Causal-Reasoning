"""
Model adapter: a Conversation object that wraps a model + chat history.

Two backends:
  - HFConversation:  Hugging Face transformers, MPS/CUDA/CPU.
  - MockConversation: synthetic responses for plumbing tests; condition-aware
    so smoke-test figures are interpretable.

The runner only depends on the `.ask(prompt) -> str` and `.pop_last_turn()`
methods of a Conversation, so models can be swapped freely.
"""

from __future__ import annotations

import random
import re
from typing import Optional

from .stimuli_loader import Story


# =============================================================================
# Hugging Face backend
# =============================================================================

class HFConversation:
    """
    Multi-turn conversation backed by a HF causal LM and its chat template.
    Re-tokenises history every turn (simple; no KV cache management). For Qwen
    7B on M5 this is fine for the 60-call pilot.
    """

    def __init__(self, model_id: str, dtype: str = "float16", device: str = "auto",
                 temperature: float = 0.7, max_new_tokens: int = 80, seed: int = 0):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._torch = torch
        if device == "auto":
            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        self.device = device

        torch_dtype = getattr(torch, dtype)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=torch_dtype
        ).to(device)
        self.model.eval()

        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self._seed = seed
        self.history: list[dict] = []
        self._history_snapshot: list[dict] | None = None

    def set_system(self, system_prompt: str):
        self.history = [{"role": "system", "content": system_prompt}]

    def seed_with_story(self, system_prompt: str, reading_prompt: str):
        """Seed the conversation with the story-reading turn."""
        self.set_system(system_prompt)
        self.history.append({"role": "user", "content": reading_prompt})
        ack = self._generate()
        self.history.append({"role": "assistant", "content": ack})
        self.snapshot()  # capture primed state for fast roll-back between task calls
        return ack

    def snapshot(self):
        """Capture current history; restore_snapshot() rolls back to here."""
        self._history_snapshot = list(self.history)

    def restore_snapshot(self):
        """Roll history back to the most recent snapshot."""
        if self._history_snapshot is not None:
            self.history = list(self._history_snapshot)

    def ask(self, user_prompt: str) -> str:
        self.history.append({"role": "user", "content": user_prompt})
        reply = self._generate()
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def pop_last_turn(self):
        """Remove the last user/assistant pair (used on parse-failure retry)."""
        if self.history and self.history[-1]["role"] == "assistant":
            self.history.pop()
        if self.history and self.history[-1]["role"] == "user":
            self.history.pop()

    def _generate(self) -> str:
        torch = self._torch
        prompt_ids = self.tokenizer.apply_chat_template(
            self.history, add_generation_prompt=True, return_tensors="pt"
        ).to(self.device)

        torch.manual_seed(self._seed)
        with torch.no_grad():
            out = self.model.generate(
                prompt_ids,
                max_new_tokens=self.max_new_tokens,
                do_sample=self.temperature > 0,
                temperature=max(self.temperature, 1e-5),
                pad_token_id=self.tokenizer.eos_token_id,
            )
        new_tokens = out[0, prompt_ids.shape[-1]:]
        text = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        return text


# =============================================================================
# Mock backend for smoke testing the pipeline without a real model
# =============================================================================

class MockConversation:
    """
    Synthetic-response model. Returns plausible answers so the pipeline can be
    run end-to-end without loading Qwen. Pair-scaling responses are derived
    from the author-intended graph plus condition-dependent noise: linear
    cleanest, atemporal noisiest. This makes smoke-test figures interpretable.
    """

    def __init__(self, story: Story, gold_graph: dict | None, seed: int = 0,
                 noise_by_condition: dict[str, float] | None = None):
        self.story = story
        self.gold_graph = gold_graph or {}
        self.rng = random.Random(seed)
        self.history: list[dict] = []
        self._history_snapshot: list[dict] | None = None
        self._last_user: Optional[str] = None
        self.noise_by_condition = noise_by_condition or {
            "linear": 0.4, "nonlinear": 1.0, "atemporal": 1.6,
        }

    def set_system(self, system_prompt: str):
        self.history = [{"role": "system", "content": system_prompt}]

    def seed_with_story(self, system_prompt: str, reading_prompt: str):
        self.set_system(system_prompt)
        self.history.append({"role": "user", "content": reading_prompt})
        self.history.append({"role": "assistant", "content": "Ready"})
        self.snapshot()
        return "Ready"

    def snapshot(self):
        self._history_snapshot = list(self.history)

    def restore_snapshot(self):
        if self._history_snapshot is not None:
            self.history = list(self._history_snapshot)

    def ask(self, user_prompt: str) -> str:
        self.history.append({"role": "user", "content": user_prompt})
        self._last_user = user_prompt
        reply = self._respond(user_prompt)
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def pop_last_turn(self):
        if self.history and self.history[-1]["role"] == "assistant":
            self.history.pop()
        if self.history and self.history[-1]["role"] == "user":
            self.history.pop()

    # ---- response synthesis -------------------------------------------------

    def _respond(self, prompt: str) -> str:
        if "Yes, No, or Unsure" in prompt:
            return self._mock_comprehension(prompt)
        if "comma-separated list of the labels" in prompt:
            return self._mock_ordering(prompt)
        if "single integer between 0 and 6" in prompt:
            return self._mock_pair_rating(prompt)
        if "single integer between 1 and 5" in prompt:
            return self._mock_cf_rating(prompt)
        return ""

    def _mock_comprehension(self, prompt: str) -> str:
        # 80% chance of correct response based on the prompt's role hint;
        # we don't have access to the item object here so we sample.
        # Bias toward Yes (4/6 of the items are Yes by design).
        return self.rng.choices(["Yes", "No", "Unsure"], weights=[0.6, 0.3, 0.1])[0]

    def _mock_ordering(self, prompt: str) -> str:
        # Recover the local-label → card-text mapping from the prompt itself,
        # then look up canonical position by card-text match against story events.
        label_to_pos: dict[str, int] = {}
        for m in re.finditer(r"\((\d+)\)\s+(.+?)\s*$", prompt, re.MULTILINE):
            label, card = m.group(1), m.group(2).strip()
            for ev in self.story.events:
                if ev.card.strip() == card:
                    label_to_pos[label] = ev.canonical_position
                    break
        sorted_labels = sorted(label_to_pos, key=label_to_pos.get)
        # Adjacent-swap noise scaled by condition (more swaps for atemporal)
        n_swaps = int(self.noise_by_condition[self.story.condition] * 1.5)
        for _ in range(n_swaps):
            if len(sorted_labels) < 2:
                break
            i = self.rng.randrange(len(sorted_labels) - 1)
            sorted_labels[i], sorted_labels[i + 1] = sorted_labels[i + 1], sorted_labels[i]
        return ", ".join(sorted_labels)

    def _mock_pair_rating(self, prompt: str) -> str:
        # Pair scaling now quotes the two event cards in the prompt; recover them.
        quoted = re.findall(r'"([^"]+)"', prompt)
        if len(quoted) < 2:
            return "0"
        src_card, tgt_card = quoted[0], quoted[1]
        src_id = next((ev.id for ev in self.story.events if ev.card.strip() == src_card.strip()), None)
        tgt_id = next((ev.id for ev in self.story.events if ev.card.strip() == tgt_card.strip()), None)
        if src_id is None or tgt_id is None:
            return "0"
        base = self._gold_strength(src_id, tgt_id)
        noise = self.rng.gauss(0, self.noise_by_condition[self.story.condition])
        rating = base + noise
        rating = max(0, min(6, round(rating)))
        return str(int(rating))

    def _gold_strength(self, src: str, tgt: str) -> float:
        """Map the author-intended graph onto a 0–6 strength."""
        for edge in self.gold_graph.get("causal_edges", []):
            if edge["source"] == src and edge["target"] == tgt:
                return 6.0 if edge["type"] == "causes" else 3.0
        return 0.0

    def _mock_cf_rating(self, prompt: str) -> str:
        """
        Synthesise a 1–5 CF rating. Recover the antecedent event by matching
        the "If X had not..." clause against the story's event cards/text by
        word overlap.
        """
        ant: str | None = None
        m = re.search(r"If\s+(.+?),\s*would", prompt, re.IGNORECASE | re.DOTALL)
        if m:
            clause = m.group(1).lower()
            clause_words = set(re.findall(r"\b\w+\b", clause))
            best_score, best_id = 0, None
            for ev in self.story.events:
                ev_words = set(re.findall(r"\b\w+\b", (ev.card + " " + ev.text).lower()))
                score = len(clause_words & ev_words)
                if score > best_score:
                    best_score, best_id = score, ev.id
            ant = best_id

        causal_distance = self._distance_to_e7(ant) if ant else None

        if causal_distance is None or causal_distance == float("inf"):
            base = 3.0  # null control: no change
        elif causal_distance == 1:
            base = 1.5  # direct cause: much less likely
        elif causal_distance == 2:
            base = 2.0  # one hop: less likely
        else:
            base = 2.6  # distal: between less likely and no change

        noise = self.rng.gauss(0, 0.4 + 0.3 * self.noise_by_condition[self.story.condition])
        rating = base + noise
        rating = max(1, min(5, round(rating)))
        return str(int(rating))

    def _distance_to_e7(self, src_id: str) -> float:
        """BFS distance in the gold graph from src to E7. inf if no path."""
        if src_id == "E7":
            return 0
        adj: dict[str, list[str]] = {}
        for e in self.gold_graph.get("causal_edges", []):
            adj.setdefault(e["source"], []).append(e["target"])
        # BFS
        seen, frontier, dist = {src_id}, [src_id], 0
        while frontier:
            dist += 1
            nxt: list[str] = []
            for node in frontier:
                for neighbour in adj.get(node, []):
                    if neighbour == "E7":
                        return dist
                    if neighbour not in seen:
                        seen.add(neighbour)
                        nxt.append(neighbour)
            frontier = nxt
        return float("inf")


# =============================================================================
# Backend: MLX (Apple Silicon native; supports 4-bit quants for 14B/32B on M5)
# =============================================================================

class MLXConversation:
    """
    Apple Silicon native inference via mlx-lm. Use this for Qwen 14B/32B (4-bit)
    that don't fit in fp16 on a 24 GB M5.

    Install: `pip install mlx-lm`
    """

    def __init__(self, model_id: str, temperature: float = 0.7,
                 max_new_tokens: int = 80, seed: int = 0):
        from mlx_lm import load as _mlx_load  # lazy
        self._mlx_lm = __import__("mlx_lm")
        self.model, self.tokenizer = _mlx_load(model_id)
        self.model_id = model_id
        self.device = "mlx"
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self._seed = seed
        self.history: list[dict] = []
        self._history_snapshot: list[dict] | None = None

    def set_system(self, system_prompt: str):
        self.history = [{"role": "system", "content": system_prompt}]

    def seed_with_story(self, system_prompt: str, reading_prompt: str):
        self.set_system(system_prompt)
        self.history.append({"role": "user", "content": reading_prompt})
        ack = self._generate()
        self.history.append({"role": "assistant", "content": ack})
        self.snapshot()
        return ack

    def snapshot(self):
        self._history_snapshot = list(self.history)

    def restore_snapshot(self):
        if self._history_snapshot is not None:
            self.history = list(self._history_snapshot)

    def ask(self, prompt: str) -> str:
        self.history.append({"role": "user", "content": prompt})
        response = self._generate()
        self.history.append({"role": "assistant", "content": response})
        return response

    def pop_last_turn(self):
        if (len(self.history) >= 2
                and self.history[-1]["role"] == "assistant"
                and self.history[-2]["role"] == "user"):
            self.history.pop()
            self.history.pop()

    def _generate(self) -> str:
        from mlx_lm.sample_utils import make_sampler          # add this import
        prompt = self.tokenizer.apply_chat_template(
            self.history, tokenize=False, add_generation_prompt=True
        )
        sampler = make_sampler(temp=self.temperature)          # build sampler
        text = self._mlx_lm.generate(
            self.model, self.tokenizer, prompt=prompt,
            max_tokens=self.max_new_tokens,
            sampler=sampler,                                   # pass sampler, not temp/temperature
            verbose=False,
        )
        return text.strip()


# =============================================================================
# Backend: OpenAI (gpt-4o, gpt-4o-mini)
# =============================================================================

class OpenAIConversation:
    """
    Chat completions via the OpenAI API. Reads OPENAI_API_KEY from env.

    Install: `pip install openai`
    """

    def __init__(self, model_id: str, temperature: float = 0.7,
                 max_new_tokens: int = 80, seed: int = 0):
        from openai import OpenAI  # lazy
        self._client = OpenAI()  # picks up OPENAI_API_KEY env var
        self.model_id = model_id
        self.device = "openai-api"
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self._seed = seed
        self.history: list[dict] = []
        self._history_snapshot: list[dict] | None = None

    def set_system(self, system_prompt: str):
        self.history = [{"role": "system", "content": system_prompt}]

    def seed_with_story(self, system_prompt: str, reading_prompt: str):
        self.set_system(system_prompt)
        self.history.append({"role": "user", "content": reading_prompt})
        ack = self._generate()
        self.history.append({"role": "assistant", "content": ack})
        self.snapshot()
        return ack

    def snapshot(self):
        self._history_snapshot = list(self.history)

    def restore_snapshot(self):
        if self._history_snapshot is not None:
            self.history = list(self._history_snapshot)

    def ask(self, prompt: str) -> str:
        self.history.append({"role": "user", "content": prompt})
        response = self._generate()
        self.history.append({"role": "assistant", "content": response})
        return response

    def pop_last_turn(self):
        if (len(self.history) >= 2
                and self.history[-1]["role"] == "assistant"
                and self.history[-2]["role"] == "user"):
            self.history.pop()
            self.history.pop()

    def _generate(self) -> str:
        resp = self._client.chat.completions.create(
            model=self.model_id,
            messages=self.history,
            temperature=self.temperature,
            max_tokens=self.max_new_tokens,
            seed=self._seed,
        )
        return (resp.choices[0].message.content or "").strip()


# =============================================================================
# Backend: Anthropic (Claude)
# =============================================================================

class AnthropicConversation:
    """
    Messages API via Anthropic SDK. Reads ANTHROPIC_API_KEY from env.

    Anthropic's API takes the system prompt as a separate argument rather than
    as a message in the history, so we hold it separately and build the request
    payload at generate time.

    Install: `pip install anthropic`
    """

    def __init__(self, model_id: str, temperature: float = 0.7,
                 max_new_tokens: int = 80, seed: int = 0):
        from anthropic import Anthropic  # lazy
        self._client = Anthropic()  # picks up ANTHROPIC_API_KEY env var
        self.model_id = model_id
        self.device = "anthropic-api"
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self._seed = seed  # not used by Anthropic API directly; kept for parity
        self._system: str | None = None
        # history holds only user/assistant turns (Anthropic-style)
        self.history: list[dict] = []
        self._history_snapshot: list[dict] | None = None
        self._system_snapshot: str | None = None

    def set_system(self, system_prompt: str):
        self._system = system_prompt
        self.history = []

    def seed_with_story(self, system_prompt: str, reading_prompt: str):
        self.set_system(system_prompt)
        self.history.append({"role": "user", "content": reading_prompt})
        ack = self._generate()
        self.history.append({"role": "assistant", "content": ack})
        self.snapshot()
        return ack

    def snapshot(self):
        self._history_snapshot = list(self.history)
        self._system_snapshot = self._system

    def restore_snapshot(self):
        if self._history_snapshot is not None:
            self.history = list(self._history_snapshot)
            self._system = self._system_snapshot

    def ask(self, prompt: str) -> str:
        self.history.append({"role": "user", "content": prompt})
        response = self._generate()
        self.history.append({"role": "assistant", "content": response})
        return response

    def pop_last_turn(self):
        if (len(self.history) >= 2
                and self.history[-1]["role"] == "assistant"
                and self.history[-2]["role"] == "user"):
            self.history.pop()
            self.history.pop()

    def _generate(self) -> str:
        resp = self._client.messages.create(
            model=self.model_id,
            system=self._system or "",
            messages=self.history,
            max_tokens=self.max_new_tokens,
            temperature=self.temperature,
        )
        # Anthropic returns a list of content blocks; concatenate text blocks.
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "".join(parts).strip()
