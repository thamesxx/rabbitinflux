# publisher.py
import pika
import json
import os
import time
from dotenv import load_dotenv
from machine_data_generator import SyntheticMachineGenerator

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

# Initialise the generator
generator = SyntheticMachineGenerator()
print(f"Generator ready — session_id: {generator.session_id}")

# Stream one reading every 3 seconds
message_count = 0
try:
    while True:
        msg = generator.generate_one()
        ch.basic_publish(
            exchange=exchange,
            routing_key=routing,
            body=json.dumps(msg),
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistent
            )
        )
        print(f"[{message_count}] Published seq={msg['seq']}  length={msg['plc']['length']}  SF_Flow={msg['utility']['SF_Flow']}")
        message_count += 1
        time.sleep(3)

except KeyboardInterrupt:
    print("\nPublisher stopped by user")
finally:
    conn.close()