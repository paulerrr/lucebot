# Lucebot

Lucebot is a Discord bot for Roman Catholic servers that posts daily Mass readings from the USCCB website.

## Features

- Automatically posts readings every day at 7:00 AM EST
- `!readings` command for on-demand fetching

## Setup

1. Copy `.env.example` to `.env` and fill in your values:

   ```
   DISCORD_TOKEN=your-bot-token-here
   DISCORD_CHANNEL_ID=your-channel-id-here
   ```

2. Run the bot with Docker Compose:

   ```bash
   docker compose up -d --build
   ```

### Running without Docker

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Run the bot:

   ```bash
   python bot.py
   ```

## Discord Bot Permissions

The bot requires the **Message Content** privileged intent enabled in the [Discord Developer Portal](https://discord.com/developers/applications).
