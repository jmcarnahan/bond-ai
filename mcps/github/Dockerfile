FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

# Install poetry
RUN pip install poetry==2.1.3

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install production dependencies only
RUN poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi --no-root

# Copy application code
COPY github/ ./github/
COPY github_mcp.py ./

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Run the MCP server
CMD ["fastmcp", "run", "github_mcp.py", "--transport", "streamable-http", "--port", "8000"]
