FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.11.4 /uv /bin/uv

WORKDIR /app

# Copy dependency definition
COPY pyproject.toml README.md /app/

# Install python dependencies
RUN uv pip install --system --no-cache -e ".[dev]"

# Copy source code
COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
