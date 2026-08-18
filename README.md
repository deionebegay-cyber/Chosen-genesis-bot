
# Chosen Genesis Bot

## Railway environment variables

Required:
- `DISCORD_TOKEN` = your Discord bot token

Recommended while testing:
- `GUILD_ID` = your Discord server ID, so slash commands sync immediately

For persistent SQLite storage on Railway:
1. Add a Railway Volume mounted at `/data`
2. Add:
   - `DATA_PATH=/data/genesis.db`

## Commands
- `/sale`
- `/appointment`
- `/kpi`
- `/leaderboard`
- `/stats`
- `/badge`

The bot expects these channel names:
- `main-chat`
- `leaderboard`
- `daily-kpis`
