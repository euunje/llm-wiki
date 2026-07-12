FROM python:3.11-slim-bookworm

# Install system dependencies for build packages and parsers (e.g., lxml, pdf extraction tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies using pyproject.toml
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV WIKI_ROOT=/app/workspace

CMD ["uvicorn", "llm_wiki.webapp.main:create_app_from_env", "--host", "0.0.0.0", "--port", "8000"]
