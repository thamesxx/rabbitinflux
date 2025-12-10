# RabbitMQ Producer-Consumer Setup Guide

This guide explains how to set up and run the RabbitMQ producer and consumer system, both locally and across different machines.

## Project Structure

```
rabbitinflux/
├── producer/
│   ├── setup/
│   │   ├── docker-compose.yml
│   │   ├── Dockerfile
│   │   ├── setup_rabbitmq.py
│   │   └── requirements.txt
│   ├── publisher/
│   │   ├── docker-compose.yml
│   │   ├── Dockerfile
│   │   ├── publisher.py
│   │   └── requirements.txt
│   └── .env
└── consumer/
    ├── docker-compose.yml
    ├── Dockerfile
    ├── consumer.py
    └── requirements.txt
```

---

## Setup Instructions

### **1. RabbitMQ Broker & Queue Setup (Machine A)**

```bash
cd rabbitinflux/producer/setup
docker compose up -d --build
```

**What this does:**
- Starts RabbitMQ broker (port 5672, management UI on 15672)
- Creates exchange: `scada_data` (type: topic)
- Creates queues: `scada_data_queue`, `sensor_health_data_queue`
- Binds queues to exchange with routing keys

**Verify setup:**
```bash
docker logs -f rabbitmq-setup
# Should see: "✓ RabbitMQ setup completed successfully!"

# Check RabbitMQ is running
docker ps | grep rabbitmq

# Access management UI
# http://localhost:15672 (guest/guest)
```

---

### **2. Publisher Setup (Machine A)**

```bash
cd ../publisher  # From setup directory
docker compose up -d --build
```

**What this does:**
- Connects to RabbitMQ broker
- Publishes messages continuously to `scada_data` exchange
- Messages use routing key: `scada.tag.data`

**Verify publisher:**
```bash
docker logs -f scada-publisher
# Should see: "[0] Sent: {'sensor_id': 'sensor-0', 'value': 20, 'unit': 'C'}"
```

---

### **3. Consumer Setup**

#### **Scenario A: Running on Same Machine (Local)**

```bash
cd ../../consumer  # From publisher directory
docker compose up -d --build
```

**Verify consumer:**
```bash
docker logs -f scada_consumer
# Should see:
# - "✓ Connected to RabbitMQ"
# - ">>> Received message: ..."
# - "✓ Stored normal data → InfluxDB: ..."
```

#### **Scenario B: Running on Different Machine (Remote)**

**You need to change connection settings to point to Machine A's IP address.**

---

## Configuration Changes for Different Machines

### **Running Consumer on Different Machine (Machine B)**

#### **Option 1: Expose RabbitMQ Directly (Not Recommended for Production)**

**On Machine A** - Update `producer/setup/docker-compose.yml`:

```yaml
services:
  rabbitmq:
    image: rabbitmq:3.13-management
    container_name: rabbitmq
    ports:
      - "0.0.0.0:5672:5672"  # ← Change this to bind to all interfaces
      - "0.0.0.0:15672:15672"
    # ... rest remains same
```

**On Machine B** - Update `consumer/docker-compose.yml`:

Find the `environment` section for the consumer service and change:

```yaml
consumer:
  environment:
    RABBIT_MQ_HOST: 192.168.1.100  # ← Replace with Machine A's IP address
    RABBIT_MQ_PORT: 5672
    # ... rest remains same
```

**Get Machine A's IP address:**
```bash
# Windows
ipconfig

# Linux/Mac
ip addr show
# or
ifconfig
```

---

#### **Option 2: Using ngrok (For Testing/Development)**

**On Machine A:**
```bash
# Install ngrok: https://ngrok.com/download
ngrok tcp 5672
```

Copy the forwarding URL (e.g., `tcp://0.tcp.ap.ngrok.io:14168`)

**On Machine B** - Update `consumer/docker-compose.yml`:

```yaml
consumer:
  environment:
    RABBIT_MQ_HOST: 0.tcp.ap.ngrok.io  # ← Replace with your ngrok URL
    RABBIT_MQ_PORT: 14168               # ← Replace with your ngrok port
    # ... rest remains same
```

