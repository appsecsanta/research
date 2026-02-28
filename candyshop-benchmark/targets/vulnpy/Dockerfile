# VulnPy — Deliberately vulnerable Python/Flask application
FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir vulnpy[flask]

EXPOSE 5050
CMD ["python", "-m", "vulnpy.flask", "--host", "0.0.0.0", "--port", "5050"]
