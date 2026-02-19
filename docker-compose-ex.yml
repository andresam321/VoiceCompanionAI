version: "3.9"

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: example_user
      POSTGRES_PASSWORD: example_password
      POSTGRES_DB: companion
    volumes:
      - pgdata:/var/lib/postgresql/data

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    env_file:
      - .env.example
    depends_on:
      - postgres
    command: uvicorn api.app.main:app --host 0.0.0.0 --port 8000

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    env_file:
      - .env.example
    depends_on:
      - postgres
    command: python -m worker.main

volumes:
  pgdata:
