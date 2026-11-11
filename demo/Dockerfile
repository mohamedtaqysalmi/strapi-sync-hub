FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY demo/mapping.yaml ./demo/mapping.yaml
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "--factory", "strapi_sync_hub.main:create_app_from_env", "--host", "0.0.0.0", "--port", "8000"]
