FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd --system --uid 10001 --create-home --shell /usr/sbin/nologin atlas

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=atlas:atlas app.py ./
COPY --chown=atlas:atlas code/ ./code/
COPY --chown=atlas:atlas database/ ./database/
COPY --chown=atlas:atlas static/ ./static/

USER atlas

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
