"""AI Agent Configuration Hub -- mem-dog example.

Manage AI agent configs, prompts, skills, engines, and model routing.
Track token usage and costs.

Usage:
    export MEM_DOG_URL=http://localhost:8080
    export MEM_DOG_API_KEY=your-key
    python main.py
"""

import os
import json
from datetime import datetime

from mem_dog_client import MemDogClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("MEM_DOG_URL", "http://localhost:8080")
API_KEY = os.environ.get("MEM_DOG_API_KEY", "")
USER_ID = "agent_hub_demo_user"

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

PROMPTS = [
    {
        "name": "classify_document",
        "description": "Classify an incoming document by type and priority.",
        "template": (
            "You are a document classifier. Given the following text, classify it into "
            "one of these categories: invoice, contract, report, correspondence, legal. "
            "Also assign a priority: low, medium, high.\n\n"
            "Text: {{text}}\n\n"
            "Respond as JSON: {\"category\": \"...\", \"priority\": \"...\"}"
        ),
        "model_hint": "small",
        "tags": ["classification", "document"],
    },
    {
        "name": "summarize_long_document",
        "description": "Generate a concise summary of a long document.",
        "template": (
            "Summarize the following document in 3-5 bullet points. Focus on key "
            "decisions, action items, and deadlines.\n\n"
            "Document: {{text}}\n\n"
            "Summary:"
        ),
        "model_hint": "medium",
        "tags": ["summarization"],
    },
    {
        "name": "extract_entities",
        "description": "Extract named entities (people, orgs, dates, amounts) from text.",
        "template": (
            "Extract all named entities from the following text. Return as JSON with "
            "keys: people (list), organizations (list), dates (list), amounts (list), "
            "locations (list).\n\n"
            "Text: {{text}}\n\n"
            "Entities:"
        ),
        "model_hint": "medium",
        "tags": ["extraction", "ner"],
    },
    {
        "name": "sentiment_analysis",
        "description": "Analyze sentiment of customer feedback.",
        "template": (
            "Analyze the sentiment of this customer feedback. Rate on a scale of "
            "1-5 (1=very negative, 5=very positive). Identify key themes.\n\n"
            "Feedback: {{text}}\n\n"
            "Response as JSON: {\"score\": N, \"sentiment\": \"...\", \"themes\": [...]}"
        ),
        "model_hint": "small",
        "tags": ["sentiment", "customer"],
    },
    {
        "name": "generate_report",
        "description": "Generate a structured report from raw data points.",
        "template": (
            "Given the following data points, generate a structured report with: "
            "Executive Summary, Key Findings, Recommendations, and Next Steps.\n\n"
            "Data: {{text}}\n\n"
            "Report:"
        ),
        "model_hint": "large",
        "tags": ["report", "generation"],
    },
]

SKILLS = [
    {
        "name": "document_triage",
        "description": "Classify, route, and prioritize incoming documents.",
        "skill_type": "pipeline",
        "config": {
            "steps": ["classify_document", "extract_entities", "route_by_category"],
            "timeout_seconds": 30,
            "fallback": "manual_review",
        },
    },
    {
        "name": "customer_insight",
        "description": "Analyze customer interactions for sentiment and themes.",
        "skill_type": "analysis",
        "config": {
            "steps": ["sentiment_analysis", "extract_entities"],
            "aggregation": "weekly_report",
            "alert_threshold": 2,  # alert if sentiment < 2
        },
    },
    {
        "name": "compliance_check",
        "description": "Scan documents for regulatory compliance issues.",
        "skill_type": "validation",
        "config": {
            "regulations": ["SOX", "GDPR", "AML"],
            "severity_levels": ["info", "warning", "violation"],
            "auto_flag": True,
        },
    },
]

