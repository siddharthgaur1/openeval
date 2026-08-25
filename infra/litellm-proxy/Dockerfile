FROM ghcr.io/berriai/litellm:main-latest

WORKDIR /app

COPY callback.py litellm_config.yaml ./

CMD ["--config", "/app/litellm_config.yaml", "--port", "4000"]
