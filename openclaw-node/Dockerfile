FROM coollabsio/openclaw:latest

USER root

# Install nginx for reverse proxy (8080 -> 18789)
RUN apt-get update && apt-get install -y --no-install-recommends nginx curl && rm -rf /var/lib/apt/lists/*

# Copy skills
COPY skills/ /data/.openclaw/skills/

# Copy custom entrypoint
COPY entrypoint.sh /opt/memdog/entrypoint.sh
RUN chmod +x /opt/memdog/entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/opt/memdog/entrypoint.sh"]
