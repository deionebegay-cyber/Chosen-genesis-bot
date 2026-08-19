import os, sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import discord
from discord import app_commands
from discord.ext import commands, tasks

TOKEN=os.getenv('DISCORD_TOKEN')
DATA_PATH=os.getenv('DATA_PATH','genesis.db')
GUILD_ID=os.getenv('GUILD_ID')
TZ=ZoneInfo(os.getenv('TIMEZONE','America/Phoenix'))

DAILY=['🩸 First Blood','👻 Ghost Hunter','🎯 Point Man','📄 Bounty Hunter','⚡ Same Day Savage','⏰ Speed Demon','💥 Sale','🥈 2 Spot','🎩 Hattrick']
STREAK=['🔥 Hot Streak','🧊 Ice Cold']
WEEKLY=['👑 Setter King','👑 Closer King']

intents=discord.Intents.default(); intents.members=True; intents.message_content=True

def con():
    c=sqlite3.connect(DATA_PATH); c.row_factory=sqlite3.Row; return c

def setup_db():
    c=con()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS stats(
      guild_id INTEGER,user_id INTEGER,sales INTEGER DEFAULT 0,appointments INTEGER DEFAULT 0,
      pitches INTEGER DEFAULT 0,hours REAL DEFAULT 0,closer_sales INTEGER DEFAULT 0,
      bills INTEGER DEFAULT 0,within_48 INTEGER DEFAULT 0,same_day INTEGER DEFAULT 0,
      PRIMARY KEY(guild_id,user_id));
    CREATE TABLE IF NOT EXISTS appointment_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER,setter_id INTEGER,
      bill_collected INTEGER,within_48 INTEGER,same_day INTEGER,local_date TEXT,week_key TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS sale_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER,setter_id INTEGER,closer_id INTEGER,
      utility TEXT,local_date TEXT,local_hour INTEGER,week_key TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS meta(guild_id INTEGER,key TEXT,value TEXT,PRIMARY KEY(guild_id,key));
    ''')
    # migrate old v1 stats safely
    cols={r['name'] for r in c.execute('PRAGMA table_info(stats)')}
    for name,typ in [('closer_sales','INTEGER DEFAULT 0'),('bills','INTEGER DEFAULT 0'),('within_48','INTEGER DEFAULT 0'),('same_day','INTEGER DEFAULT 0')]:
        if name not in cols: c.execute(f'ALTER TABLE stats ADD COLUMN {name} {typ}')
    c.commit(); c.close()

def now(): return datetime.now(TZ)
def dkey(d=None): return (d or now().date()).isoformat()
def wkey(d=None):
    iso=(d or now().date()).isocalendar(); return f'{iso.year}-W{iso.week:02d}'

def add(g,u,field,n):
    allowed={'sales','appointments','pitches','hours','closer_sales','bills','within_48','same_day'}
    if field not in allowed: return
    c=con(); c.execute('INSERT OR IGNORE INTO stats(guild_id,user_id) VALUES(?,?)',(g,u))
    c.execute(f'UPDATE stats SET {field}={field}+? WHERE guild_id=? AND user_id=?',(n,g,u)); c.commit(); c.close()

def meta_get(g,k):
    c=con(); r=c.execute('SELECT value FROM meta WHERE guild_id=? AND key=?',(g,k)).fetchone(); c.close(); return r['value'] if r else None

def meta_set(g,k,v):
    c=con(); c.execute('INSERT INTO meta VALUES(?,?,?) ON CONFLICT(guild_id,key) DO UPDATE SET value=excluded.value',(g,k,v)); c.commit(); c.close()

async def channel(guild,name): return discord.utils.get(guild.text_channels,name=name)
async def main(guild,content=None,embed=None):
    ch=await channel(guild,'main-chat')
    if ch: await ch.send(content=content,embed=embed)

def is_manager(member):
    return isinstance(member, discord.Member) and any(r.name.lower() == 'manager' for r in member.roles)

async def role(guild,name):
    r=discord.utils.get(guild.roles,name=name)
    if not r: r=await guild.create_role(name=name,reason='Chosen Genesis automated badge')
    return r

async def set_holders(guild,name,ids):
    r=await role(guild,name); ids=set(ids); current={m.id for m in r.members}
    for uid in current-ids:
        m=guild.get_member(uid)
        if m:
            try: await m.remove_roles(r,reason='Badge leader changed')
            except discord.Forbidden: pass
    for uid in ids-current:
        m=guild.get_member(uid)
        if m:
            try: await m.add_roles(r,reason='Earned automated badge')
            except discord.Forbidden: pass

async def add_role(guild,member,name):
    r=await role(guild,name)
    if r not in member.roles:
        try: await member.add_roles(r,reason='Earned automated badge')
        except discord.Forbidden: return False
    return True

async def clear_roles(guild,names):
    for name in names:
        r=discord.utils.get(guild.roles,name=name)
        if r:
            for m in list(r.members):
                try: await m.remove_roles(r,reason='Badge reset')
                except discord.Forbidden: pass

def daily_leaders(g,metric):
    c=con(); today=dkey()
    if metric=='appointments': q='SELECT setter_id user_id,COUNT(*) value FROM appointment_events WHERE guild_id=? AND local_date=? GROUP BY setter_id'
    elif metric=='bills': q='SELECT setter_id user_id,SUM(bill_collected) value FROM appointment_events WHERE guild_id=? AND local_date=? GROUP BY setter_id'
    elif metric=='same_day': q='SELECT setter_id user_id,SUM(same_day) value FROM appointment_events WHERE guild_id=? AND local_date=? GROUP BY setter_id'
    else: q='SELECT setter_id user_id,SUM(within_48) value FROM appointment_events WHERE guild_id=? AND local_date=? GROUP BY setter_id'
    rows=c.execute(q,(g,today)).fetchall(); c.close()
    rows=[r for r in rows if r['value'] and r['value']>0]
    if not rows: return []
    best=max(r['value'] for r in rows)
    return [r['user_id'] for r in rows if r['value']==best]

async def refresh_daily_comp(guild):
    for metric,badge in [('appointments','🎯 Point Man'),('bills','📄 Bounty Hunter'),('same_day','⚡ Same Day Savage'),('within_48','⏰ Speed Demon')]:
        await set_holders(guild,badge,daily_leaders(guild.id,metric))

def closer_sales_today(g,u):
    c=con(); n=c.execute('SELECT COUNT(*) c FROM sale_events WHERE guild_id=? AND closer_id=? AND local_date=?',(g,u,dkey())).fetchone()['c']; c.close(); return n

def first_setter(g):
    c=con(); r=c.execute('SELECT setter_id FROM appointment_events WHERE guild_id=? AND local_date=? ORDER BY id LIMIT 1',(g,dkey())).fetchone(); c.close(); return r['setter_id'] if r else None

def prev_workday(d):
    d-=timedelta(days=1)
    while d.weekday()==6: d-=timedelta(days=1)
    return d

def streak(g,u,table,col,needed):
    c=con(); cur=now().date()
    def has(d): return bool(c.execute(f'SELECT 1 FROM {table} WHERE guild_id=? AND {col}=? AND local_date=? LIMIT 1',(g,u,d.isoformat())).fetchone())
    if cur.weekday()==6 or not has(cur): cur=prev_workday(cur)
    for _ in range(needed):
        if not has(cur): c.close(); return False
        cur=prev_workday(cur)
    c.close(); return True

async def refresh_streaks(guild):
    c=con(); setters=[r['setter_id'] for r in c.execute('SELECT DISTINCT setter_id FROM appointment_events WHERE guild_id=?',(guild.id,))]
    closers=[r['closer_id'] for r in c.execute('SELECT DISTINCT closer_id FROM sale_events WHERE guild_id=?',(guild.id,))]; c.close()
    await set_holders(guild,'🔥 Hot Streak',[u for u in setters if streak(guild.id,u,'appointment_events','setter_id',5)])
    await set_holders(guild,'🧊 Ice Cold',[u for u in closers if streak(guild.id,u,'sale_events','closer_id',3)])

def week_winners(g,wk,kind):
    c=con()
    if kind=='setter': rows=c.execute('SELECT setter_id user_id,COUNT(*) value FROM appointment_events WHERE guild_id=? AND week_key=? GROUP BY setter_id',(g,wk)).fetchall()
    else: rows=c.execute('SELECT closer_id user_id,COUNT(*) value FROM sale_events WHERE guild_id=? AND week_key=? GROUP BY closer_id',(g,wk)).fetchall()
    c.close()
    if not rows: return [],0
    best=max(r['value'] for r in rows); return [r['user_id'] for r in rows if r['value']==best],best

async def weekly_kings(guild):
    if now().weekday()!=0: return
    prev=now().date()-timedelta(days=1); wk=wkey(prev)
    if meta_get(guild.id,'weekly_awarded')==wk: return
    s,sc=week_winners(guild.id,wk,'setter'); c,cc=week_winners(guild.id,wk,'closer')
    await set_holders(guild,'👑 Setter King',s); await set_holders(guild,'👑 Closer King',c)
    if s or c:
        e=discord.Embed(title='👑 WEEKLY KINGS')
        e.add_field(name='👑 Setter King',value=(", ".join(f'<@{x}>' for x in s)+f' — **{sc} appointments**') if s else 'No winner',inline=False)
        e.add_field(name='👑 Closer King',value=(", ".join(f'<@{x}>' for x in c)+f' — **{cc} sales**') if c else 'No winner',inline=False)
        await main(guild,embed=e)
    meta_set(guild.id,'weekly_awarded',wk)

async def restore_daily(guild):
    await clear_roles(guild,DAILY)
    f=first_setter(guild.id)
    if f:
        m=guild.get_member(f)
        if m: await add_role(guild,m,'🩸 First Blood')
    c=con(); rows=c.execute('SELECT closer_id,COUNT(*) c,MAX(local_hour) h FROM sale_events WHERE guild_id=? AND local_date=? GROUP BY closer_id',(guild.id,dkey())).fetchall(); c.close()
    ghosts=[]
    for r in rows:
        m=guild.get_member(r['closer_id'])
        if not m: continue
        if r['c']>=1: await add_role(guild,m,'💥 Sale')
        if r['c']>=2: await add_role(guild,m,'🥈 2 Spot')
        if r['c']>=3: await add_role(guild,m,'🎩 Hattrick')
        if r['h']>=19: ghosts.append(r['closer_id'])
    await set_holders(guild,'👻 Ghost Hunter',ghosts)
    await refresh_daily_comp(guild)

async def refresh_leaderboard(guild):
    ch=await channel(guild,'leaderboard')
    if not ch: return
    c=con()
    def rows(field): return c.execute(f'SELECT user_id,{field} value FROM stats WHERE guild_id=? AND {field}>0 ORDER BY {field} DESC LIMIT 10',(guild.id,)).fetchall()
    a,s,cl=rows('appointments'),rows('sales'),rows('closer_sales'); c.close()
    def fmt(rs):
        medals=['🥇','🥈','🥉']; out=[]
        for i,r in enumerate(rs):
            m=guild.get_member(r['user_id']); n=m.display_name if m else f"<@{r['user_id']}>"; out.append(f"{medals[i] if i<3 else str(i+1)+'.'} {n} — **{r['value']}**")
        return '\n'.join(out) or 'No stats yet.'
    e=discord.Embed(title='🏆 Chosen Genesis Leaderboard',timestamp=datetime.now(timezone.utc))
    e.add_field(name='📅 Appointments',value=fmt(a),inline=False); e.add_field(name='💰 Setter Sales',value=fmt(s),inline=False); e.add_field(name='🤝 Closer Sales',value=fmt(cl),inline=False)
    async for msg in ch.history(limit=25):
        if msg.author.id==bot.user.id and msg.embeds and msg.embeds[0].title=='🏆 Chosen Genesis Leaderboard': await msg.edit(embed=e); return
    await ch.send(embed=e)


PERIOD_CHOICES = [
    app_commands.Choice(name='Today', value='today'),
    app_commands.Choice(name='This Week', value='week'),
    app_commands.Choice(name='This Month', value='month'),
    app_commands.Choice(name='All Time', value='all'),
]

def subtract_stat(g,u,field,n):
    allowed={'sales','appointments','pitches','hours','closer_sales','bills','within_48','same_day'}
    if field not in allowed: return
    c=con()
    c.execute('INSERT OR IGNORE INTO stats(guild_id,user_id) VALUES(?,?)',(g,u))
    c.execute(f'UPDATE stats SET {field}=MAX(0,{field}-?) WHERE guild_id=? AND user_id=?',(n,g,u))
    c.commit(); c.close()

async def recalc_after_event_change(guild):
    await restore_daily(guild)
    await refresh_streaks(guild)
    await refresh_leaderboard(guild)

def period_bounds(period):
    local_now=now()
    today=local_now.date()
    if period=='today':
        return today.isoformat(), today.isoformat(), 'Today'
    if period=='week':
        start=today-timedelta(days=today.weekday())
        return start.isoformat(), today.isoformat(), 'This Week'
    if period=='month':
        start=today.replace(day=1)
        return start.isoformat(), today.isoformat(), local_now.strftime('%B')
    return None,None,'All Time'

def period_rows(guild_id,period,kind):
    start,end,_=period_bounds(period)
    c=con()
    if period=='all':
        field={'appointments':'appointments','setter_sales':'sales','closer_sales':'closer_sales'}[kind]
        rows=c.execute(
            f'SELECT user_id,{field} value FROM stats WHERE guild_id=? AND {field}>0 ORDER BY {field} DESC LIMIT 10',
            (guild_id,)
        ).fetchall()
    elif kind=='appointments':
        rows=c.execute(
            'SELECT setter_id user_id,COUNT(*) value FROM appointment_events '
            'WHERE guild_id=? AND local_date BETWEEN ? AND ? '
            'GROUP BY setter_id ORDER BY value DESC LIMIT 10',
            (guild_id,start,end)
        ).fetchall()
    elif kind=='setter_sales':
        rows=c.execute(
            'SELECT setter_id user_id,COUNT(*) value FROM sale_events '
            'WHERE guild_id=? AND local_date BETWEEN ? AND ? '
            'GROUP BY setter_id ORDER BY value DESC LIMIT 10',
            (guild_id,start,end)
        ).fetchall()
    else:
        rows=c.execute(
            'SELECT closer_id user_id,COUNT(*) value FROM sale_events '
            'WHERE guild_id=? AND local_date BETWEEN ? AND ? '
            'GROUP BY closer_id ORDER BY value DESC LIMIT 10',
            (guild_id,start,end)
        ).fetchall()
    c.close()
    return rows

async def show_period_leaderboard(guild,period='all'):
    ch=await channel(guild,'leaderboard')
    if not ch: return False
    _,_,label=period_bounds(period)
    a=period_rows(guild.id,period,'appointments')
    s=period_rows(guild.id,period,'setter_sales')
    cl=period_rows(guild.id,period,'closer_sales')

    def fmt(rs):
        medals=['🥇','🥈','🥉']; out=[]
        for i,r in enumerate(rs):
            m=guild.get_member(r['user_id'])
            name=m.display_name if m else f"<@{r['user_id']}>"
            prefix=medals[i] if i<3 else f"{i+1}."
            out.append(f"{prefix} {name} — **{r['value']}**")
        return '\n'.join(out) or 'No stats yet.'

    e=discord.Embed(
        title=f'🏆 Chosen Genesis Leaderboard — {label}',
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(name='📅 Appointments',value=fmt(a),inline=False)
    e.add_field(name='💰 Setter Sales',value=fmt(s),inline=False)
    e.add_field(name='🤝 Closer Sales',value=fmt(cl),inline=False)
    await ch.send(embed=e)
    return True

class Genesis(commands.Bot):
    async def setup_hook(self):
        setup_db(); maintenance.start()
        if GUILD_ID:
            g=discord.Object(id=int(GUILD_ID)); self.tree.copy_global_to(guild=g); await self.tree.sync(guild=g)
        else: await self.tree.sync()

bot=Genesis(command_prefix='!',intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    for g in bot.guilds:
        if meta_get(g.id,'daily_date')!=dkey(): meta_set(g.id,'daily_date',dkey())
        await restore_daily(g); await refresh_streaks(g)

@tasks.loop(minutes=2)
async def maintenance():
    for g in bot.guilds:
        if meta_get(g.id,'daily_date')!=dkey():
            await clear_roles(g,DAILY); meta_set(g.id,'daily_date',dkey()); await restore_daily(g)
        await refresh_streaks(g); await weekly_kings(g)

@maintenance.before_loop
async def before_maintenance(): await bot.wait_until_ready()

@bot.tree.command(name='appointment',description='Log a new appointment')
@app_commands.describe(setter='Who set it',bill_collected='Did you collect the electric bill?',within_48_hours='Is it within 48 hours?',same_day='Is it same day?')
async def appointment(interaction:discord.Interaction,setter:discord.Member,bill_collected:bool,within_48_hours:bool,same_day:bool=False):
    if not interaction.guild: return
    n=now(); g=interaction.guild.id
    c=con(); c.execute('INSERT INTO appointment_events(guild_id,setter_id,bill_collected,within_48,same_day,local_date,week_key,created_at) VALUES(?,?,?,?,?,?,?,?)',(g,setter.id,int(bill_collected),int(within_48_hours),int(same_day),dkey(n.date()),wkey(n.date()),datetime.now(timezone.utc).isoformat())); c.commit(); c.close()
    add(g,setter.id,'appointments',1)
    if bill_collected: add(g,setter.id,'bills',1)
    if within_48_hours: add(g,setter.id,'within_48',1)
    if same_day: add(g,setter.id,'same_day',1)
    e=discord.Embed(title='📅 NEW APPOINTMENT',timestamp=datetime.now(timezone.utc)); e.add_field(name='👤 Setter',value=setter.mention,inline=False); e.add_field(name='📄 Bill',value='✅ Collected' if bill_collected else '❌ No'); e.add_field(name='⏰ Within 48 Hours',value='✅ Yes' if within_48_hours else '❌ No'); e.add_field(name='⚡ Same Day',value='✅ Yes' if same_day else '❌ No')
    await interaction.response.send_message('Appointment logged ✅',ephemeral=True); await main(interaction.guild,embed=e)
    if first_setter(g)==setter.id:
        await set_holders(interaction.guild,'🩸 First Blood',[setter.id]); await main(interaction.guild,content=f'🩸 **FIRST BLOOD!** {setter.mention} set the first appointment of the day!')
    await refresh_daily_comp(interaction.guild); await refresh_streaks(interaction.guild); await refresh_leaderboard(interaction.guild)

@bot.tree.command(name='sale',description='Log a new sale')
@app_commands.describe(setter='Setter on the deal',closer='Closer who closed it',utility='APS, SRP, etc.')
async def sale(interaction:discord.Interaction,setter:discord.Member,closer:discord.Member,utility:str='Unknown'):
    if not interaction.guild: return
    n=now(); g=interaction.guild.id
    c=con(); c.execute('INSERT INTO sale_events(guild_id,setter_id,closer_id,utility,local_date,local_hour,week_key,created_at) VALUES(?,?,?,?,?,?,?,?)',(g,setter.id,closer.id,utility,dkey(n.date()),n.hour,wkey(n.date()),datetime.now(timezone.utc).isoformat())); c.commit(); c.close()
    add(g,setter.id,'sales',1); add(g,closer.id,'closer_sales',1)
    e=discord.Embed(title='🚨 NEW SALE',description='**CHOSEN GENESIS +1** 🔥',timestamp=datetime.now(timezone.utc)); e.add_field(name='🔥 Setter',value=setter.mention); e.add_field(name='🤝 Closer',value=closer.mention); e.add_field(name='⚡ Utility',value=utility.upper())
    await interaction.response.send_message('Sale logged ✅',ephemeral=True); await main(interaction.guild,embed=e)
    count=closer_sales_today(g,closer.id)
    if count>=1: await add_role(interaction.guild,closer,'💥 Sale')
    if count==1: await main(interaction.guild,content=f'💥 **SALE BADGE!** {closer.mention} got a sale today!')
    if count>=2: await add_role(interaction.guild,closer,'🥈 2 Spot')
    if count==2: await main(interaction.guild,content=f'🥈 **2 SPOT!** {closer.mention} has **2 sales today!**')
    if count>=3: await add_role(interaction.guild,closer,'🎩 Hattrick')
    if count==3: await main(interaction.guild,content=f'🎩 **HATTRICK!** {closer.mention} has **3 sales today!** 🔥')
    if n.hour>=19:
        await add_role(interaction.guild,closer,'👻 Ghost Hunter'); await main(interaction.guild,content=f'👻 **GHOST HUNTER!** {closer.mention} closed a deal after 7 PM!')
    await refresh_streaks(interaction.guild); await refresh_leaderboard(interaction.guild)

@bot.tree.command(name='kpi',description="Log today's KPI activity")
async def kpi(interaction:discord.Interaction,pitches:int,appointments:int,hours:float):
    if not interaction.guild: return
    add(interaction.guild.id,interaction.user.id,'pitches',pitches); add(interaction.guild.id,interaction.user.id,'hours',hours)
    e=discord.Embed(title=f'📊 KPI — {interaction.user.display_name}',timestamp=datetime.now(timezone.utc)); e.add_field(name='🗣️ Pitches',value=pitches); e.add_field(name='📅 Appointments',value=appointments); e.add_field(name='⏱️ Hours',value=f'{hours:g}'); e.add_field(name='Appt / Pitch',value=f'{(appointments/pitches*100 if pitches else 0):.1f}%'); e.add_field(name='Pitches / Hr',value=f'{(pitches/hours if hours else 0):.1f}'); e.add_field(name='Appts / Hr',value=f'{(appointments/hours if hours else 0):.2f}')
    await interaction.response.send_message('KPIs logged ✅',ephemeral=True); ch=await channel(interaction.guild,'daily-kpis');
    if ch: await ch.send(embed=e)

@bot.tree.command(name='leaderboard',description='Show a leaderboard for a time period')
@app_commands.describe(period='Today, this week, this month, or all time')
@app_commands.choices(period=PERIOD_CHOICES)
async def leaderboard(interaction:discord.Interaction,period:app_commands.Choice[str]|None=None):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    selected=period.value if period else 'all'
    ok=await show_period_leaderboard(interaction.guild,selected)
    if ok:
        await interaction.followup.send('Leaderboard posted ✅',ephemeral=True)
    else:
        await interaction.followup.send('I could not find the **leaderboard** channel.',ephemeral=True)

@bot.tree.command(name='stats',description="See a rep's stats")
async def stats(interaction:discord.Interaction,member:discord.Member|None=None):
    member=member or interaction.user; c=con(); r=c.execute('SELECT * FROM stats WHERE guild_id=? AND user_id=?',(interaction.guild.id,member.id)).fetchone(); c.close()
    if not r: return await interaction.response.send_message('No stats yet.',ephemeral=True)
    a=r['appointments']; e=discord.Embed(title=f"📈 {member.display_name}'s Stats"); e.add_field(name='📅 Appointments',value=a); e.add_field(name='📄 Bills',value=f"{r['bills']} ({(r['bills']/a*100 if a else 0):.0f}%)"); e.add_field(name='⏰ Within 48h',value=f"{r['within_48']} ({(r['within_48']/a*100 if a else 0):.0f}%)"); e.add_field(name='💰 Setter Sales',value=r['sales']); e.add_field(name='🤝 Closer Sales',value=r['closer_sales']); e.add_field(name='🗣️ Pitches',value=r['pitches']); e.add_field(name='⏱️ Hours',value=f"{r['hours']:g}")
    await interaction.response.send_message(embed=e)



UNDO_CHOICES = [
    app_commands.Choice(name='Appointment', value='appointment'),
    app_commands.Choice(name='Sale', value='sale'),
]

@bot.tree.command(name='undo',description='Manager-only: undo an accidental appointment or sale log')
@app_commands.describe(
    log_type='What type of log should be undone?',
    member='Optional: undo the latest log involving this member'
)
@app_commands.choices(log_type=UNDO_CHOICES)
async def undo(
    interaction: discord.Interaction,
    log_type: app_commands.Choice[str],
    member: discord.Member|None=None
):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)

    if not is_manager(interaction.user):
        return await interaction.response.send_message(
            '❌ Only users with the **Manager** role can undo logs.',
            ephemeral=True
        )

    g=interaction.guild.id
    c=con()

    if log_type.value=='appointment':
        if member:
            row=c.execute(
                'SELECT * FROM appointment_events WHERE guild_id=? AND setter_id=? ORDER BY id DESC LIMIT 1',
                (g,member.id)
            ).fetchone()
        else:
            row=c.execute(
                'SELECT * FROM appointment_events WHERE guild_id=? ORDER BY id DESC LIMIT 1',
                (g,)
            ).fetchone()

        if not row:
            c.close()
            return await interaction.response.send_message('No appointment log found to undo.',ephemeral=True)

        c.execute('DELETE FROM appointment_events WHERE id=?',(row['id'],))
        c.commit(); c.close()

        subtract_stat(g,row['setter_id'],'appointments',1)
        if row['bill_collected']: subtract_stat(g,row['setter_id'],'bills',1)
        if row['within_48']: subtract_stat(g,row['setter_id'],'within_48',1)
        if row['same_day']: subtract_stat(g,row['setter_id'],'same_day',1)

        target=interaction.guild.get_member(row['setter_id'])
        target_text=target.mention if target else '<@%s>' % row['setter_id']
        await recalc_after_event_change(interaction.guild)
        return await interaction.response.send_message(
            f'✅ Undid the latest appointment for {target_text}.',
            ephemeral=True
        )

    if member:
        row=c.execute(
            'SELECT * FROM sale_events WHERE guild_id=? AND (setter_id=? OR closer_id=?) ORDER BY id DESC LIMIT 1',
            (g,member.id,member.id)
        ).fetchone()
    else:
        row=c.execute(
            'SELECT * FROM sale_events WHERE guild_id=? ORDER BY id DESC LIMIT 1',
            (g,)
        ).fetchone()

    if not row:
        c.close()
        return await interaction.response.send_message('No sale log found to undo.',ephemeral=True)

    c.execute('DELETE FROM sale_events WHERE id=?',(row['id'],))
    c.commit(); c.close()

    subtract_stat(g,row['setter_id'],'sales',1)
    subtract_stat(g,row['closer_id'],'closer_sales',1)

    setter=interaction.guild.get_member(row['setter_id'])
    closer=interaction.guild.get_member(row['closer_id'])
    setter_text=setter.mention if setter else '<@%s>' % row['setter_id']
    closer_text=closer.mention if closer else '<@%s>' % row['closer_id']

    await recalc_after_event_change(interaction.guild)
    return await interaction.response.send_message(
        f'✅ Undid the latest sale: setter {setter_text}, closer {closer_text}.',
        ephemeral=True
    )

STAT_CHOICES = [
    app_commands.Choice(name='Appointments', value='appointments'),
    app_commands.Choice(name='Bills', value='bills'),
    app_commands.Choice(name='Within 48 Hours', value='within_48'),
    app_commands.Choice(name='Same Day', value='same_day'),
    app_commands.Choice(name='Setter Sales', value='sales'),
    app_commands.Choice(name='Closer Sales', value='closer_sales'),
    app_commands.Choice(name='Pitches', value='pitches'),
    app_commands.Choice(name='Hours', value='hours'),
]

ACTION_CHOICES = [
    app_commands.Choice(name='➕ Add', value='add'),
    app_commands.Choice(name='➖ Remove', value='remove'),
    app_commands.Choice(name='✏️ Set', value='set'),
]

@bot.tree.command(name='editstats',description='Manager-only: add, remove, or set saved totals')
@app_commands.describe(
    member='Member whose stats you want to change',
    stat='Which stat to change',
    action='Add, remove, or set',
    amount='Amount to change'
)
@app_commands.choices(stat=STAT_CHOICES, action=ACTION_CHOICES)
async def editstats(
    interaction: discord.Interaction,
    member: discord.Member,
    stat: app_commands.Choice[str],
    action: app_commands.Choice[str],
    amount: float
):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)

    if not is_manager(interaction.user):
        return await interaction.response.send_message(
            '❌ Only users with the **Manager** role can modify stats.',
            ephemeral=True
        )

    if amount < 0:
        return await interaction.response.send_message(
            'Amount must be 0 or higher. Choose **Remove** to subtract.',
            ephemeral=True
        )

    field = stat.value
    allowed = {'appointments','bills','within_48','same_day','sales','closer_sales','pitches','hours'}
    if field not in allowed:
        return await interaction.response.send_message('Invalid stat.',ephemeral=True)

    c=con()
    c.execute('INSERT OR IGNORE INTO stats(guild_id,user_id) VALUES(?,?)',(interaction.guild.id,member.id))
    r=c.execute(f'SELECT {field} value FROM stats WHERE guild_id=? AND user_id=?',
                (interaction.guild.id,member.id)).fetchone()
    current=float(r['value']) if r else 0.0

    if action.value == 'add':
        new_value=current+amount
    elif action.value == 'remove':
        new_value=max(0,current-amount)
    else:
        new_value=max(0,amount)

    if field != 'hours':
        new_value=int(round(new_value))

    c.execute(f'UPDATE stats SET {field}=? WHERE guild_id=? AND user_id=?',
              (new_value,interaction.guild.id,member.id))
    c.commit(); c.close()

    await refresh_leaderboard(interaction.guild)

    labels={
        'appointments':'Appointments',
        'bills':'Bills',
        'within_48':'Within 48 Hours',
        'same_day':'Same Day',
        'sales':'Setter Sales',
        'closer_sales':'Closer Sales',
        'pitches':'Pitches',
        'hours':'Hours',
    }

    await interaction.response.send_message(
        f"✅ {member.mention}'s **{labels[field]}** is now **{new_value:g}**.",
        ephemeral=True
    )


@bot.tree.command(name='badges',description="Show current automated badges")
async def badges(interaction:discord.Interaction):
    e=discord.Embed(title="🏅 Chosen Genesis Badges")
    for name in DAILY+STREAK+WEEKLY:
        r=discord.utils.get(interaction.guild.roles,name=name); holders=r.members if r else []; e.add_field(name=name,value=', '.join(m.mention for m in holders) if holders else 'Unclaimed',inline=False)
    await interaction.response.send_message(embed=e)

if not TOKEN: raise RuntimeError('DISCORD_TOKEN environment variable is missing')
bot.run(TOKEN)
