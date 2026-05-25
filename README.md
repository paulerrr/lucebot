# Lucebot — Moderation Edition

A Discord moderation bot for Roman Catholic servers.

## Features

- **Purgatory verification** — new members are held in a restricted channel until a mod verifies them
- **Member join/leave logging** — embeds posted to a configurable log channel
- **Reaction roles** — emoji-to-role mapping via slash commands
- `!compliment [@member]` — sends a random compliment to the mentioned member (or yourself if omitted)
- `!insult [@member]` — sends a random playful insult to the mentioned member (or yourself if omitted)

## Setup

1. Copy `.env.example` to `.env` and fill in your values:

   ```
   DISCORD_TOKEN=your-bot-token-here
   DISCORD_GUILD_ID=your-guild-id-here          # optional, speeds up slash command sync
   DISCORD_PURGATORY_CHANNEL_ID=your-channel-id  # optional if using /purgatory-setup
   DISCORD_PURGATORY_ROLE_ID=your-role-id        # optional if using /purgatory-setup
   DISCORD_LOG_CHANNEL_ID=your-channel-id        # optional if using /set-log-channel
   ```

2. Run with Docker Compose:

   ```bash
   docker compose up -d --build
   ```

### Running without Docker

```bash
pip install -r requirements.txt
python bot.py
```

## Purgatory Verification

When a new member joins, the bot automatically assigns them the **Purgatory** role, restricting them to a single `#purgatory` channel. The bot pings them there with verification questions:

1. Are you Catholic or enquiring? If not, what denomination or religion?
2. Are you 18 years old or older?
3. Do you disagree with any traditional Church teachings?
4. Are you sedevacantist?
5. Do you want a rosary or prayer ping?

Once answered, they ping a mod for manual review and role removal using `!verify @member` or `/verify @member`.

### Setting up purgatory

Run `/purgatory-setup` in your server (requires **Manage Server** permission):

```
/purgatory-setup                          # creates role and channel automatically
/purgatory-setup role:@Purgatory          # use an existing role
/purgatory-setup channel:#purgatory       # use an existing channel
/purgatory-setup role:@Purgatory channel:#purgatory
```

Config is saved to `config.json` and persists across restarts. You can also set IDs directly in `.env`:

```
DISCORD_PURGATORY_CHANNEL_ID=your-channel-id-here
DISCORD_PURGATORY_ROLE_ID=your-role-id-here
```

> **Docker note:** mount `config.json` as a volume to preserve config across container rebuilds:
> ```yaml
> volumes:
>   - ./config.json:/app/config.json
> ```

## Member Join/Leave Logging

When a member joins or leaves, the bot posts an embed to the configured log channel.

- **Join embed**: member mention, account creation date, new member count
- **Leave embed**: member mention, roles held at the time of leaving, new member count

Set the log channel via slash command or env var:

```
/set-log-channel channel:#mod-log
```

```
DISCORD_LOG_CHANNEL_ID=your-channel-id-here
```

## Reaction Roles

| Command | Description |
|---|---|
| `/reaction-role-setup` | Post a new reaction role embed in a channel (up to 5 emoji→role pairs) |
| `/reaction-role-add` | Add more pairs to an existing reaction role message |
| `/reaction-role-list` | List all configured reaction role messages |
| `/reaction-role-remove` | Delete a reaction role message and remove its config |

## Social Interactions

`!compliment` and `!insult` send a random message to the mentioned member (or the caller if no mention). Messages cycle through the full pool before repeating, with a separate shuffle per guild.

**Admin commands** (requires Administrator permission):

| Command | Description |
|---|---|
| `!blockuser @member` | Prevent a member from using `!compliment` and `!insult` |
| `!unblockuser @member` | Remove the block |
| `!listblockedusers` | Show all currently blocked members |
| `!reload_messages` | Hot-reload compliment/insult files without restarting |

Message lists are stored in `data/social_interactions/compliments.md` and `data/social_interactions/insults.md`. Blocked users are persisted in `data/social_interactions/blocked_users.json`.

## Discord Bot Permissions

Enable the following in the [Discord Developer Portal](https://discord.com/developers/applications):

- **Message Content** privileged intent
- **Server Members** privileged intent

The bot also needs **Manage Roles** permission, and its role must be positioned **above** the Purgatory role in the role list.
