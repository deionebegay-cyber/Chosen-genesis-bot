Chosen Genesis Bot V2

Automated badges:
Daily: First Blood, Ghost Hunter, Point Man, Bounty Hunter, Same Day Savage, Speed Demon, Sale, 2 Spot, Hattrick.
Ties for Point Man/Bounty Hunter/Same Day Savage/Speed Demon share the badge until someone pulls ahead.
Streaks: Hot Streak = appointment 5 consecutive workdays; Ice Cold = sale 3 consecutive workdays. Sunday is skipped.
Weekly: Setter King = most appointments in the completed week; Closer King = most closer sales. Assigned automatically on Monday.

Recommended Railway vars:
TIMEZONE=America/Phoenix
For persistent data, mount a Railway Volume at /data and set DATA_PATH=/data/genesis.db


## Version 3
Adds `/editstats`.

Only Discord members with a role named exactly `Manager` can use it.

Fields:
- Member
- Stat
- Action: Add / Remove / Set
- Amount

The command never allows a value below zero and refreshes leaderboard/badges after corrections.
