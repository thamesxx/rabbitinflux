# consumer.py
import pika
import json
import logging
# from influxdb_client import InfluxDBClient, Point, WritePrecision
# from datetime import datetime
import os
import time
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("consumer")

# ===== MongoDB Config =====
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "machine_db")

mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client[MONGO_DB]
readings_col = mongo_db["machine_readings"]
readings_col.create_index([("session_id", ASCENDING), ("seq", ASCENDING)])

# ===== InfluxDB Config (commented out) =====
# INFLUX_URL = os.getenv("INFLUX_DB_URL")
# INFLUX_TOKEN = os.getenv("INFLUX_DB_TOKEN")
# INFLUX_ORG = os.getenv("INFLUX_DB_ORG")
# BUCKET = os.getenv("INFLUX_DB_BUCKET_NS")
# MEASUREMENT = os.getenv("INFLUX_DB_MEASUREMENT")
# HEALTH_MEASUREMENT = os.getenv("INFLUX_DB_HEALTH_DATA_MEASUREMENT")
# influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
# write_api = influx_client.write_api()

# ===== RabbitMQ Config =====
RABBIT_USER = os.getenv("RABBIT_MQ_USER")
RABBIT_PASS = os.getenv("RABBIT_MQ_PASSWORD")
RABBIT_HOST = os.getenv("RABBIT_MQ_HOST")
RABBIT_PORT = int(os.getenv("RABBIT_MQ_PORT"))

EXCHANGE = os.getenv("RABBIT_MQ_EXCHANGE")
QUEUE = os.getenv("RABBIT_MQ_QUEUE")
ROUTING = os.getenv("RABBIT_MQ_ROUTING_KEY")

HEALTH_QUEUE = os.getenv("RABBIT_MQ_HEALTH_DATA_QUEUE")
HEALTH_ROUTING = os.getenv("RABBIT_MQ_HEALTH_DATA_ROUTING_KEY")


def write_to_mongo(data: dict):
    try:
        readings_col.insert_one(data)
        logger.info(f"Stored to MongoDB → session={data.get('session_id', '?')}  seq={data.get('seq', '?')}")
    except Exception as e:
        logger.error(f"ERROR writing to MongoDB: {e}")


# ===== InfluxDB write functions (commented out) =====
# def write_normal_data(data: dict):
#     try:
#         p = (
#             Point(MEASUREMENT)
#             .tag("sensor_id", data.get("sensor_id", ""))
#             .tag("unit", str(data.get("unit", "")))
#             .tag("attribute", str(data.get("attribute", "")))
#             .field("value", float(data.get("value", 0)))
#             .time(datetime.utcnow(), WritePrecision.NS)
#         )
#         write_api.write(bucket=BUCKET, org=INFLUX_ORG, record=p)
#         logger.info("Stored normal data → InfluxDB")
#     except Exception as e:
#         logger.error(f"ERROR writing normal data: {e}")
#
# def write_health_data(data: dict):
#     try:
#         p = (
#             Point(HEALTH_MEASUREMENT)
#             .tag("sensor_id", str(data.get("sensor_id")))
#             .field("success_request", float(data.get("success_request", 0)))
#             .field("total_request", float(data.get("total_request", 0)))
#             .time(datetime.utcnow(), WritePrecision.NS)
#         )
#         write_api.write(bucket=BUCKET, org=INFLUX_ORG, record=p)
#         logger.info("Stored health data → InfluxDB")
#     except Exception as e:
#         logger.error(f"ERROR writing health data: {e}")


def on_message(ch, method, props, body):
    try:
        data = json.loads(body)
        write_to_mongo(data)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
    ch.basic_ack(method.delivery_tag)


def on_health_message(ch, method, props, body):
    try:
        data = json.loads(body)
        logger.info(f"Health message received: {data}")
        # write_health_data(data)  # swap in when InfluxDB is re-enabled
    except Exception as e:
        logger.error(f"Error processing health message: {e}")
    ch.basic_ack(method.delivery_tag)


def connect_and_consume():
    creds = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)

    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBIT_HOST,
                    port=RABBIT_PORT,
                    credentials=creds
                )
            )
            logger.info("Connected to RabbitMQ")

            ch = connection.channel()

            ch.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)

            # Normal queue
            ch.queue_declare(queue=QUEUE, durable=True)
            ch.queue_bind(exchange=EXCHANGE, queue=QUEUE, routing_key=ROUTING)
            logger.info(f"Bound queue '{QUEUE}' to exchange '{EXCHANGE}' with routing key '{ROUTING}'")
            ch.basic_consume(queue=QUEUE, on_message_callback=on_message)

            # Health queue
            ch.queue_declare(queue=HEALTH_QUEUE, durable=True)
            ch.queue_bind(exchange=EXCHANGE, queue=HEALTH_QUEUE, routing_key=HEALTH_ROUTING)
            logger.info(f"Bound queue '{HEALTH_QUEUE}' to exchange '{EXCHANGE}' with routing key '{HEALTH_ROUTING}'")
            ch.basic_consume(queue=HEALTH_QUEUE, on_message_callback=on_health_message)

            logger.info("Waiting for messages...")
            ch.start_consuming()

        except Exception as e:
            logger.warning(f"RabbitMQ not available, retrying in 5s: {e}")
            time.sleep(5)


if __name__ == "__main__":
    connect_and_consume()