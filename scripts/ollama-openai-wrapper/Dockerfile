FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic
COPY wrapper.py .
ENV OLLAMA_BASE_URL=http://ollama:11434
EXPOSE 8000
CMD ["uvicorn", "wrapper:app", "--host", "0.0.0.0", "--port", "8000"]
