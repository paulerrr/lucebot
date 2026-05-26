FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py config.py message_store.py social_interactions.py webui.py ./
COPY data/ ./data/

CMD ["python", "bot.py"]
