FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY voice_receptionist /app/voice_receptionist
COPY apps /app/apps
COPY static /app/static
COPY public /app/public
COPY scripts /app/scripts
COPY manage.py /app/manage.py
COPY app.py /app/app.py

ENV PORT=8000
EXPOSE 8000

RUN addgroup --system app && adduser --system --ingroup app --home /app app \
    && mkdir -p /app/data && chown -R app:app /app
USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["python", "app.py"]
