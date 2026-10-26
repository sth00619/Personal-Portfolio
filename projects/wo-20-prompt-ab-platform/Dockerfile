FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY data/download.py data/download.py
COPY tests/ tests/
COPY pytest.ini .

CMD ["python", "src/experiment.py"]
