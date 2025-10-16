#!/usr/bin/env python3
"""Simple diagnostic script to verify Bedrock credentials/config."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None  # type: ignore[assignment]

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agents.bedrock_client import invoke_with_fallback


DEFAULT_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
FALLBACK_MESSAGE = "Hackathon fallback: unable to reach Bedrock."


def _mask(value: str | None) -> str:
    """Obfuscate secrets so they can be printed safely."""

    if not value:
        return "<missing>"
    if len(value) <= 4:
        return "*" * (len(value) - 1) + value[-1]
    return f"{value[:2]}…{value[-4:]}"


def _load_env(dotenv_path: str | None) -> None:
    """Load environment variables from .env when python-dotenv is installed."""

    if load_dotenv is None:
        return
    if dotenv_path and os.path.isfile(dotenv_path):
        load_dotenv(dotenv_path)
    else:
        load_dotenv()


def _print_env_overview() -> None:
    """Print a quick summary of AWS-related environment variables."""

    region = os.getenv("BEDROCK_REGION") or "us-east-1 (default)"
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    session_token = os.getenv("AWS_SESSION_TOKEN")

    print("Environment check:")
    print(f"  BEDROCK_REGION: {region}")
    print(f"  AWS_ACCESS_KEY_ID: {_mask(access_key)}")
    print(f"  AWS_SECRET_ACCESS_KEY: {_mask(secret_key)}")
    if session_token:
        print(f"  AWS_SESSION_TOKEN: {_mask(session_token)}")
    print()


def _invoke(model_id: str, prompt: str, temperature: float) -> Dict[str, Any]:
    """Invoke Bedrock using the shared helper."""

    return invoke_with_fallback(model_id, prompt, temperature=temperature)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Probe AWS Bedrock connectivity.")
    parser.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help=f"Model identifier to invoke (default: {DEFAULT_MODEL_ID})",
    )
    parser.add_argument(
        "--prompt",
        default="Please output your model name.",
        help="Prompt sent to the model.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature for the request.",
    )
    parser.add_argument(
        "--dotenv",
        default=None,
        help="Optional path to a .env file containing AWS credentials.",
    )

    args = parser.parse_args(argv)

    _load_env(args.dotenv)
    _print_env_overview()

    print(f"Invoking Bedrock model: {args.model_id}")
    response = _invoke(args.model_id, args.prompt, temperature=args.temperature)
    text = response.get("output", {}).get("text", "")
    usage = response.get("usage")
    has_raw = "raw" in response

    print("Response summary:")
    print(f"  Received raw payload: {has_raw}")
    if usage:
        print(f"  Usage: {json.dumps(usage)}")
    else:
        print("  Usage: <missing>")
    print(f"  Output text:\n{text}\n")

    if not has_raw or text.strip() == FALLBACK_MESSAGE:
        print(
            "Bedrock invocation appears to have fallen back to the offline stub.\n"
            "Verify your AWS credentials, permissions, and network connectivity."
        )
        return 1

    print("Bedrock invocation succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
