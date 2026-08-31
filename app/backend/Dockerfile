FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY app/backend/requirements.txt /tmp/req.txt
RUN pip install --no-cache-dir -r /tmp/req.txt

COPY odata_1c /app/odata_1c
COPY app/backend /app/app/backend
RUN mkdir -p /app/data

ENV DB_URL=sqlite+aiosqlite:////app/data/app.db \
    PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.backend.main:app", \
     "--host", "0.0.0.0", "--port", "8000"]
