FROM python:3.12-slim

RUN groupadd -r app && useradd -r -g app -m -d /app app

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir . && mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import http.client; conn=http.client.HTTPConnection('localhost:8000'); conn.request('GET','/health'); resp=conn.getresponse(); exit(0 if resp.status==200 else 1)"

CMD ["uvicorn", "gw2_progression.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
