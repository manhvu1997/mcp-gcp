FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt


FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PYTHONOPTIMIZE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY src /app/src
COPY main.py /app/
COPY .env /app/.env
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
RUN groupadd -r mcp && \
    useradd -r -g mcp -d /app mcp && \
    chown -R mcp:mcp /app
USER mcp
CMD ["uv", "run", "main.py", "--transport", "stdio"]

# If you want to use SSE transport for remote access, uncomment:
# EXPOSE 8000
# CMD ["python", "-m", "src.main", "--transport", "sse", "--host", "0.0.0.0", "--port", "8000"]