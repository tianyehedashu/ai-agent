#!/usr/bin/env python3
"""Print configured LLM models (by API keys)."""
from bootstrap.config import settings
from domains.agent.infrastructure.llm import get_configured_models

configured = get_configured_models(settings)
if not configured:
    print("No LLM API keys configured. Set keys in .env (e.g. OPENAI_API_KEY, DEEPSEEK_API_KEY).")
else:
    print("Configured models by provider:")
    for provider, models in configured.items():
        print(f"  {provider}:")
        for m in models:
            print(f"    - {m['id']}  ({m['name']})")
