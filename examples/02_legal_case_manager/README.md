# Legal Case Manager

Store case documents, witness statements, and legal precedents. Compare search modes and explore entity relationships.

## Features Demonstrated

- **Full client** (`MemDogClient`) for advanced operations
- **All 5 search modes** compared side-by-side (vector, fts, hybrid, graph, full)
- **All 4 rerankers** compared (none, rrf, mmr, cross-encoder)
- **Factual memory** for legal precedents
- **Episodic memory** for case timeline
- **Knowledge graph**: batch entity creation, relationship traversal
- **Tags**: add, search by tags

## Run

```bash
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-key
python main.py
```

## What It Does

1. Creates episodic memory for a case and factual memory for precedents
2. Stores 5 case documents and 3 legal precedents
3. Runs the same query across all 5 search modes, prints comparison
4. Compares all 4 rerankers on the same query
5. Creates entities (witnesses, judges, firms) and explores relationships