AGENT_CONFIGS = [
    {
        "agent_type": "classifier",
        "name": "Document Classifier Agent",
        "description": "Lightweight agent for fast document classification.",
        "config": {
            "model_tier": "small",
            "max_tokens": 256,
            "temperature": 0.1,
            "prompt_id": None,  # will be filled after prompt creation
            "skill_ids": [],
            "retry_count": 2,
            "timeout_seconds": 10,
        },
    },
    {
        "agent_type": "summarizer",
        "name": "Document Summarizer Agent",
        "description": "Medium-tier agent for generating document summaries.",
        "config": {
            "model_tier": "medium",
            "max_tokens": 1024,
            "temperature": 0.3,
            "prompt_id": None,
            "skill_ids": [],
            "retry_count": 1,
            "timeout_seconds": 30,
        },
    },
    {
        "agent_type": "extractor",
        "name": "Entity Extractor Agent",
        "description": "Agent for extracting structured data from unstructured text.",
        "config": {
            "model_tier": "medium",
            "max_tokens": 2048,
            "temperature": 0.0,
            "prompt_id": None,
            "skill_ids": [],
            "retry_count": 3,
            "timeout_seconds": 45,
        },
    },
]


def check_system_health(client: MemDogClient) -> None:
    """Verify system health and AI configuration."""
    print("=" * 60)
    print("STEP 1: System Health Check")
    print("=" * 60)

    # AI config probe
    test_resp = client.ai_query_test()
    test_resp.raise_for_status()
    test_result = test_resp.json()
    print(f"  AI query test: {json.dumps(test_result, indent=2)[:200]}")

    # System config
    config_resp = client.get_system_config()
    config_resp.raise_for_status()
    config = config_resp.json()
    print(f"\n  System config keys: {list(config.keys())[:10]}")
    for key in ["embedding_model", "default_model", "search_mode"]:
        if key in config:
            print(f"    {key}: {config[key]}")


def explore_model_catalog(client: MemDogClient) -> None:
    """Browse the self-hostable model catalog."""
    print("\n" + "=" * 60)
    print("STEP 2: Model Catalog")
    print("=" * 60)

    # Full catalog
    catalog_resp = client.get_model_catalog()
    catalog_resp.raise_for_status()
    catalog = catalog_resp.json()
    models = catalog if isinstance(catalog, list) else catalog.get("models", [])
    print(f"  Total models in catalog: {len(models)}")

    for model in models[:5]:
        name = model.get("model_id") or model.get("name", "?")
        family = model.get("family", "?")
        role = model.get("role", "?")
        mem_gb = model.get("memory_gb", "?")
        print(f"    {name} (family={family}, role={role}, mem={mem_gb}GB)")

    # Filter by role
    print(f"\n  -- Filtering: role=embedding --")
    emb_resp = client.get_model_catalog(role="embedding")
    emb_resp.raise_for_status()
    emb_catalog = emb_resp.json()
    emb_models = emb_catalog if isinstance(emb_catalog, list) else emb_catalog.get("models", [])
    print(f"  Embedding models: {len(emb_models)}")

    # Get details for a specific model
    if models:
        model_id = models[0].get("model_id") or models[0].get("name")
        if model_id:
            detail_resp = client.get_model_details(model_id)
            detail_resp.raise_for_status()
            detail = detail_resp.json()
            print(f"\n  -- Details for {model_id} --")
            for key in ["description", "parameters", "quantization", "context_length"]:
                if key in detail:
                    print(f"    {key}: {detail[key]}")


def create_ai_engines(client: MemDogClient) -> list[str]:
    """Configure AI engines for different tiers."""
    print("\n" + "=" * 60)
    print("STEP 3: Configuring AI Engines")
    print("=" * 60)

    engines = [
        {
            "name": "ollama_small",
            "engine_type": "ollama",
            "model": "gemma3:4b",
            "description": "Small tier for classification tasks",
            "config": {
                "base_url": "http://ollama-small:11434",
                "temperature": 0.1,
                "max_tokens": 512,
            },
        },
        {
            "name": "ollama_medium",
            "engine_type": "ollama",
            "model": "gemma3:12b",
            "description": "Medium tier for summarization and extraction",
            "config": {
                "base_url": "http://ollama-medium:11434",
                "temperature": 0.3,
                "max_tokens": 2048,
            },
        },
        {
            "name": "gemini_large",
            "engine_type": "gemini",
            "model": "gemini-2.5-flash",
            "description": "Large tier for complex generation tasks",
            "config": {
                "temperature": 0.5,
                "max_tokens": 4096,
            },
        },
    ]

    engine_ids = []
    for eng in engines:
        resp = client.create_ai_engine(eng)
        resp.raise_for_status()
        result = resp.json()
        eid = result.get("engine_id") or result.get("id")
        engine_ids.append(eid)
        print(f"  Created engine: {eng['name']} ({eng['model']}) -> {eid}")

    # List all engines
    list_resp = client.list_ai_engines()
    list_resp.raise_for_status()
    all_engines = list_resp.json()
    items = all_engines if isinstance(all_engines, list) else all_engines.get("engines", [])
    print(f"\n  Total engines configured: {len(items)}")

    return engine_ids


