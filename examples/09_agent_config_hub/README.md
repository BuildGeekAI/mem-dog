# AI Agent Configuration Hub

Manage multi-agent AI configurations, prompt libraries, skill registries, and cost tracking.

## Features Demonstrated

- **Model catalog**: browse available models, get details
- **AI engines**: create and list engine configurations
- **Prompts**: full CRUD for reusable prompt templates
- **Skills**: register and manage AI skills
- **Agent configs**: create per-type configs, resolve effective config
- **Token usage**: record consumption, retrieve cost reports
- **Agent type counts**: track and increment/decrement agent counts
- **Health checks**: system config, AI query test

## Run

```bash
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-key
python main.py
```

## What It Does

1. Explores the model catalog for available models
2. Configures AI engine endpoints
3. Creates a prompt library with 5 reusable templates
4. Registers 3 AI skills (classify, summarize, extract)
5. Creates agent configs for 3 agent types and resolves effective configs
6. Records token usage and generates a cost report
