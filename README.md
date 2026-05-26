# Lucebot — Moderation Edition

A Discord moderation bot for Roman Catholic servers.

## Features

- **Purgatory verification** — new members are held in a restricted channel until a mod verifies them
- **Moderation logging** — configurable per-category log channels for messages, members, and joins/leaves
- **Reaction roles** — emoji-to-role mapping via slash commands
- **Web admin UI** — manage all configuration and secrets from a browser
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
   WEBUI_PASSWORD=admin                           # change this
   ```

2. Run with Docker Compose:

   ```bash
   docker compose up -d --build
   ```

   This starts both the bot and the web UI. The admin panel is available at `http://localhost:8765`.

### Running without Docker

```bash
pip install -r requirements.txt

# Start the bot
python bot.py

# Start the admin UI (separate terminal)
python webui.py
```

## Admin Web UI

The web UI runs on port `8765` (override with `WEBUI_PORT` in `.env`) and lets you manage everything without editing files by hand.

| Section | What you can manage |
|---|---|
| **Secrets** | Discord token, Guild ID, channel/role ID overrides, web UI password |
| **Log Channels** | Join/leave, message, and member log channel IDs |
| **Purgatory** | Purgatory channel and role IDs |
| **Blocked Users** | Add/remove users blocked from `!compliment` and `!insult` |
| **Social Messages** | Edit the compliment and insult message pools |
| **Reaction Roles** | Read-only view of configured reaction role messages |

The default password is `admin` — change it immediately under **Secrets → Web UI Password**.

> **Note:** Changes to secrets (`.env`) and most config values require a bot restart to take effect. Social messages can be reloaded without a restart using `!reload_messages` in Discord.

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

Config is saved to `config.json` and persists across restarts. You can also set IDs in `.env` or via the web UI.

## Moderation Logging

Log events are split into three categories, each with its own configurable channel. Any category without a dedicated channel falls back to the join/leave channel.

| Category | Events logged |
|---|---|
| **join** | Member joined, member left |
| **message** | Message deleted, message edited, bulk purge, invite links posted |
| **member** | Role added/removed, nickname changed, username changed, timed out, timeout removed, banned, unbanned |

Set channels with `/set-log-channel` (requires **Manage Server**) or via the web UI:

```
/set-log-channel log_type:join/leave    channel:#join-log
/set-log-channel log_type:message       channel:#message-log
/set-log-channel log_type:member        channel:#member-log
```

To route everything to one channel, only set the `join/leave` channel — the others will fall back to it.

Message content is persisted to `data/messages.db` (SQLite) as messages arrive, so delete and edit logs work even for messages that have scrolled out of Discord's memory cache. The only messages that can't be recovered are those sent before the bot was first deployed.

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

Message lists are stored in `data/social_interactions/compliments.md` and `data/social_interactions/insults.md` and can be edited from the web UI. Blocked users are persisted in `data/social_interactions/blocked_users.json`.

## Discord Bot Permissions

Enable the following in the [Discord Developer Portal](https://discord.com/developers/applications):

- **Message Content** privileged intent
- **Server Members** privileged intent

The bot needs the following permissions:

- **Manage Roles** — to assign/remove the Purgatory role (must be positioned above it in the role list)
- **View Audit Log** — recommended so ban/kick events include the responsible moderator
- **Read Message History** — required to fetch messages in reaction role commands
