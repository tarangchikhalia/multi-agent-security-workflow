FROM ghcr.io/astral-sh/uv:0.11.31 AS uv
FROM python:3.14-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev
RUN useradd --uid 10001 --create-home agent
USER agent
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=20s CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["/app/.venv/bin/uvicorn", "debug_agent.app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning", "--no-access-log"]
