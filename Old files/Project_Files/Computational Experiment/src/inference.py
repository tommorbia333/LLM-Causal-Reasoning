"""
Inference module for running Hugging Face models on Apple Silicon via MPS.

Uses the transformers library with PyTorch MPS backend for GPU acceleration.
Qwen 2.5 7B Instruct in float16 requires ~14GB — fits in 24GB unified memory.

Usage:
    model = load_model("Qwen/Qwen2.5-7B-Instruct")
    response = generate(model, system_prompt, user_prompt)
"""

import json
import torch
from typing import Any, Optional
from transformers import AutoModelForCausalLM, AutoTokenizer


def get_device() -> str:
    """Determine the best available device."""
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_model(model_id: str, dtype: str = "float16", **kwargs) -> dict[str, Any]:
    """
    Load a model and tokenizer from Hugging Face Hub.

    Recommended models:
        - Qwen/Qwen2.5-7B-Instruct  (primary)
        - meta-llama/Llama-3.1-8B-Instruct  (comparison)

    Args:
        model_id: Hugging Face model identifier
        dtype: "float16" or "bfloat16" — float16 is safest on MPS

    Returns:
        dict containing model, tokenizer, device, and metadata.
    """
    device = get_device()
    torch_dtype = torch.float16 if dtype == "float16" else torch.bfloat16

    print(f"  Device: {device}")
    print(f"  Dtype:  {dtype}")
    print(f"  Loading tokenizer...")

    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        trust_remote_code=True,
    )

    print(f"  Loading model weights (this may take a moment on first run)...")

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch_dtype,
        device_map=device,
        trust_remote_code=True,
    )
    model.eval()

    # Ensure pad token is set
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    return {
        "model": model,
        "tokenizer": tokenizer,
        "device": device,
        "backend": "transformers",
        "model_id": model_id,
    }


def generate(
    model_bundle: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    max_new_tokens: int = 2048,
    temperature: float = 0.1,
    do_sample: bool = True,
    verbose: bool = False,
) -> str:
    """
    Generate a response given system + user prompts.

    Uses the model's chat template for proper formatting.

    Args:
        model_bundle: output of load_model()
        system_prompt: the schema/instruction prompt
        user_prompt: the current segment + graph state
        max_new_tokens: maximum tokens to generate
        temperature: sampling temperature (low = more deterministic)
        do_sample: whether to sample (False = greedy decoding)
        verbose: print the raw prompt and response

    Returns:
        The model's response as a string (decoded, prompt-stripped).
    """
    model = model_bundle["model"]
    tokenizer = model_bundle["tokenizer"]
    device = model_bundle["device"]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Apply chat template
    prompt_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    if verbose:
        print(f"--- PROMPT ({len(prompt_text)} chars) ---")
        preview = prompt_text[:500] + "..." if len(prompt_text) > 500 else prompt_text
        print(preview)
        print("--- END PROMPT ---\n")

    # Tokenize
    inputs = tokenizer(prompt_text, return_tensors="pt").to(device)
    input_length = inputs["input_ids"].shape[1]

    # Generate
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature if do_sample else None,
            do_sample=do_sample,
            pad_token_id=tokenizer.pad_token_id,
        )

    # Decode only the new tokens (strip the prompt)
    new_tokens = outputs[0][input_length:]
    response = tokenizer.decode(new_tokens, skip_special_tokens=True)

    if verbose:
        print(f"--- RESPONSE ({len(response)} chars) ---")
        preview = response[:500] + "..." if len(response) > 500 else response
        print(preview)
        print("--- END RESPONSE ---\n")

    return response


def extract_json(response: str) -> Optional[dict]:
    """
    Attempt to extract a JSON object from the model's response.

    Handles common issues:
    - Markdown code fences (```json ... ```)
    - Leading/trailing whitespace or commentary
    - Multiple JSON objects (takes the first complete one)
    """
    text = response.strip()

    # Strip markdown fences
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object boundaries
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None

    return None