def create_prompts(client: MemDogClient) -> list[str]:
    """Register prompt templates."""
    print("\n" + "=" * 60)
    print("STEP 4: Registering Prompts")
    print("=" * 60)

    prompt_ids = []
    for p in PROMPTS:
        resp = client.create_prompt(p)
        resp.raise_for_status()
        result = resp.json()
        pid = result.get("prompt_id") or result.get("id")
        prompt_ids.append(pid)
        print(f"  Created: {p['name']} ({p['model_hint']}) -> {pid}")

    # Update a prompt (add versioning note)
    updated = client.update_prompt(prompt_ids[0], {
        "description": "Classify an incoming document by type and priority. v1.1: "
                       "added 'memo' category.",
        "template": PROMPTS[0]["template"].replace(
            "legal.",
            "legal, memo."
        ),
    })
    updated.raise_for_status()
    print(f"\n  Updated prompt {prompt_ids[0]}: added 'memo' category")

    # List all prompts
    list_resp = client.list_prompts()
    list_resp.raise_for_status()
    all_prompts = list_resp.json()
    items = all_prompts if isinstance(all_prompts, list) else all_prompts.get("prompts", [])
    print(f"  Total prompts: {len(items)}")

    return prompt_ids


def register_skills(client: MemDogClient) -> list[str]:
    """Register AI skills."""
    print("\n" + "=" * 60)
    print("STEP 5: Registering Skills")
    print("=" * 60)

    skill_ids = []
    for s in SKILLS:
        resp = client.create_skill(s)
        resp.raise_for_status()
        result = resp.json()
        sid = result.get("skill_id") or result.get("id")
        skill_ids.append(sid)
        print(f"  Created: {s['name']} ({s['skill_type']}) -> {sid}")

    # List skills
    list_resp = client.list_skills()
    list_resp.raise_for_status()
    all_skills = list_resp.json()
    items = all_skills if isinstance(all_skills, list) else all_skills.get("skills", [])
    print(f"\n  Total skills: {len(items)}")

    return skill_ids


def configure_agents(
    client: MemDogClient, prompt_ids: list[str], skill_ids: list[str]
) -> list[str]:
    """Create agent configurations with linked prompts and skills."""
    print("\n" + "=" * 60)
    print("STEP 6: Configuring Agent Types")
    print("=" * 60)

    # Map prompts and skills to agent configs
    prompt_map = {
        "classifier": prompt_ids[0],    # classify_document
        "summarizer": prompt_ids[1],    # summarize_long_document
        "extractor": prompt_ids[2],     # extract_entities
    }
    skill_map = {
        "classifier": [skill_ids[0]],   # document_triage
        "summarizer": [],
        "extractor": [skill_ids[1]],    # customer_insight
    }

    config_ids = []
    for ac in AGENT_CONFIGS:
        agent_type = ac["agent_type"]
        ac["config"]["prompt_id"] = prompt_map.get(agent_type)
        ac["config"]["skill_ids"] = skill_map.get(agent_type, [])

        resp = client.create_agent_config(ac)
        resp.raise_for_status()
        result = resp.json()
        cid = result.get("config_id") or result.get("id")
        config_ids.append(cid)
        print(f"  Created: {ac['name']} (type={agent_type}) -> {cid}")

    # Resolve effective config for each agent type
    print(f"\n  -- Resolving effective configs --")
    for agent_type in ["classifier", "summarizer", "extractor"]:
        resolve_resp = client.resolve_agent_config(agent_type)
        resolve_resp.raise_for_status()
        resolved = resolve_resp.json()
        tier = resolved.get("config", {}).get("model_tier", "?")
        max_tok = resolved.get("config", {}).get("max_tokens", "?")
        print(f"    {agent_type}: model_tier={tier}, max_tokens={max_tok}")

    return config_ids


