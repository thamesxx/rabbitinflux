import pika, json, os, time
from dotenv import load_dotenv

load_dotenv()

user = os.getenv("RABBIT_MQ_USER")
pw = os.getenv("RABBIT_MQ_PASSWORD")
host = os.getenv("RABBIT_MQ_HOST")
port = int(os.getenv("RABBIT_MQ_PORT"))
exchange = os.getenv("RABBIT_MQ_EXCHANGE")
routing = os.getenv("RABBIT_MQ_ROUTING_KEY")

creds = pika.PlainCredentials(user, pw)

# Retry connection logic
max_retries = 10
retry_delay = 3

for attempt in range(max_retries):
    try:
        print(f"Attempting to connect to RabbitMQ (attempt {attempt + 1}/{max_retries})...")
        conn = pika.BlockingConnection(pika.ConnectionParameters(host=host, port=port, credentials=creds))
        print("Connected successfully!")
        break
    except pika.exceptions.AMQPConnectionError as e:
        if attempt < max_retries - 1:
            print(f"Connection failed. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
        else:
            print("Max retries reached. Exiting.")
            raise

ch = conn.channel()

# Declare the exchange (this creates it if it doesn't exist)
ch.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)
print(f"Exchange '{exchange}' declared")

# Optionally declare a queue and bind it (useful for testing)
queue_name = os.getenv("RABBIT_MQ_QUEUE")
if queue_name:
    ch.queue_declare(queue=queue_name, durable=True)
    ch.queue_bind(exchange=exchange, queue=queue_name, routing_key=routing)
    print(f"Queue '{queue_name}' declared and bound to exchange")

for i in range(5):
    msg = {"sensor_id": f"test-{i}", "value": 20 + i, "unit": "C"}
    ch.basic_publish(exchange=exchange, routing_key=routing, body=json.dumps(msg))
    print("Sent:", msg)
    time.sleep(1)

conn.close()