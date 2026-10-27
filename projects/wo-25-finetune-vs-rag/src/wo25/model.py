"""MLX model conversion and inference helpers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from wo25.config import BASE_MODEL_REPO, BASE_MODEL_REVISION, MODEL_DIR, QUANTIZATION_BITS, RESULTS_DIR


def convert_model() -> None:
    """Download the pinned Hugging Face model and convert it to local 4-bit MLX."""
    from mlx_lm import convert
    from huggingface_hub import snapshot_download

    snapshot = snapshot_download(repo_id=BASE_MODEL_REPO, revision=BASE_MODEL_REVISION)
    convert(str(snapshot), mlx_path=str(MODEL_DIR), quantize=True, q_bits=QUANTIZATION_BITS)
    _record_converted_model()


def _record_converted_model() -> None:
    """Add the converted model checksum and observed quantization rate to the manifest."""
    digest = hashlib.sha256()
    with (MODEL_DIR / "model.safetensors").open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    manifest_path = RESULTS_DIR / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config = json.loads((MODEL_DIR / "config.json").read_text(encoding="utf-8"))
    manifest["base_model"]["mlx_model_sha256"] = digest.hexdigest()
    manifest["base_model"]["quantization_config"] = config.get("quantization")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_model(adapter_path: Path | None = None):
    """Load the shared converted base, optionally applying a LoRA adapter."""
    from mlx_lm import load

    kwargs = {"adapter_path": str(adapter_path)} if adapter_path else {}
    return load(str(MODEL_DIR), **kwargs)


def generate(model, tokenizer, messages: list[dict[str, str]], max_tokens: int = 512) -> str:
    """Generate a deterministic greedy response from chat messages."""
    from mlx_lm import generate as mlx_generate
    from mlx_lm.generate import greedy_sampler

    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return mlx_generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens,
                        sampler=greedy_sampler, verbose=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--convert", action="store_true")
    args = parser.parse_args()
    if args.convert:
        convert_model()
    else:
        parser.error("Pass --convert")


if __name__ == "__main__":
    main()
