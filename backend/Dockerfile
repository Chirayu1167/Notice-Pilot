# NoticePilot GST — backend API (FastAPI)
FROM python:3.12-slim

WORKDIR /srv/app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# SQLite + uploaded files live here; mount a volume to persist them.
ENV NOTICE_PILOT_STORAGE=/srv/data
VOLUME /srv/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
