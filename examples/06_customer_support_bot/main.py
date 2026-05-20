"""Customer Support Bot -- mem-dog example.

Multi-turn support chatbot with FAQ knowledge base, conversation
memory, LangChain adapter, and automatic memory compression.

Usage:
    export MEM_DOG_URL=http://localhost:8080
    export MEM_DOG_API_KEY=your-key
    pip install mem-dog-client[langchain]
    python main.py
"""

import os
import json
from datetime import datetime

from mem_dog_client import MemDog, MemDogClient
from mem_dog_client.adapters.langchain import MemDogChatMessageHistory, MemDogRetriever

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("MEM_DOG_URL", "http://localhost:8080")
API_KEY = os.environ.get("MEM_DOG_API_KEY", "")

# ---------------------------------------------------------------------------
# Sample data: 10 FAQ entries for a SaaS product
# ---------------------------------------------------------------------------

FAQ_ENTRIES = [
    {
        "question": "How do I reset my password?",
        "answer": "Go to Settings > Security > Reset Password. You will receive "
                  "an email with a reset link valid for 24 hours.",
    },
    {
        "question": "What payment methods do you accept?",
        "answer": "We accept Visa, MasterCard, American Express, and bank "
                  "transfers (ACH/SEPA). Invoices are available for annual plans.",
    },
    {
        "question": "How do I cancel my subscription?",
        "answer": "Navigate to Billing > Manage Subscription > Cancel. Your "
                  "access continues until the end of the current billing period.",
    },
    {
        "question": "What is the uptime SLA?",
        "answer": "We guarantee 99.95% uptime on Business plans and 99.99% on "
                  "Enterprise plans. SLA credits are issued automatically.",
    },
    {
        "question": "How do I export my data?",
        "answer": "Use Settings > Data Management > Export. You can export as "
                  "JSON or CSV. Exports include all records, attachments, and metadata.",
    },
    {
        "question": "Can I add team members?",
        "answer": "Yes. Go to Team > Invite Members. Free plans support up to "
                  "3 members. Pro plans support 25, and Enterprise is unlimited.",
    },
    {
        "question": "How does single sign-on (SSO) work?",
        "answer": "SSO is available on Enterprise plans. We support SAML 2.0 "
                  "and OIDC. Configure it under Settings > Authentication > SSO.",
    },
    {
        "question": "What are API rate limits?",
        "answer": "Free: 100 req/min. Pro: 1,000 req/min. Enterprise: 10,000 "
                  "req/min. Rate limit headers are included in every response.",
    },
    {
        "question": "How do I enable two-factor authentication?",
        "answer": "Go to Settings > Security > 2FA. We support authenticator "
                  "apps (TOTP) and hardware security keys (WebAuthn).",
    },
    {
        "question": "Do you offer phone support?",
        "answer": "Phone support is included in Enterprise plans. Pro plans "
                  "get priority email (4h SLA). Free plans use community forums.",
    },
]

# 3 simulated multi-turn conversations
CONVERSATIONS = [
    {
        "customer": "billing_user_42",
        "turns": [
            ("user", "Hi, I need help with my billing."),
            ("assistant", "Of course! I can help with billing questions. What do you need?"),
            ("user", "I want to cancel my subscription but keep access until month end."),
            ("assistant", "Navigate to Billing > Manage Subscription > Cancel. "
                          "Your access continues until the end of the current billing period."),
            ("user", "Great, and can I get a refund for the unused portion?"),
            ("assistant", "Refunds for partial months are available within 14 days "
                          "of the billing date. I can submit a refund request for you."),
        ],
    },
    {
        "customer": "security_user_88",
        "turns": [
            ("user", "How do I set up 2FA on my account?"),
            ("assistant", "Go to Settings > Security > 2FA. We support "
                          "authenticator apps (TOTP) and hardware security keys."),
            ("user", "Can I require 2FA for my whole team?"),
            ("assistant", "Yes! As an admin, go to Team > Security Policies > "
                          "Require 2FA. All members will be prompted on their next login."),
        ],
    },
    {
        "customer": "api_user_15",
        "turns": [
            ("user", "I keep getting 429 errors on the API."),
            ("assistant", "You are hitting the rate limit. Check the "
                          "X-RateLimit-Remaining header. Free plans allow 100 req/min."),
            ("user", "How do I upgrade to get higher limits?"),
            ("assistant", "Go to Billing > Change Plan > Pro. Pro plans give "
                          "you 1,000 req/min. The change takes effect immediately."),
            ("user", "Does the Pro plan also give me webhook support?"),
            ("assistant", "Yes, Pro plans include webhooks with up to 50 "
                          "endpoints. Configure them under Settings > Webhooks."),
        ],
    },
]


