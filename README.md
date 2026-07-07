# Lucebot

Lucebot is a Discord bot for Roman Catholic servers that posts daily Mass readings, saint quotes, and the saint/feast of the day.

## Features

- Automatically posts Mass readings every day at 7:00 AM US Eastern
- Supports Novus Ordo (USCCB) or 1962 Traditional Latin Mass (TLM) readings via `READINGS_TYPE` env var
- Daily saint quote (random from 1,866 quotes by 224 Catholic saints)
- Saint of the day with the full biography from [Vatican News](https://www.vaticannews.va/en/saints.html)
- `!readings` command for on-demand readings
- `!latin` command for on-demand Traditional Latin Mass readings
- `!quote` command for on-demand saint quotes
- `!saint` command for on-demand saint/feast of the day
- Bible verse lookup — type a reference like `John 3:16` or `Gen 1:1-3` and the bot replies with the verse(s) in your preferred translation
- Five translations supported: Knox Bible (default), Douay-Rheims, RSV Catholic Edition, New American Bible Revised Edition (NABRE), and Clementine Vulgate (Latin)
- `/set-translation` slash command to set your preferred translation
- Append `[vul]`, `[dr]`, `[rsvce]`, `[nabre]`, or `[knox]` to any reference to override your preference inline (e.g. `John 3:16 [nabre]`)
- `/search` slash command to search the Bible by keyword or phrase
- Purgatory verification system — new members are held in a restricted channel until a mod verifies them
- `!verify @member` command (and `/verify` slash command) to remove the Purgatory role and grant server access
- `!compliment [@member]` — sends a random compliment to the mentioned member (or yourself if omitted)
- `!insult [@member]` — sends a random playful insult to the mentioned member (or yourself if omitted)
- Spam name auto-ban — new members with spammy usernames (keyword matches or dot-obfuscated names like `.TEENS .MEGA ..LINKS S.ELLER`) are automatically banned and logged

## Setup

1. Copy `.env.example` to `.env` and fill in your values:

   ```
   DISCORD_TOKEN=your-bot-token-here
   DISCORD_CHANNEL_ID=your-channel-id-here
   DISCORD_QUOTE_CHANNEL_ID=your-quote-channel-id-here
   DISCORD_SAINT_CHANNEL_ID=your-saint-channel-id-here
   DISCORD_LOG_CHANNEL_ID=your-log-channel-id-here
   READINGS_TYPE=novus_ordo  # or "latin" for Traditional Latin Mass
   ```

   `DISCORD_QUOTE_CHANNEL_ID`, `DISCORD_SAINT_CHANNEL_ID`, `DISCORD_LOG_CHANNEL_ID`, and the purgatory variables are all optional.

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

## Member Join/Leave Logging

When a member joins or leaves, the bot posts an embed to the configured log channel.

- **Join embed**: member mention, account creation date, new member count
- **Leave embed**: member mention, roles held at the time of leaving, new member count

Set the log channel via env var or slash command:

```
DISCORD_LOG_CHANNEL_ID=your-channel-id-here
```

```
/set-log-channel channel:#mod-log
```

The slash command saves to `config.json` and takes effect immediately. The env var takes precedence if both are set.

## Purgatory Verification

When a new member joins, the bot automatically assigns them the **Purgatory** role, which restricts them to a single `#purgatory` channel. The bot pings them there with six verification questions:

1. Are you Catholic or enquiring? If not, what denomination or religion?
2. Are you 18 years old or older?
3. Do you disagree with any traditional Church teachings?
4. Are you sedevacantist?
5. What is your opinion on the SSPX?
6. Do you want a rosary or prayer ping?

Once answered, they ping a mod for manual review and role removal using `!verify @member` or `/verify @member`.

Members who have not posted any message in `#purgatory` within **3 days** of joining are automatically kicked. The bot checks every hour and logs the kick to the configured log channel if one is set.

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

## Spam Name Auto-Ban

When a new member joins, their username and display name are checked against a spam filter. A match causes an immediate ban and a log entry (if a log channel is configured) — the member never gets a chance to post.

A name is flagged if either:

- It contains a keyword from the blocklist (case-insensitive substring match), or
- It has an obfuscated dot pattern typical of spam bots (e.g. `.TEENS .MEGA ..LINKS S.ELLER`) — 3+ periods with a high period-to-length ratio across 3+ tokens.

**Admin commands** (requires Ban Members permission):

| Command | Description |
|---|---|
| `/spam-filter-add keyword:` | Add a keyword to the blocklist |
| `/spam-filter-remove keyword:` | Remove a keyword from the blocklist |
| `/spam-filter-list` | Show all configured keywords |
| `/spam-filter-test name:` | Check whether a given name would be auto-banned, without banning anyone |

The keyword list starts with a built-in default set and is persisted to `config.json`, so additions/removals survive restarts.

## Social Interactions

`!compliment` and `!insult` send a random message to the mentioned member (or the caller if no mention). Messages cycle through the full pool before repeating, with a separate shuffle per guild.

**Admin commands** (requires Administrator permission):

| Command | Description |
|---|---|
| `!blockuser @member` | Prevent a member from using `!compliment` and `!insult` |
| `!unblockuser @member` | Remove the block |
| `!listblockedusers` | Show all currently blocked members |
| `!reload_messages` | Hot-reload compliment/insult files without restarting |

Message lists are stored in `data/social_interactions/compliments.md` and `data/social_interactions/insults.md`. Blocked users are persisted in `data/social_interactions/blocked_users.json` (mounted as a Docker volume).

## Discord Bot Permissions

The bot requires the following enabled in the [Discord Developer Portal](https://discord.com/developers/applications):

- **Message Content** privileged intent
- **Server Members** privileged intent (required for purgatory / `on_member_join`)

The bot also needs **Manage Roles** permission in the server, and its role must be positioned **above** the Purgatory role in the role list. **Ban Members** permission is required for the spam name auto-ban filter.
