FROM python:3.11-slim
WORKDIR /app
COPY requirements-score.txt ./requirements-score.txt
RUN pip install --no-cache-dir -r requirements-score.txt
COPY src ./src
CMD ["python", "src/score.py"]