**Note:** ngrok URL changes every time you restart it (unless you have a paid plan).

---

#### **Option 3: VPN or Cloud Deployment (Recommended for Production)**

Set up both machines on the same VPN or deploy to cloud (AWS, Azure, GCP) where they can communicate via private network.

---

## Environment Variables Reference

### **Producer (.env file location: `producer/.env`)**

```env
# RabbitMQ Connection
RABBIT_MQ_USER=guest
RABBIT_MQ_PASSWORD=guest
RABBIT_MQ_HOST=rabbitmq          # For local: "rabbitmq", For remote: change to IP
RABBIT_MQ_PORT=5672

# RabbitMQ Topology
RABBIT_MQ_EXCHANGE=scada_data
RABBIT_MQ_QUEUE=scada_data_queue
RABBIT_MQ_ROUTING_KEY=scada.tag.data

RABBIT_MQ_HEALTH_DATA_QUEUE=sensor_health_data_queue
RABBIT_MQ_HEALTH_DATA_ROUTING_KEY=scada.sensor.health
```

### **Consumer (docker-compose.yml environment section)**

```yaml
environment:
  # RabbitMQ Connection - CHANGE THESE FOR REMOTE
  RABBIT_MQ_HOST: rabbitmq        # ← LOCAL: "rabbitmq" | REMOTE: Machine A IP or ngrok URL
  RABBIT_MQ_PORT: 5672            # ← LOCAL: 5672 | REMOTE: 5672 or ngrok port
  RABBIT_MQ_USER: guest
  RABBIT_MQ_PASSWORD: guest
  
  # RabbitMQ Topology - Keep same as producer
  RABBIT_MQ_EXCHANGE: scada_data
  RABBIT_MQ_QUEUE: scada_data_queue
  RABBIT_MQ_ROUTING_KEY: scada.tag.data
  RABBIT_MQ_HEALTH_DATA_QUEUE: sensor_health_data_queue
  RABBIT_MQ_HEALTH_DATA_ROUTING_KEY: scada.sensor.health
  
  # InfluxDB - Local to consumer machine
  INFLUX_DB_URL: http://influxdb:8086
  INFLUX_DB_TOKEN: your-token-here
  INFLUX_DB_ORG: my-org
  INFLUX_DB_BUCKET_NS: scada_bucket
  INFLUX_DB_MEASUREMENT: sensor_data
  INFLUX_DB_HEALTH_DATA_MEASUREMENT: sensor_health_data
```

---

## Quick Start Commands

### **Local Setup (Everything on One Machine):**

```bash
# Terminal 1 - Start RabbitMQ & Setup
cd rabbitinflux/producer/setup
docker compose up -d --build

# Terminal 2 - Start Publisher
cd ../publisher
docker compose up -d --build

# Terminal 3 - Start Consumer
cd ../../consumer
docker compose up -d --build

# Monitor logs
docker logs -f scada-publisher  # See messages being sent
docker logs -f scada_consumer   # See messages being consumed
```

---

### **Remote Setup (Producer on Machine A, Consumer on Machine B):**

**Machine A (Producer):**
```bash
# Terminal 1 - Start RabbitMQ & Setup
cd rabbitinflux/producer/setup
docker compose up -d --build

# Terminal 2 - Start Publisher
cd ../publisher
docker compose up -d --build

# Get Machine A's IP
ipconfig  # Windows
# or
ip addr show  # Linux
```

**Machine B (Consumer):**
```bash
# 1. Edit consumer/docker-compose.yml
#    Change RABBIT_MQ_HOST to Machine A's IP address

# 2. Start Consumer
cd rabbitinflux/consumer
docker compose up -d --build

# 3. Monitor logs
docker logs -f scada_consumer
```

---

## Stopping Services

```bash
# Stop consumer
cd consumer
docker compose down

# Stop publisher
cd producer/publisher
docker compose down

# Stop RabbitMQ
cd ../setup
docker compose down

# Remove volumes (clean slate)
docker compose down -v
```

---

## Troubleshooting

### **Messages not being consumed**

