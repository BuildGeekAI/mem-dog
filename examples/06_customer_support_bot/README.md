# Customer Support Bot

Multi-turn support chatbot with FAQ knowledge base, conversation memory, and automatic compression.

## Features Demonstrated

- **LangChain adapter**: ChatMessageHistory and Retriever setup
- **Conversation memory** with 1-hour TTL for active chats
- **Factual memory** for FAQ knowledge base (no expiry)
- **User memory** for customer preferences
- **RAG chat** with conversation history for multi-turn
- **Memory compression** for old conversations
- **AI skills**: create a support triage skill

## Prerequisites

```bash
pip install -e "clients/python[langchain]"
```

## Run

```bash
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-key
python main.py
```

## What It Does

1. Seeds a knowledge base with 10 FAQ entries
2. Creates a support triage AI skill
3. Simulates 3 multi-turn support conversations
4. Compresses an old conversation with archival
5. Shows LangChain ChatMessageHistory and Retriever patterns
6. Stores learned user preferences
