import pika
import json
import os
import time
import csv
from pathlib import Path
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

# Function to read data from files
def read_data_file():
    data_dir = Path("data")
    
    # Check for JSON file
    json_files = list(data_dir.glob("*.json"))
    if json_files:
        file_path = json_files[0]
        print(f"Found JSON file: {file_path}")
        with open(file_path, 'r') as f:
            data = json.load(f)
        return (file_path, data if isinstance(data, list) else [data])
    
    # Check for CSV file
    csv_files = list(data_dir.glob("*.csv"))
    if csv_files:
        file_path = csv_files[0]
        print(f"Found CSV file: {file_path}")
        data = []
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        return (file_path, data)
    
    return None

# Wait for data file to appear
print("Checking for data files...")
result = None
while result is None:
    result = read_data_file()
    if result is None:
        print("No data files found. Waiting...")
        time.sleep(5)

file_path, messages = result
file_mtime = file_path.stat().st_mtime

print(f"Loaded {len(messages)} messages from data file")

# Publish messages
message_count = 0
try:
    for msg in messages:
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
    
    # Wait for file to change before sending again
    print("\nWaiting for data file to be updated...")
    while True:
        time.sleep(5)
        if file_path.exists():
            current_mtime = file_path.stat().st_mtime
            if current_mtime != file_mtime:
                print("File has been updated! Restarting...")
                break
        else:
            print("File was deleted. Checking for new files...")
            new_result = read_data_file()
            if new_result:
                new_file_path, _ = new_result
                if new_file_path != file_path:
                    print("New file detected! Restarting...")
                    break
        
except KeyboardInterrupt:
    print("\nPublisher stopped by user")
finally:
    conn.close()