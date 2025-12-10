FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rabbitmq_consumer.py .

CMD ["python", "rabbitmq_consumer.py"]
