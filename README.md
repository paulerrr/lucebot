# Lucebot

Lucebot is a Discord bot for Roman Catholic servers that posts daily Mass readings, saint quotes, and the saint/feast of the day.

## Features

- Automatically posts Mass readings every day at 7:00 AM EST
- Supports Novus Ordo (USCCB) or 1962 Traditional Latin Mass (TLM) readings via `READINGS_TYPE` env var
- Daily saint quote (random from 1,866 quotes by 224 Catholic saints)
- Saint/feast of the day from the liturgical calendar (skips ordinary weekdays)
- `!readings` command for on-demand readings
- `!latin` command for on-demand Traditional Latin Mass readings
- `!quote` command for on-demand saint quotes
- `!saint` command for on-demand saint/feast of the day
- Bible verse lookup — type a reference like `John 3:16` or `Gen 1:1-3` and the bot replies with the verse(s) from the Knox Bible translation
- `/search` slash command to search the Knox Bible by keyword or phrase
- Purgatory verification system — new members are held in a restricted channel until a mod verifies them

## Setup

1. Copy `.env.example` to `.env` and fill in your values:

   ```
   DISCORD_TOKEN=your-bot-token-here
   DISCORD_CHANNEL_ID=your-channel-id-here
   DISCORD_QUOTE_CHANNEL_ID=your-quote-channel-id-here
   DISCORD_SAINT_CHANNEL_ID=your-saint-channel-id-here
   READINGS_TYPE=novus_ordo  # or "latin" for Traditional Latin Mass
   ```

   `DISCORD_QUOTE_CHANNEL_ID`, `DISCORD_SAINT_CHANNEL_ID`, and the purgatory variables are all optional.

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

## Purgatory Verification

When a new member joins, the bot automatically assigns them the **Purgatory** role, which restricts them to a single `#purgatory` channel. The bot pings them there with three verification questions:

1. Are you Catholic?
2. Are you 18 years old or older?
3. Who is the current pope?

Once answered, they ping a mod for manual review and role removal.

### Setting up purgatory

Run the `/purgatory-setup` slash command in your server (requires **Manage Server** permission). The bot will:

- Create a **Purgatory** role (or use one you specify)
- Create a **#purgatory** channel (or use one you specify)
- Automatically configure channel permissions — denying the Purgatory role access to all other channels

```
/purgatory-setup                          # creates role and channel automatically
/purgatory-setup role:@Purgatory          # use an existing role
/purgatory-setup channel:#purgatory       # use an existing channel
/purgatory-setup role:@Purgatory channel:#purgatory
```

Config is saved to `config.json` and persists across restarts. Alternatively, you can skip the slash command and set the IDs directly in `.env`:

```
DISCORD_PURGATORY_CHANNEL_ID=your-channel-id-here
DISCORD_PURGATORY_ROLE_ID=your-role-id-here
```

> **Docker note:** mount `config.json` as a volume to preserve purgatory config across container rebuilds:
> ```yaml
> volumes:
>   - ./config.json:/app/config.json
> ```

## Discord Bot Permissions

The bot requires the following enabled in the [Discord Developer Portal](https://discord.com/developers/applications):

- **Message Content** privileged intent
- **Server Members** privileged intent (required for purgatory / `on_member_join`)

The bot also needs **Manage Roles** permission in the server, and its role must be positioned **above** the Purgatory role in the role list.
