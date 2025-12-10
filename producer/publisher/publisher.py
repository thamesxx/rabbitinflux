import pika
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

user = os.getenv("RABBIT_MQ_USER")
pw = os.getenv("RABBIT_MQ_PASSWORD")
host = os.getenv("RABBIT_MQ_HOST")
port = int(os.getenv("RABBIT_MQ_PORT"))
exchange = os.getenv("RABBIT_MQ_EXCHANGE")
routing = os.getenv("RABBIT_MQ_ROUTING_KEY")

# Number of messages to send (set to None for infinite)
MAX_MESSAGES = 10  # Change this number or set to None

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

# Publish messages
message_count = 0
try:
    while MAX_MESSAGES is None or message_count < MAX_MESSAGES:
        msg = {
            "sensor_id": f"sensor-{message_count % 10}",
            "value": 20 + (message_count % 50),
            "unit": "C"
        }
        ch.basic_publish(
            exchange=exchange,
            routing_key=routing,
            body=json.dumps(msg),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
            )
        )
        print(f"[{message_count}] Sent: {msg}")
        message_count += 1
        time.sleep(2)  # Send a message every 2 seconds
    
    print(f"\n✓ Finished sending {message_count} messages!")
        
except KeyboardInterrupt:
    print("\nPublisher stopped by user")
finally:
    conn.close()