def seed_faq_knowledge_base(m: MemDog) -> list[dict]:
    """Seed the FAQ knowledge base as factual memories."""
    print("=" * 60)
    print("STEP 1: Seeding FAQ Knowledge Base")
    print("=" * 60)

    faq_items = []
    for i, faq in enumerate(FAQ_ENTRIES, 1):
        content = f"Q: {faq['question']}\nA: {faq['answer']}"
        result = m.add(
            content,
            memory_type="factual",
            tags=["faq", "support", f"faq:{i:02d}"],
            name=f"FAQ: {faq['question'][:50]}",
        )
        faq_items.append(result)
        print(f"  [{i:2d}] Stored FAQ: {faq['question'][:45]}...")
        print(f"       data_id={result['data_id']}, memory_id={result['memory_id']}")

    print(f"\n  Total FAQ entries stored: {len(faq_items)}")
    return faq_items


def create_triage_skill(client: MemDogClient) -> str:
    """Register a support triage skill."""
    print("\n" + "=" * 60)
    print("STEP 2: Creating Support Triage Skill")
    print("=" * 60)

    resp = client.create_skill({
        "name": "support_triage",
        "description": "Classifies support tickets by urgency and routes to "
                       "the correct team: billing, security, technical, or general.",
        "skill_type": "classification",
        "config": {
            "categories": ["billing", "security", "technical", "general"],
            "priority_levels": ["low", "medium", "high", "critical"],
            "escalation_rules": {
                "critical": "page_on_call",
                "high": "assign_senior",
                "medium": "queue_standard",
                "low": "auto_faq",
            },
        },
    })
    resp.raise_for_status()
    skill = resp.json()
    skill_id = skill.get("skill_id") or skill.get("id")
    print(f"  Created skill: support_triage (id={skill_id})")

    # Verify it appears in the skill list
    list_resp = client.list_skills()
    list_resp.raise_for_status()
    skills = list_resp.json()
    items = skills if isinstance(skills, list) else skills.get("items", [])
    print(f"  Total registered skills: {len(items)}")

    return skill_id


def store_user_preferences(m: MemDog) -> list[dict]:
    """Store user preferences for personalized support."""
    print("\n" + "=" * 60)
    print("STEP 3: Storing User Preferences")
    print("=" * 60)

    preferences = [
        {
            "content": "User billing_user_42 prefers email communication. "
                       "Timezone: US/Pacific. Plan: Pro. Language: English.",
            "name": "Prefs: billing_user_42",
        },
        {
            "content": "User security_user_88 is an admin on Enterprise plan. "
                       "Prefers Slack notifications. Timezone: Europe/London.",
            "name": "Prefs: security_user_88",
        },
        {
            "content": "User api_user_15 is a developer on Free plan. "
                       "Prefers API/webhook responses. Timezone: Asia/Tokyo.",
            "name": "Prefs: api_user_15",
        },
    ]

    results = []
    for pref in preferences:
        result = m.add(
            pref["content"],
            memory_type="user",
            tags=["user_pref", "support_context"],
            name=pref["name"],
        )
        results.append(result)
        print(f"  Stored: {pref['name']} -> data_id={result['data_id']}")

    return results


def simulate_multi_turn_chat(client: MemDogClient) -> list[str]:
    """Run multi-turn conversations using RAG chat."""
    print("\n" + "=" * 60)
    print("STEP 4: Simulating Multi-Turn Conversations (RAG Chat)")
    print("=" * 60)

    memory_ids = []

    for conv in CONVERSATIONS:
        customer = conv["customer"]
        print(f"\n  --- Conversation with {customer} ---")

        # Build up conversation history turn by turn
        history = []
        for role, message in conv["turns"]:
            lc_role = role  # "user" or "assistant"
            history.append({"role": lc_role, "content": message})
            print(f"  [{role:>9}] {message[:70]}...")

        # Final RAG-powered response using full history
        last_user_msg = [t for t in conv["turns"] if t[0] == "user"][-1][1]
        resp = client.chat(
            last_user_msg,
            search_mode="hybrid",
            conversation_history=history[:-1],  # exclude last assistant reply
        )
        resp.raise_for_status()
        chat_result = resp.json()
        answer = chat_result.get("response", chat_result.get("answer", ""))
        sources = chat_result.get("sources", [])
        print(f"  [  RAG bot] {str(answer)[:70]}...")
        print(f"              Sources: {len(sources)} documents referenced")

        # Track memory IDs for compression later
        mid = chat_result.get("memory_id")
        if mid:
            memory_ids.append(mid)

    return memory_ids


