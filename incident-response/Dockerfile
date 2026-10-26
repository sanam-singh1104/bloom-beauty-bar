# On-call responder: Python service + the Claude Code CLI (needs Node).
#   docker build incident-response
FROM node:22.23.4-slim AS node

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISABLE_AUTOUPDATER=1

# Node runtime from the official image, then Claude Code pinned to a known version.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && npm install -g --no-fund --no-audit @anthropic-ai/claude-code@2.1.310 \
 && claude --version

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY responder ./responder

# Claude Code keeps its config in $HOME, so the user needs a writable one.
RUN useradd --create-home responder && mkdir /incidents /workspace \
 && chown responder /incidents
USER responder

EXPOSE 8001
CMD ["uvicorn", "responder.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
