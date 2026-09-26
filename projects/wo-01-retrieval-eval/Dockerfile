FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.14.0 \
    && pip install --no-cache-dir -r requirements.txt

COPY . ./

CMD ["sh", "-c", "python run.py --mode gate && pytest -q"]
