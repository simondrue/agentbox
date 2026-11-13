FROM node:24-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl git ripgrep procps \
       python3 python3-pip python3-venv build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @openai/codex

RUN mkdir -p /workspace /home/node/.codex \
    && chown -R node:node /workspace /home/node/.codex

USER node
WORKDIR /workspace

CMD ["codex"]
