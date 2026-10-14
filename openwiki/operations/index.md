# Files

- [Environment variables per service](environment-variables.md) - Configuration surface of the Dalgo backend, webapp, prefect-proxy, ai-llm-service and docker compose, grouped by purpose, with which component reads each variable and what breaks when it is missing. Names and purposes only, no values.
- [Local services and external dependencies](local-services-and-dependencies.md) - Which processes must run for a working Dalgo dev stack (Postgres, Redis, Airbyte, Prefect server, prefect-proxy, Celery workers and beat, ai-llm-service) and which external systems the code talks to (Airbyte, Prefect, LLM providers, Langfuse, Sentry, PostHog, AWS SES/S3/Secrets Manager, Superset), with how each is wired and how it fails.
