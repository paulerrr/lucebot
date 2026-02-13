# Lucebot

Lucebot is a Discord bot for Roman Catholic servers that posts daily Mass readings and saint quotes.

## Features

- Automatically posts Mass readings every day at 7:00 AM EST
- Daily saint quote (random from 1,866 quotes by 224 Catholic saints)
- `!readings` command for on-demand readings
- `!quote` command for on-demand saint quotes

## Setup

1. Copy `.env.example` to `.env` and fill in your values:

   ```
   DISCORD_TOKEN=your-bot-token-here
   DISCORD_CHANNEL_ID=your-channel-id-here
   DISCORD_QUOTE_CHANNEL_ID=your-quote-channel-id-here
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

2. Clone the [saint-quotes](https://github.com/paulerrr/saint-quotes) library into the project directory:

   ```bash
   git clone --depth 1 https://github.com/paulerrr/saint-quotes.git /tmp/saint-quotes
   cp /tmp/saint-quotes/saint_quotes.py /tmp/saint-quotes/saint_quotes.db ./
   rm -rf /tmp/saint-quotes
   ```

3. Run the bot:

   ```bash
   python bot.py
   ```

## Discord Bot Permissions

The bot requires the **Message Content** privileged intent enabled in the [Discord Developer Portal](https://discord.com/developers/applications).
