FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py readings.py latin_readings.py quotes.py saints.py bible.py config.py saint_quotes.py saint_quotes.db ./
COPY bibles/ ./bibles/

CMD ["python", "bot.py"]
