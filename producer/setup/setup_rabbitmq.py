#!/usr/bin/env python3
# setup_rabbitmq.py — robust startup/bootstrap for RabbitMQ (safe for Fly)
import os
import time
import random
import socket
import sys
from dotenv import load_dotenv

# load local .env if present (OK for local dev; on Fly env vars are used)
load_dotenv()

# Helper to read many possible names (compose vs secrets naming differences)
def get_env(*names, default=None):
    for n in names:
        v = os.getenv(n)
        if v is not None and v != "":
            return v
    return default

# Credentials & host/port (allow multiple env-var names)
USER = get_env("RABBIT_MQ_USER", "RABBITMQ_USER", "RABBIT_USER", default="guest")
PW   = get_env("RABBIT_MQ_PASSWORD", "RABBITMQ_PASSWORD", "RABBIT_PASS", default="guest")

# Host: try compose name, then common alternatives, then leave as 'rabbitmq'
HOST = get_env("RABBIT_MQ_HOST", "RABBITMQ_HOST", "RABBIT_HOST", "RABBITMQ_SERVICE", default="rabbitmq")
PORT = int(get_env("RABBIT_MQ_PORT", "RABBITMQ_PORT", default=5672))

# Optional fallback (e.g. rabbitmq-app.internal)
FALLBACK = get_env("RABBITMQ_FALLBACK", "RABBIT_MQ_FALLBACK", default=None)

# Exchange / queues / routing keys
EXCHANGE = get_env("RABBIT_MQ_EXCHANGE", "RABBITMQ_EXCHANGE", default="rabbitinflux.exchange")
DATA_QUEUE = get_env("RABBIT_MQ_QUEUE", "RABBITMQ_QUEUE", default="data.queue")
DATA_ROUTING = get_env("RABBIT_MQ_ROUTING_KEY", "RABBITMQ_ROUTING_KEY", default="data.routing")

HEALTH_QUEUE = get_env("RABBIT_MQ_HEALTH_DATA_QUEUE", "RABBITMQ_HEALTH_QUEUE", default="health.queue")
HEALTH_ROUTING = get_env("RABBIT_MQ_HEALTH_DATA_ROUTING_KEY", "RABBITMQ_HEALTH_ROUTING_KEY", default="health.routing")

# connection params
MAX_ATTEMPTS = int(get_env("RABBIT_SETUP_MAX_ATTEMPTS", default=60))
BASE_DELAY = float(get_env("RABBIT_SETUP_BASE_DELAY", default=1.0))  # seconds
MAX_DELAY = float(get_env("RABBIT_SETUP_MAX_DELAY", default=30.0))

# import pika lazily in runtime after env prepared (so errors are visible)
try:
    import pika
except Exception as e:
    print("Missing dependency 'pika' or failed to import it:", e)
    raise

def try_resolve(hostname, port):
    try:
        socket.getaddrinfo(hostname, port)
        return True
    except socket.gaierror:
        return False

def connect_with_retries():
    creds = pika.PlainCredentials(USER, PW)
    params = pika.ConnectionParameters(host=HOST, port=PORT, credentials=creds)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Attempt {attempt}/{MAX_ATTEMPTS} — resolving {HOST}:{PORT} ...")
            if not try_resolve(HOST, PORT):
                print(f"  DNS lookup failed for {HOST}.")
                if FALLBACK:
                    print(f"  Trying fallback host: {FALLBACK}")
                    # switch host to fallback and continue (will be used in next loop iteration)
                    global HOST  # intentionally update global HOST for the next attempt
                    HOST = FALLBACK
                    params = pika.ConnectionParameters(host=HOST, port=PORT, credentials=creds)
                else:
                    print("  No fallback provided. Will retry DNS after backoff.")
                    # fall through to sleep and retry
            else:
                print(f"  Hostname {HOST} resolved — attempting AMQP connect...")
                conn = pika.BlockingConnection(params)
                print(f"Connected to RabbitMQ at {HOST}:{PORT}")
                return conn

        except pika.exceptions.AMQPConnectionError as e:
            print(f"  AMQP connection error: {e}")
        except Exception as e:
            print(f"  Unexpected error while connecting: {type(e).__name__}: {e}")

        # backoff with jitter
        delay = min(MAX_DELAY, BASE_DELAY * (2 ** (attempt - 1)))
        jitter = random.uniform(0, delay * 0.1)
        sleep_time = delay + jitter
        print(f"  Waiting {sleep_time:.1f}s before next attempt...")
        time.sleep(sleep_time)

    # if we reach here, all attempts failed
    raise SystemExit(f"Could not connect to RabbitMQ at {HOST}:{PORT} after {MAX_ATTEMPTS} attempts")

def main():
    print("Starting RabbitMQ setup script with configuration:")
    print(f"  USER={USER}, HOST={HOST}, PORT={PORT}, EXCHANGE={EXCHANGE}")
    try:
        conn = connect_with_retries()
    except SystemExit as e:
        print(str(e))
        sys.exit(1)

    try:
        ch = conn.channel()

        # Declare the exchange
        ch.exchange_declare(exchange=EXCHANGE, exchange_type='topic', durable=True)
        print(f"✓ Exchange '{EXCHANGE}' declared (type: topic)")

        # Declare and bind data queue
        ch.queue_declare(queue=DATA_QUEUE, durable=True)
        ch.queue_bind(exchange=EXCHANGE, queue=DATA_QUEUE, routing_key=DATA_ROUTING)
        print(f"✓ Queue '{DATA_QUEUE}' declared and bound with routing key '{DATA_ROUTING}'")

        # Declare and bind health queue
        ch.queue_declare(queue=HEALTH_QUEUE, durable=True)
        ch.queue_bind(exchange=EXCHANGE, queue=HEALTH_QUEUE, routing_key=HEALTH_ROUTING)
        print(f"✓ Queue '{HEALTH_QUEUE}' declared and bound with routing key '{HEALTH_ROUTING}'")

    except Exception as e:
        print("Failed during queue/exchange declaration:", type(e).__name__, e)
        try:
            conn.close()
        except Exception:
            pass
        sys.exit(2)

    # close connection and exit successfully
    conn.close()
    print("✓ RabbitMQ setup completed successfully!")
    sys.exit(0)

if __name__ == "__main__":
    main()
