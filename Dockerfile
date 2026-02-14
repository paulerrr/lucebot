FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN git clone --depth 1 https://github.com/paulerrr/saint-quotes.git /tmp/saint-quotes && \
    cp /tmp/saint-quotes/saint_quotes.py /tmp/saint-quotes/saint_quotes.db ./ && \
    rm -rf /tmp/saint-quotes

COPY bot.py readings.py latin_readings.py quotes.py saints.py bible.py knox.json ./

CMD ["python", "bot.py"]