1. **Check consumer is registered:**
   ```bash
   # On Machine A (where RabbitMQ is running)
   docker exec -it rabbitmq rabbitmqctl list_consumers
   ```

2. **Check messages in queue:**
   ```bash
   docker exec -it rabbitmq rabbitmqctl list_queues name messages
   ```

3. **Check exchange bindings:**
   ```bash
   docker exec -it rabbitmq rabbitmqadmin list bindings
   ```

### **Consumer can't connect to RabbitMQ**

1. **Verify RabbitMQ is running:**
   ```bash
   docker ps | grep rabbitmq
   ```

2. **Test connection from consumer machine:**
   ```bash
   # Replace with Machine A's IP
   telnet 192.168.1.100 5672
   
   # Or use Python
   python3 -c "import socket; s=socket.socket(); s.settimeout(5); s.connect(('192.168.1.100', 5672)); print('Connected!'); s.close()"
   ```

3. **Check firewall:**
   ```bash
   # Windows - Allow port 5672
   netsh advfirewall firewall add rule name="RabbitMQ" dir=in action=allow protocol=TCP localport=5672
   ```

### **InfluxDB connection errors**

1. **Check InfluxDB is running:**
   ```bash
   docker ps | grep influxdb
   ```

2. **Verify InfluxDB health:**
   ```bash
   curl http://localhost:8086/health
   ```

---

## Port Reference

| Service | Port | Purpose |
|---------|------|---------|
| RabbitMQ AMQP | 5672 | Message broker protocol |
| RabbitMQ Management | 15672 | Web UI (http://localhost:15672) |
| InfluxDB | 8086 | Time-series database |

---

## Architecture Diagram

### Local Setup:
```
┌─────────────────────────────────────┐
│  Machine A                          │
│                                     │
│  ┌──────────┐    ┌──────────┐     │
│  │ RabbitMQ │◄───│Publisher │     │
│  └────┬─────┘    └──────────┘     │
│       │                             │
│       ▼                             │
│  ┌──────────┐    ┌──────────┐     │
│  │Consumer  │───►│ InfluxDB │     │
│  └──────────┘    └──────────┘     │
└─────────────────────────────────────┘
```

### Remote Setup:
```
┌─────────────────────┐         ┌─────────────────────┐
│  Machine A          │         │  Machine B          │
│                     │         │                     │
│  ┌──────────┐      │         │  ┌──────────┐      │
│  │ RabbitMQ │◄─────┼─────────┼──│Consumer  │      │
│  └────┬─────┘      │         │  └────┬─────┘      │
│       ▲             │         │       │             │
│  ┌────┴─────┐      │         │  ┌────▼─────┐      │
│  │Publisher │      │         │  │ InfluxDB │      │
│  └──────────┘      │         │  └──────────┘      │
└─────────────────────┘         └─────────────────────┘
          ▲                               │
          │      Internet/VPN/LAN         │
          └───────────────────────────────┘
```

---

## Summary of Changes Needed

| Scenario | Files to Change | What to Change |
|----------|----------------|----------------|
| **Local (same machine)** | None | Use defaults, everything works |
| **Remote (different machines)** | `consumer/docker-compose.yml` | Change `RABBIT_MQ_HOST` to Machine A's IP address |
| **Using ngrok** | `consumer/docker-compose.yml` | Change `RABBIT_MQ_HOST` to ngrok URL and `RABBIT_MQ_PORT` to ngrok port |
| **Custom credentials** | `producer/.env` | Change `RABBIT_MQ_USER` and `RABBIT_MQ_PASSWORD` |

---

## Best Practices

1. **Security:** Change default credentials (`guest/guest`) in production
2. **Monitoring:** Use RabbitMQ Management UI to monitor queues and consumers
3. **Scaling:** Run multiple consumer instances for load distribution
4. **Persistence:** Messages are durable (survive RabbitMQ restarts)
5. **Error Handling:** Failed messages are logged but not requeued

---

## Need Help?

- RabbitMQ Management UI: `http://localhost:15672` (guest/guest)
- Check logs: `docker logs -f <container-name>`
- List running containers: `docker ps`
- Restart a service: `docker compose restart <service-name>`