def track_token_usage(client: MemDogClient) -> None:
    """Record and query token usage for cost tracking."""
    print("\n" + "=" * 60)
    print("STEP 7: Token Usage & Cost Tracking")
    print("=" * 60)

    # Simulate token usage records
    usage_records = [
        {
            "user_id": USER_ID,
            "agent_type": "classifier",
            "model": "gemma3:4b",
            "prompt_tokens": 150,
            "completion_tokens": 45,
            "total_tokens": 195,
            "cost_usd": 0.0,  # self-hosted, no cost
            "timestamp": "2025-05-20T10:00:00Z",
        },
        {
            "user_id": USER_ID,
            "agent_type": "summarizer",
            "model": "gemma3:12b",
            "prompt_tokens": 2048,
            "completion_tokens": 512,
            "total_tokens": 2560,
            "cost_usd": 0.0,
            "timestamp": "2025-05-20T10:05:00Z",
        },
        {
            "user_id": USER_ID,
            "agent_type": "extractor",
            "model": "gemini-2.5-flash",
            "prompt_tokens": 1500,
            "completion_tokens": 800,
            "total_tokens": 2300,
            "cost_usd": 0.0023,  # cloud model
            "timestamp": "2025-05-20T10:10:00Z",
        },
    ]

    for rec in usage_records:
        resp = client.record_token_usage(rec)
        resp.raise_for_status()
        print(f"  Recorded: {rec['agent_type']} / {rec['model']} "
              f"-> {rec['total_tokens']} tokens (${rec['cost_usd']:.4f})")

    # Query usage for the user
    print(f"\n  -- Token usage for {USER_ID} --")
    usage_resp = client.get_token_usage(USER_ID)
    usage_resp.raise_for_status()
    usage = usage_resp.json()
    if isinstance(usage, dict):
        total = usage.get("total_tokens", "?")
        total_cost = usage.get("total_cost_usd", "?")
        print(f"  Total tokens: {total}")
        print(f"  Total cost:   ${total_cost}")
        by_model = usage.get("by_model", {})
        if by_model:
            print(f"  By model:")
            for model, stats in by_model.items():
                print(f"    {model}: {stats}")
    elif isinstance(usage, list):
        print(f"  Records: {len(usage)}")
        for u in usage[:5]:
            print(f"    {u.get('agent_type')}: {u.get('total_tokens')} tokens")


def track_agent_type_counts(client: MemDogClient) -> None:
    """Track agent type invocation counts."""
    print("\n" + "=" * 60)
    print("STEP 8: Agent Type Counts")
    print("=" * 60)

    # Increment counts to simulate usage
    increments = [
        ("classifier", 5),
        ("summarizer", 3),
        ("extractor", 7),
    ]

    for agent_type, count in increments:
        for _ in range(count):
            client.increment_agent_type(agent_type)
        print(f"  Incremented {agent_type} x{count}")

    # Get all counts
    counts_resp = client.get_agent_type_counts()
    counts_resp.raise_for_status()
    counts = counts_resp.json()
    print(f"\n  Agent type counts:")
    if isinstance(counts, dict):
        for k, v in counts.items():
            print(f"    {k}: {v}")
    elif isinstance(counts, list):
        for item in counts:
            print(f"    {item}")


def main():
    """Run the AI agent configuration hub demo."""
    print("AI Agent Configuration Hub -- mem-dog Example")
    print(f"API: {BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print()

    client = MemDogClient(BASE_URL, api_key=API_KEY)

    # Step 1: Health check
    check_system_health(client)

    # Step 2: Model catalog
    explore_model_catalog(client)

    # Step 3: AI engines
    engine_ids = create_ai_engines(client)

    # Step 4: Prompts
    prompt_ids = create_prompts(client)

    # Step 5: Skills
    skill_ids = register_skills(client)

    # Step 6: Agent configs
    config_ids = configure_agents(client, prompt_ids, skill_ids)

    # Step 7: Token usage
    track_token_usage(client)

    # Step 8: Agent type counts
    track_agent_type_counts(client)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  AI engines:     {len(engine_ids)}")
    print(f"  Prompts:        {len(prompt_ids)}")
    print(f"  Skills:         {len(skill_ids)}")
    print(f"  Agent configs:  {len(config_ids)}")
    print(f"  Agent types:    classifier, summarizer, extractor")
    print(f"  Token records:  3")
    print("\nDone.")


if __name__ == "__main__":
    main()