def demonstrate_langchain_adapter(m: MemDog) -> None:
    """Show LangChain adapter integration patterns."""
    print("\n" + "=" * 60)
    print("STEP 5: LangChain Adapter Integration")
    print("=" * 60)

    # --- MemDogChatMessageHistory ---
    # In a real app, you would pass this to a LangChain ConversationChain
    # or RunnableWithMessageHistory.
    print("\n  -- MemDogChatMessageHistory --")

    history = MemDogChatMessageHistory(
        mem_dog=m,
        memory_type="conversation",
        user_id="langchain_demo_user",
    )
    print(f"  Initialized history (memory_type=conversation)")
    print(f"  Current messages in store: {len(history.messages)}")

    # Add messages (these persist to mem-dog)
    from langchain_core.messages import HumanMessage, AIMessage

    history.add_message(HumanMessage(content="What plans do you offer?"))
    history.add_message(AIMessage(
        content="We offer Free, Pro, and Enterprise plans. "
                "Pro starts at $29/mo with 1,000 API req/min."
    ))
    print(f"  Added 2 messages (human + ai)")
    print(f"  Messages after add: {len(history.messages)}")

    # --- MemDogRetriever ---
    # In a real app, you would chain this with an LLM via
    # RetrievalQA or create_retrieval_chain.
    print("\n  -- MemDogRetriever --")

    retriever = MemDogRetriever(
        mem_dog=m,
        search_kwargs={"limit": 5, "use_ai": False},
    )
    print(f"  Initialized retriever (limit=5, use_ai=False)")

    # Invoke the retriever (calls m.search internally)
    docs = retriever.invoke("password reset")
    print(f"  Query: 'password reset' -> {len(docs)} documents")
    for i, doc in enumerate(docs[:3]):
        print(f"    [{i+1}] {doc.page_content[:60]}...")

    # Pattern for use with a chain (illustrative, not executed):
    print("\n  -- Integration Pattern (not executed) --")
    print("  # from langchain.chains import RetrievalQA")
    print("  # from langchain_openai import ChatOpenAI")
    print("  # llm = ChatOpenAI(model='gpt-4o-mini')")
    print("  # qa = RetrievalQA.from_chain_type(llm, retriever=retriever)")
    print("  # answer = qa.invoke('How do I reset my password?')")


def compress_old_conversations(m: MemDog, memory_ids: list[str]) -> None:
    """Compress old conversation memories to save space."""
    print("\n" + "=" * 60)
    print("STEP 6: Compressing Old Conversations")
    print("=" * 60)

    if not memory_ids:
        # Use the FAQ memory as a demo target
        print("  No conversation memory IDs captured; using FAQ memory for demo.")
        # Search for any factual memory to compress
        results = m.search("", memory_type="factual", limit=1)
        if results:
            mid = results[0].get("memory_id") or results[0].get("id")
            if mid:
                memory_ids = [mid]

    for mid in memory_ids[:2]:  # compress up to 2 memories
        print(f"\n  Compressing memory: {mid}")
        try:
            result = m.compress(
                mid,
                archive_originals=True,
                max_summary_length=500,
            )
            print(f"    Summary data_id: {result.get('summary_data_id')}")
            print(f"    Original items:  {result.get('original_count')}")
            print(f"    Summary length:  {result.get('summary_length')} chars")
            print(f"    Archived:        {result.get('archived')}")
        except Exception as e:
            print(f"    Compression skipped: {e}")


def main():
    """Run the customer support bot demo."""
    print("Customer Support Bot -- mem-dog Example")
    print(f"API: {BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print()

    # Initialize clients
    m = MemDog(BASE_URL, api_key=API_KEY)
    client = m.client

    # Step 1: Seed FAQ knowledge base
    faq_items = seed_faq_knowledge_base(m)

    # Step 2: Create triage skill
    skill_id = create_triage_skill(client)

    # Step 3: Store user preferences
    user_prefs = store_user_preferences(m)

    # Step 4: Simulate multi-turn conversations
    memory_ids = simulate_multi_turn_chat(client)

    # Step 5: LangChain adapter demo
    demonstrate_langchain_adapter(m)

    # Step 6: Compress old conversations
    compress_old_conversations(m, memory_ids)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  FAQ entries:      {len(faq_items)}")
    print(f"  User preferences: {len(user_prefs)}")
    print(f"  Conversations:    {len(CONVERSATIONS)}")
    print(f"  Triage skill:     {skill_id}")
    print(f"  Memories compressed: {min(len(memory_ids), 2)}")
    print("\nDone.")


if __name__ == "__main__":
    main()
