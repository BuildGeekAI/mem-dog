# Research Paper Analyzer

Ingest research papers, generate multiple AI viewpoints, build citation graphs, and use analysis templates.

## Features Demonstrated

- **Viewpoints**: create multiple perspectives per paper, view history
- **Analysis templates**: create custom templates, seed defaults
- **Semantic memory** for topic clustering
- **Knowledge graph**: batch entity creation (authors, institutions), relationship traversal
- **Graph search** for concept exploration

## Run

```bash
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-key
python main.py
```

## What It Does

1. Ingests 4 research paper abstracts with metadata
2. Creates 3 viewpoints per paper (Key Findings, Methodology, Limitations)
3. Defines a custom "Paper Review" analysis template
4. Builds a citation graph with authors and institutions as entities
5. Explores topic relationships via graph search
