# OrderFlow Integrator

[![CI](https://github.com/hunterinvariants/orderflow-integrator/actions/workflows/ci.yml/badge.svg)](https://github.com/hunterinvariants/orderflow-integrator/actions/workflows/ci.yml)

OrderFlow Integrator is a FastAPI service that accepts orders, normalizes them, and routes them through a simple integration workflow.

## What it includes

- FastAPI API with `/health` and `/ready`
- In-memory order flow lifecycle
- Integration registry for routing targets
- Dockerfile and Docker Compose setup
- Linux-friendly line endings and platform-neutral commands

## Run locally with Docker

```bash
docker compose up --build
```

If your system still uses the legacy Compose v1 CLI, use:

```bash
docker-compose up --build
```

Open:

- `http://localhost:8000/health`
- `http://localhost:8000/docs`

## Run tests

```bash
python -m pip install -e ".[dev]"
pytest
```

## Environment

The service runs with safe development defaults. To customize it, use the
variables shown in `.env.example` through a Compose `environment` or `env_file`
configuration.

## Deployment on Ubuntu

```bash
cd /home/user
git clone https://github.com/hunterinvariants/orderflow-integrator.git
cd orderflow-integrator
docker compose up --build
```

If the Ubuntu host only has Compose v1 installed, replace the last line with `docker-compose up --build`.

If you already cloned the repository while it was empty, update that existing
directory after this project has been pushed:

```bash
cd /home/user/orderflow-integrator
git pull origin main
docker-compose up --build
```

## API summary

- `GET /health`
- `GET /ready`
- `GET /v1/integrations`
- `GET /v1/orders`
- `POST /v1/orders`
- `GET /v1/orders/{order_id}`
- `POST /v1/orders/{order_id}/route`
