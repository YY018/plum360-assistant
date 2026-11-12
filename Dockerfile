# Builds the front end, installs the Python app, bakes the local search model
# into the image, and serves site + API from one FastAPI process.
# Private manual data is fetched at start-up by scripts/fetch_private_data.py
# when DATA_REPO is configured. Render sets PORT (10000 by default).

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . ./
COPY --from=web /web/dist ./frontend/dist
# Download the local embedding model once, at build time.
RUN python -c "from plum360_assistant.vector_store import LocalEmbeddings; LocalEmbeddings('BAAI/bge-small-en-v1.5').embed_query('warm up')"
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app
EXPOSE 10000
CMD ["sh", "-c", "python -m scripts.fetch_private_data && python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
