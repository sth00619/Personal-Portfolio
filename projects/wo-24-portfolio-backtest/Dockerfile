FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src
COPY requirements.txt .
RUN pip install --no-cache-dir --index-url https://pypi.org/simple -r requirements.txt
COPY pyproject.toml .
COPY src ./src
COPY tests ./tests
COPY README.md ./README.md
COPY Makefile ./Makefile
CMD ["python", "-m", "wo24.pipeline"]
