FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py config.py leveling.py message_store.py modwarnings.py social_interactions.py webui.py ./
COPY entrypoint.sh ./
COPY data/ ./data/
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "bot.py"]
