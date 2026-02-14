# -*- coding: utf-8 -*-
"""
UI LLM Infrastructure
Bedrock client creation, prompt assembly, model invocation, and JSON extraction.
Swap this file to change LLM provider without touching any node or config.
"""

from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

try:
    import boto3  # type: ignore
except ImportError:
    boto3 = None  # type: ignore

if TYPE_CHECKING:
    from .ui_state import UIAgentState

from .ui_components import UI_COMPONENTS, SYSTEM_PROMPT_TEMPLATE
from .ui_config import (
    BEDROCK_MAX_TOKENS,
    BEDROCK_MODEL_ID,
    BEDROCK_REGION,
    BEDROCK_TEMPERATURE,
    GOAL_PLANNING_PROMPT,
    INTENT_ROUTES,
    LANGUAGE_PROMPTS,
    PLATFORM_PROMPTS,
)


# ── Client ─────────────────────────────────────────────────────────────────────

def get_bedrock_client():
    """Return a boto3 Bedrock Runtime client, or None on failure."""
    if boto3 is None:
        return None
    try:
        return boto3.client(
            "bedrock-runtime",
            region_name=BEDROCK_REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
        )
    except Exception as exc:
        print(f"[UIAgent] Bedrock client init failed: {exc}")
        return None


# ── Prompt builder ─────────────────────────────────────────────────────────────

def _format_chat_history(messages: list) -> str:
    lines = []
    for msg in messages:
        role = "User" if getattr(msg, "type", "") == "human" else "Assistant"
        lines.append(f"{role}: {str(getattr(msg, 'content', ''))[:500]}")
    return "\n".join(lines)


def build_prompt(state: "UIAgentState") -> str:
    platform = state.get("platform", "web")
    language = state.get("language", "Chinese")
    intent   = str(state.get("intent", "")).lower()

    print(f"[LLM] build_prompt | intent={intent!r} | language={language!r} | platform={platform!r}")

    context = {
        "intent":                  state.get("intent"),
        "platform":                platform,
        "language":                language,          # ← LLM now sees language in data
        "user_input":              state.get("user_input"),
        "agent_response":          state.get("agent_response"),
        "nutrition_facts":         state.get("nutrition_facts"),
        "food_detection_json":     state.get("food_detection_json"),
        "recommended_restaurants": state.get("recommended_restaurants"),
        "has_image":               state.get("has_image", False),
        "image_path":              state.get("food_vis_path"),
        "chat_history_summary":    _format_chat_history(state.get("chat_history") or []),
        "user_history":            state.get("user_history"),
    }

    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        components_json=json.dumps(UI_COMPONENTS, indent=2)
    )
    prompt += PLATFORM_PROMPTS.get(platform, PLATFORM_PROMPTS["web"])

    if intent in INTENT_ROUTES.get("goal_planning", set()):
        prompt += GOAL_PLANNING_PROMPT

    prompt += f"\n\nCurrent State Data:\n{json.dumps(context, indent=2, default=str)}"

    # Language instruction goes LAST so it overrides everything above
    prompt += LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["Chinese"])

    print(f"[LLM] Prompt assembled | total_chars={len(prompt)}")
    return prompt


# ── Model invocation ───────────────────────────────────────────────────────────

def invoke_bedrock(client, prompt: str) -> Tuple[str, int, int]:
    """Send *prompt* to Bedrock; return (response_text, input_tokens, output_tokens). Raises on error."""
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens":        BEDROCK_MAX_TOKENS,
        "temperature":       BEDROCK_TEMPERATURE,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    }
    print(f"[LLM] Invoking Bedrock | model={BEDROCK_MODEL_ID} | max_tokens={BEDROCK_MAX_TOKENS}")
    response = client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    headers = response.get("ResponseMetadata", {}).get("HTTPHeaders", {})
    in_tok  = int(headers.get("x-amzn-bedrock-input-token-count", 0))
    out_tok = int(headers.get("x-amzn-bedrock-output-token-count", 0))
    print(f"[LLM] Bedrock response received | in_tokens={in_tok} | out_tokens={out_tok}")

    result = json.loads(response["body"].read())
    raw_text = result["content"][0]["text"]
    print(f"[LLM] Raw output (first 200 chars): {raw_text[:200]!r}")
    return raw_text, in_tok, out_tok


# ── JSON extraction ────────────────────────────────────────────────────────────

def parse_plan_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse the first JSON object in *text*; return None on failure."""
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        print("[LLM] parse_plan_json: no JSON object found in LLM output")
        return None
    raw = match.group(0)
    try:
        parsed = json.loads(raw)
        print(f"[LLM] parse_plan_json OK | mode={parsed.get('mode')!r} | sections={len(parsed.get('sections', []))}")
        return parsed
    except json.JSONDecodeError:
        try:
            parsed = json.loads(raw, strict=False)
            print(f"[LLM] parse_plan_json OK (strict=False) | mode={parsed.get('mode')!r}")
            return parsed
        except Exception as exc:
            print(f"[LLM] parse_plan_json FAILED: {exc}")
            return None
