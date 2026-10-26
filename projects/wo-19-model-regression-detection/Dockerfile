FROM python:3.11-slim

WORKDIR /app/wo19

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ scripts/
COPY tests/ tests/
COPY pytest.ini .

ENV PYTHONPATH=/app/wo07

CMD ["python", "scripts/run_experiments.py"]
