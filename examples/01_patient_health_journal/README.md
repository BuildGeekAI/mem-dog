# Patient Health Journal

Record daily symptoms, vitals, and medication notes. Query your health history with AI and explore extracted medical entities.

## Features Demonstrated

- **Simple facade** (`MemDog`) — add, search, get, entities, related
- **Timeline memory** for daily health entries
- **User memory** for patient profile
- **RAG chat** (`use_ai=True`) for natural-language health queries
- **Entity search** to find medications, symptoms, and conditions
- **Tags** for categorizing entries (vitals, symptom, medication)

## Run

```bash
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-key
python main.py
```

## What It Does

1. Creates a patient profile in user memory
2. Logs 8 health journal entries across different days
3. Queries: "When did headaches start?", "What medications am I taking?", "Blood pressure trend"
4. Searches for medication entities in the knowledge graph
5. Shows entities extracted from a specific journal entry
