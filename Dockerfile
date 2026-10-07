FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Don't run the app as root. climber_profiles/ is the SQLite fallback path,
# so it has to be writable by that user when no hosted database is set.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/climber_profiles \
    && chown -R app:app /app
USER app

EXPOSE 8501

HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
