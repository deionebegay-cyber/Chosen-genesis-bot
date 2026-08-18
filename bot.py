import os
import sqlite3
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
DATA_PATH = os.getenv("DATA_PATH", "genesis.db")
GUILD_ID = os.getenv("GUILD_ID")  # optional; makes slash commands appear immediately while testing

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

def db():
    conn = sqlite3.connect(DATA_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def setup_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS stats (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        sales INTEGER NOT NULL DEFAULT 0,
        appointments INTEGER NOT NULL DEFAULT 0,
        doors INTEGER NOT NULL DEFAULT 0,
        pitches INTEGER NOT NULL DEFAULT 0,
        hours REAL NOT NULL DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS badges (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        badge TEXT NOT NULL,
        awarded_at TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()

def add_stat(guild_id: int, user_id: int, field: str, amount):
    allowed = {"sales", "appointments", "doors", "pitches", "hours"}
    if field not in allowed:
        raise ValueError("Invalid stat field")

    conn = db()
    conn.execute(
        "INSERT OR IGNORE INTO stats (guild_id, user_id) VALUES (?, ?)",
        (guild_id, user_id),
    )
    conn.execute(
        f"UPDATE stats SET {field} = {field} + ? WHERE guild_id = ? AND user_id = ?",
        (amount, guild_id, user_id),
    )
    conn.commit()
    conn.close()

def get_stats(guild_id: int, user_id: int):
    conn = db()
    row = conn.execute(
        "SELECT * FROM stats WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()
    conn.close()
    return row

def leaderboard_rows(guild_id: int, field: str, limit: int = 10):
    allowed = {"sales", "appointments", "doors", "pitches", "hours"}
    if field not in allowed:
        raise ValueError("Invalid leaderboard field")

    conn = db()
    rows = conn.execute(
        f"SELECT user_id, {field} AS value FROM stats "
        f"WHERE guild_id = ? ORDER BY {field} DESC LIMIT ?",
        (guild_id, limit),
    ).fetchall()
    conn.close()
    return rows

async def find_text_channel(guild: discord.Guild, name: str):
    return discord.utils.get(guild.text_channels, name=name)

async def send_main_chat(guild: discord.Guild, content=None, embed=None):
    channel = await find_text_channel(guild, "main-chat")
    if channel:
        await channel.send(content=content, embed=embed)

async def refresh_leaderboard_channel(guild: discord.Guild):
    channel = await find_text_channel(guild, "leaderboard")
    if not channel:
        return

    sales = leaderboard_rows(guild.id, "sales", 10)
    appts = leaderboard_rows(guild.id, "appointments", 10)
    doors = leaderboard_rows(guild.id, "doors", 10)

    def format_rows(rows):
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, row in enumerate(rows):
            member = guild.get_member(row["user_id"])
            name = member.display_name if member else f"<@{row['user_id']}>"
            prefix = medals[i] if i < 3 else f"**{i+1}.**"
            lines.append(f"{prefix} {name} — **{row['value']}**")
        return "\n".join(lines) if lines else "No stats yet."

    embed = discord.Embed(
        title="🏆 Chosen Genesis Leaderboard",
        description="Current all-time totals",
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="💰 Sales", value=format_rows(sales), inline=False)
    embed.add_field(name="📅 Appointments", value=format_rows(appts), inline=False)
    embed.add_field(name="🚪 Doors", value=format_rows(doors), inline=False)

    # Keep the channel clean: update the bot's latest leaderboard if possible.
    async for msg in channel.history(limit=25):
        if msg.author.id == bot.user.id and msg.embeds and msg.embeds[0].title == "🏆 Chosen Genesis Leaderboard":
            await msg.edit(embed=embed)
            return
    await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

class GenesisBot(commands.Bot):
    async def setup_hook(self):
        setup_db()
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to test guild {GUILD_ID}")
        else:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} global commands")

bot = GenesisBot(command_prefix="!", intents=intents)

@bot.tree.command(name="sale", description="Log a new sale")
@app_commands.describe(setter="Setter on the deal", closer="Closer on the deal", utility="APS, SRP, etc.")
async def sale(
    interaction: discord.Interaction,
    setter: discord.Member,
    closer: discord.Member,
    utility: str = "Unknown",
):
    if not interaction.guild:
        return await interaction.response.send_message("Use this command inside the server.", ephemeral=True)

    add_stat(interaction.guild.id, setter.id, "sales", 1)

    embed = discord.Embed(
        title="🚨 NEW SALE",
        description="**CHOSEN GENESIS +1** 🔥",
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="🔥 Setter", value=setter.mention, inline=True)
    embed.add_field(name="🤝 Closer", value=closer.mention, inline=True)
    embed.add_field(name="⚡ Utility", value=utility.upper(), inline=True)

    await interaction.response.send_message("Sale logged ✅", ephemeral=True)
    await send_main_chat(interaction.guild, embed=embed)
    await refresh_leaderboard_channel(interaction.guild)

@bot.tree.command(name="appointment", description="Log a new appointment")
@app_commands.describe(setter="Who set it", same_day="Was it scheduled for the same day?")
async def appointment(
    interaction: discord.Interaction,
    setter: discord.Member,
    same_day: bool = False,
):
    if not interaction.guild:
        return await interaction.response.send_message("Use this command inside the server.", ephemeral=True)

    add_stat(interaction.guild.id, setter.id, "appointments", 1)
    row = get_stats(interaction.guild.id, setter.id)
    total = row["appointments"] if row else 1

    embed = discord.Embed(
        title="📅 NEW APPOINTMENT",
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Setter", value=setter.mention, inline=True)
    embed.add_field(name="Same Day", value="🔥 YES" if same_day else "No", inline=True)
    embed.add_field(name="Total Logged", value=str(total), inline=True)

    await interaction.response.send_message("Appointment logged ✅", ephemeral=True)
    await send_main_chat(interaction.guild, embed=embed)
    await refresh_leaderboard_channel(interaction.guild)

@bot.tree.command(name="kpi", description="Log today's KPI activity")
@app_commands.describe(
    doors="Doors knocked",
    pitches="Pitches given",
    appointments="Appointments set",
    hours="Hours worked",
)
async def kpi(
    interaction: discord.Interaction,
    doors: int,
    pitches: int,
    appointments: int,
    hours: float,
):
    if not interaction.guild:
        return await interaction.response.send_message("Use this command inside the server.", ephemeral=True)

    uid = interaction.user.id
    gid = interaction.guild.id

    add_stat(gid, uid, "doors", doors)
    add_stat(gid, uid, "pitches", pitches)
    add_stat(gid, uid, "appointments", appointments)
    add_stat(gid, uid, "hours", hours)

    pitch_rate = (pitches / doors * 100) if doors else 0
    appt_rate = (appointments / pitches * 100) if pitches else 0
    dph = (doors / hours) if hours else 0

    embed = discord.Embed(
        title=f"📊 KPI — {interaction.user.display_name}",
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="🚪 Doors", value=str(doors), inline=True)
    embed.add_field(name="🗣️ Pitches", value=str(pitches), inline=True)
    embed.add_field(name="📅 Appts", value=str(appointments), inline=True)
    embed.add_field(name="⏱️ Hours", value=f"{hours:g}", inline=True)
    embed.add_field(name="Pitch Rate", value=f"{pitch_rate:.1f}%", inline=True)
    embed.add_field(name="Appt / Pitch", value=f"{appt_rate:.1f}%", inline=True)
    embed.add_field(name="Doors / Hr", value=f"{dph:.1f}", inline=True)

    await interaction.response.send_message("KPIs logged ✅", ephemeral=True)

    channel = await find_text_channel(interaction.guild, "daily-kpis")
    if channel:
        await channel.send(embed=embed)
    await refresh_leaderboard_channel(interaction.guild)

@bot.tree.command(name="leaderboard", description="Show the current Genesis leaderboard")
async def leaderboard(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Use this command inside the server.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    await refresh_leaderboard_channel(interaction.guild)
    await interaction.followup.send("Leaderboard updated ✅", ephemeral=True)

@bot.tree.command(name="stats", description="See a rep's current stats")
async def stats(interaction: discord.Interaction, member: discord.Member | None = None):
    if not interaction.guild:
        return await interaction.response.send_message("Use this command inside the server.", ephemeral=True)

    member = member or interaction.user
    row = get_stats(interaction.guild.id, member.id)

    if not row:
        return await interaction.response.send_message(f"No stats logged yet for {member.mention}.", ephemeral=True)

    embed = discord.Embed(title=f"📈 {member.display_name}'s Stats")
    embed.add_field(name="Sales", value=row["sales"], inline=True)
    embed.add_field(name="Appointments", value=row["appointments"], inline=True)
    embed.add_field(name="Doors", value=row["doors"], inline=True)
    embed.add_field(name="Pitches", value=row["pitches"], inline=True)
    embed.add_field(name="Hours", value=f"{row['hours']:g}", inline=True)

    await interaction.response.send_message(embed=embed)

BADGE_NAMES = {
    "first blood": "🩸 First Blood",
    "ghost hunter": "👻 Ghost Hunter",
    "door champion": "🚪 Door Champion",
    "point man": "🎯 Point Man",
    "night owl": "🦉 Night Owl",
    "game ball": "🏈 Game Ball",
}

@bot.tree.command(name="badge", description="Award a Genesis badge (Manage Roles required)")
@app_commands.checks.has_permissions(manage_roles=True)
async def badge(interaction: discord.Interaction, member: discord.Member, badge_name: str):
    if not interaction.guild:
        return await interaction.response.send_message("Use this command inside the server.", ephemeral=True)

    display = BADGE_NAMES.get(badge_name.lower(), f"🏅 {badge_name.title()}")

    role = discord.utils.get(interaction.guild.roles, name=display)
    if role is None:
        role = await interaction.guild.create_role(name=display, reason="Genesis badge")

    try:
        await member.add_roles(role, reason=f"Badge awarded by {interaction.user}")
    except discord.Forbidden:
        return await interaction.response.send_message(
            "I can't assign that role yet. Move the CG BOT role above the badge roles in Server Settings → Roles.",
            ephemeral=True,
        )

    conn = db()
    conn.execute(
        "INSERT INTO badges (guild_id, user_id, badge, awarded_at) VALUES (?, ?, ?, ?)",
        (interaction.guild.id, member.id, display, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()

    await interaction.response.send_message(f"Awarded **{display}** to {member.mention} ✅")
    await send_main_chat(interaction.guild, content=f"🏅 {member.mention} earned **{display}**!")

@badge.error
async def badge_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You need **Manage Roles** to award badges.", ephemeral=True)
    else:
        raise error

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN environment variable is missing.")

bot.run(TOKEN)