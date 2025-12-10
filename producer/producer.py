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
conn = pika.BlockingConnection(pika.ConnectionParameters(host=host, port=port, credentials=creds))
ch = conn.channel()

for i in range(5):
    msg = {"sensor_id": f"test-{i}", "value": 20 + i, "unit": "C"}
    ch.basic_publish(exchange=exchange, routing_key=routing, body=json.dumps(msg))
    print("Sent:", msg)
    time.sleep(1)

conn.close()
