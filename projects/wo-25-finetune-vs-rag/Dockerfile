FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src
COPY requirements-score.txt .
RUN pip install --no-cache-dir -r requirements-score.txt
COPY pyproject.toml .
COPY src ./src
COPY tests ./tests
CMD ["python", "-m", "wo25.score"]

