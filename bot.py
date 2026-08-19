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
    CREATE TABLE IF NOT EXISTS stat_adjustments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      guild_id INTEGER,user_id INTEGER,stat_name TEXT,amount REAL,
      local_date TEXT,week_key TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS team_sale_adjustments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      guild_id INTEGER,amount INTEGER,local_date TEXT,created_at TEXT);
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


def adjustment_sum(g,u,stat,start_date,end_date):
    c=con(); r=c.execute(
        'SELECT COALESCE(SUM(amount),0) v FROM stat_adjustments WHERE guild_id=? AND user_id=? AND stat_name=? AND local_date BETWEEN ? AND ?',
        (g,u,stat,start_date,end_date)).fetchone(); c.close(); return float(r['v'] or 0)

def record_adjustment(g,u,stat,amount,local_date):
    if abs(amount) < 1e-9: return
    try: d=datetime.strptime(local_date,'%Y-%m-%d').date()
    except ValueError: return
    c=con(); c.execute(
        'INSERT INTO stat_adjustments(guild_id,user_id,stat_name,amount,local_date,week_key,created_at) VALUES(?,?,?,?,?,?,?)',
        (g,u,stat,amount,local_date,wkey(d),datetime.now(timezone.utc).isoformat()))
    c.commit(); c.close()

def resolved_edit_date(date_mode,custom_date):
    today=now().date()
    if date_mode=='today': return today
    if date_mode=='yesterday': return today-timedelta(days=1)
    if date_mode=='custom':
        if not custom_date: return None
        try: return datetime.strptime(custom_date,'%Y-%m-%d').date()
        except ValueError: return None
    return today

def daily_metric_totals(g,metric):
    today=dkey(); c=con(); totals={}
    if metric=='appointments':
        rows=c.execute('SELECT setter_id user_id,COUNT(*) value FROM appointment_events WHERE guild_id=? AND local_date=? GROUP BY setter_id',(g,today)).fetchall()
        stat='appointments'
    elif metric=='bills':
        rows=c.execute('SELECT setter_id user_id,SUM(bill_collected) value FROM appointment_events WHERE guild_id=? AND local_date=? GROUP BY setter_id',(g,today)).fetchall()
        stat='bills'
    elif metric=='same_day':
        rows=c.execute('SELECT setter_id user_id,SUM(same_day) value FROM appointment_events WHERE guild_id=? AND local_date=? GROUP BY setter_id',(g,today)).fetchall()
        stat='same_day'
    else:
        rows=c.execute('SELECT setter_id user_id,SUM(within_48) value FROM appointment_events WHERE guild_id=? AND local_date=? GROUP BY setter_id',(g,today)).fetchall()
        stat='within_48'
    for r in rows: totals[r['user_id']]=float(r['value'] or 0)
    adj=c.execute('SELECT user_id,SUM(amount) value FROM stat_adjustments WHERE guild_id=? AND stat_name=? AND local_date=? GROUP BY user_id',(g,stat,today)).fetchall()
    c.close()
    for r in adj: totals[r['user_id']]=totals.get(r['user_id'],0)+float(r['value'] or 0)
    return {u:max(0,v) for u,v in totals.items()}

def daily_leaders(g,metric):
    totals=daily_metric_totals(g,metric)
    totals={u:v for u,v in totals.items() if v>0}
    if not totals: return []
    best=max(totals.values())
    return [u for u,v in totals.items() if v==best]

async def refresh_daily_comp(guild):
    for metric,badge in [('appointments','🎯 Point Man'),('bills','📄 Bounty Hunter'),('same_day','⚡ Same Day Savage'),('within_48','⏰ Speed Demon')]:
        await set_holders(guild,badge,daily_leaders(guild.id,metric))

def closer_sales_today(g,u):
    today=dkey(); c=con()
    n=c.execute('SELECT COUNT(*) c FROM sale_events WHERE guild_id=? AND closer_id=? AND local_date=?',(g,u,today)).fetchone()['c']
    a=c.execute('SELECT COALESCE(SUM(amount),0) v FROM stat_adjustments WHERE guild_id=? AND user_id=? AND stat_name=? AND local_date=?',(g,u,'closer_sales',today)).fetchone()['v']
    c.close(); return max(0,int(n+(a or 0)))

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
    closers=[r['closer_id'] for r in c.execute('SELECT DISTINCT closer_id FROM sale_events WHERE guild_id=? AND closer_id>0',(guild.id,))]; c.close()
    await set_holders(guild,'🔥 Hot Streak',[u for u in setters if streak(guild.id,u,'appointment_events','setter_id',5)])
    await set_holders(guild,'🧊 Ice Cold',[u for u in closers if streak(guild.id,u,'sale_events','closer_id',3)])

def week_winners(g,wk,kind):
    c=con(); totals={}
    if kind=='setter':
        rows=c.execute('SELECT setter_id user_id,COUNT(*) value FROM appointment_events WHERE guild_id=? AND week_key=? GROUP BY setter_id',(g,wk)).fetchall(); stat='appointments'
    else:
        rows=c.execute('SELECT closer_id user_id,COUNT(*) value FROM sale_events WHERE guild_id=? AND week_key=? AND closer_id>0 GROUP BY closer_id',(g,wk)).fetchall(); stat='closer_sales'
    for r in rows: totals[r['user_id']]=float(r['value'] or 0)
    adj=c.execute('SELECT user_id,SUM(amount) value FROM stat_adjustments WHERE guild_id=? AND week_key=? AND stat_name=? GROUP BY user_id',(g,wk,stat)).fetchall(); c.close()
    for r in adj: totals[r['user_id']]=max(0,totals.get(r['user_id'],0)+float(r['value'] or 0))
    totals={u:v for u,v in totals.items() if v>0}
    if not totals: return [],0
    best=max(totals.values()); return [u for u,v in totals.items() if v==best],best

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
    c=con(); rows=c.execute('SELECT closer_id,COUNT(*) c,MAX(local_hour) h FROM sale_events WHERE guild_id=? AND local_date=? AND closer_id>0 GROUP BY closer_id',(guild.id,dkey())).fetchall()
    actual={r['closer_id']:{'c':int(r['c'] or 0),'h':int(r['h'] or 0)} for r in rows}
    adj=c.execute('SELECT user_id,SUM(amount) v FROM stat_adjustments WHERE guild_id=? AND stat_name=? AND local_date=? GROUP BY user_id',(guild.id,'closer_sales',dkey())).fetchall(); c.close()
    totals={u:data['c'] for u,data in actual.items()}
    for r in adj: totals[r['user_id']]=max(0,int(totals.get(r['user_id'],0)+float(r['v'] or 0)))
    ghosts=[]
    for uid,count in totals.items():
        m=guild.get_member(uid)
        if not m: continue
        if count>=1: await add_role(guild,m,'💥 Sale')
        if count>=2: await add_role(guild,m,'🥈 2 Spot')
        if count>=3: await add_role(guild,m,'🎩 Hattrick')
        if actual.get(uid,{}).get('h',0)>=19: ghosts.append(uid)
    await set_holders(guild,'👻 Ghost Hunter',ghosts)
    await refresh_daily_comp(guild)


DAILY_APPOINTMENT_GOAL = 10
MONTHLY_SALES_GOAL = 30

def progress_bar(value, goal, width=12):
    if goal <= 0:
        return '░' * width
    filled = max(0, min(width, round((value / goal) * width)))
    return '█' * filled + '░' * (width - filled)

def team_daily_appointments(guild_id):
    today=dkey()
    c=con()

    # Count each setter separately, then apply that setter's corrections.
    # This prevents an old negative correction on one person from incorrectly
    # reducing the whole team's daily goal counter.
    totals={}

    rows=c.execute(
        'SELECT setter_id user_id,COUNT(*) value FROM appointment_events '
        'WHERE guild_id=? AND local_date=? GROUP BY setter_id',
        (guild_id,today)
    ).fetchall()
    for r in rows:
        totals[r['user_id']]=float(r['value'] or 0)

    adjustments=c.execute(
        'SELECT user_id,COALESCE(SUM(amount),0) value FROM stat_adjustments '
        'WHERE guild_id=? AND stat_name=? AND local_date=? GROUP BY user_id',
        (guild_id,'appointments',today)
    ).fetchall()
    c.close()

    for r in adjustments:
        uid=r['user_id']
        totals[uid]=max(0,totals.get(uid,0)+float(r['value'] or 0))

    return int(round(sum(max(0,v) for v in totals.values())))

def team_monthly_sales(guild_id):
    today=now().date()
    start=today.replace(day=1).isoformat()
    end=today.isoformat()
    c=con()
    base=c.execute(
        'SELECT COUNT(*) v FROM sale_events WHERE guild_id=? AND local_date BETWEEN ? AND ?',
        (guild_id,start,end)
    ).fetchone()['v']
    manual=c.execute(
        'SELECT COALESCE(SUM(amount),0) v FROM team_sale_adjustments '
        'WHERE guild_id=? AND local_date BETWEEN ? AND ?',
        (guild_id,start,end)
    ).fetchone()['v']
    c.close()
    return max(0,int(round(float(base or 0)+float(manual or 0))))


def current_badge_board(guild):
    lines=[]
    for badge in DAILY+STREAK+WEEKLY:
        r=discord.utils.get(guild.roles,name=badge)
        holders=list(r.members) if r else []
        if holders:
            names=', '.join(m.display_name for m in holders)
            lines.append(f'{badge} — **{names}**')
    return '\n'.join(lines) if lines else 'No badges claimed yet.'

def weekly_leaderboard_rows(guild_id,kind):
    return period_rows(guild_id,'week',kind)

async def refresh_leaderboard(guild):
    ch=await channel(guild,'leaderboard')
    if not ch: return

    def fmt(rs):
        medals=['🥇','🥈','🥉']; out=[]
        for i,r in enumerate(rs):
            m=guild.get_member(r['user_id'])
            name=m.display_name if m else f"<@{r['user_id']}>"
            prefix=medals[i] if i<3 else f"{i+1}."
            out.append(f"{prefix} {name} — **{r['value']}**")
        return '\n'.join(out) or 'No stats yet.'

    async def upsert_board(meta_key,title,embed):
        saved_id=meta_get(guild.id,meta_key)
        if saved_id:
            try:
                msg=await ch.fetch_message(int(saved_id))
                await msg.edit(embed=embed)
                return
            except (discord.NotFound,discord.Forbidden,discord.HTTPException,ValueError):
                pass

        async for msg in ch.history(limit=100):
            if msg.author.id==bot.user.id and msg.embeds and msg.embeds[0].title==title:
                await msg.edit(embed=embed)
                meta_set(guild.id,meta_key,str(msg.id))
                return

        msg=await ch.send(embed=embed)
        meta_set(guild.id,meta_key,str(msg.id))

    # WEEKLY LIVE BOARD
    a=period_rows(guild.id,'week','appointments')
    s=period_rows(guild.id,'week','setter_sales')
    cl=period_rows(guild.id,'week','closer_sales')
    daily_appts=team_daily_appointments(guild.id)
    monthly_sales=team_monthly_sales(guild.id)

    daily_bar=progress_bar(daily_appts,DAILY_APPOINTMENT_GOAL)
    monthly_bar=progress_bar(monthly_sales,MONTHLY_SALES_GOAL)

    weekly=discord.Embed(
        title='🏆 Chosen Genesis — Weekly Leaderboard',
        description=(
            f'**🎯 TODAY: {daily_appts} / {DAILY_APPOINTMENT_GOAL} APPOINTMENTS**\n'
            f'`{daily_bar}` **{min(100,round(daily_appts/DAILY_APPOINTMENT_GOAL*100))}%**\n\n'
            f'**💰 MONTH: {monthly_sales} / {MONTHLY_SALES_GOAL} SALES**\n'
            f'`{monthly_bar}` **{min(100,round(monthly_sales/MONTHLY_SALES_GOAL*100))}%**'
        ),
        timestamp=datetime.now(timezone.utc)
    )
    weekly.add_field(name='📅 This Week — Appointments',value=fmt(a),inline=False)
    weekly.add_field(name='💰 This Week — Setter Sales',value=fmt(s),inline=False)
    weekly.add_field(name='🤝 This Week — Closer Sales',value=fmt(cl),inline=False)
    weekly.add_field(name='🏅 Current Badges',value=current_badge_board(guild),inline=False)
    weekly.set_footer(text='Updates automatically when stats change.')

    # MONTHLY BOARD
    ma=period_rows(guild.id,'month','appointments')
    ms=period_rows(guild.id,'month','setter_sales')
    mcl=period_rows(guild.id,'month','closer_sales')
    month_label=now().strftime('%B %Y')
    monthly=discord.Embed(
        title='📆 Chosen Genesis — Monthly Leaderboard',
        description=f'**{month_label}**',
        timestamp=datetime.now(timezone.utc)
    )
    monthly.add_field(name='📅 Appointments',value=fmt(ma),inline=False)
    monthly.add_field(name='💰 Setter Sales',value=fmt(ms),inline=False)
    monthly.add_field(name='🤝 Closer Sales',value=fmt(mcl),inline=False)
    monthly.set_footer(text='Updates automatically when stats change.')

    # YEARLY BOARD
    ya=period_rows(guild.id,'year','appointments')
    ys=period_rows(guild.id,'year','setter_sales')
    ycl=period_rows(guild.id,'year','closer_sales')
    yearly=discord.Embed(
        title='🏆 Chosen Genesis — Yearly Leaderboard',
        description=f'**{now().year}**',
        timestamp=datetime.now(timezone.utc)
    )
    yearly.add_field(name='📅 Appointments',value=fmt(ya),inline=False)
    yearly.add_field(name='💰 Setter Sales',value=fmt(ys),inline=False)
    yearly.add_field(name='🤝 Closer Sales',value=fmt(ycl),inline=False)
    yearly.set_footer(text='Updates automatically when stats change.')

    await upsert_board('weekly_leaderboard_message_id','🏆 Chosen Genesis — Weekly Leaderboard',weekly)
    await upsert_board('monthly_leaderboard_message_id','📆 Chosen Genesis — Monthly Leaderboard',monthly)
    await upsert_board('yearly_leaderboard_message_id','🏆 Chosen Genesis — Yearly Leaderboard',yearly)


PERIOD_CHOICES = [
    app_commands.Choice(name='Today', value='today'),
    app_commands.Choice(name='This Week', value='week'),
    app_commands.Choice(name='This Month', value='month'),
    app_commands.Choice(name='This Year', value='year'),
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
    if period=='year':
        start=today.replace(month=1,day=1)
        return start.isoformat(), today.isoformat(), str(today.year)
    return None,None,'All Time'

def period_rows(guild_id,period,kind):
    start,end,_=period_bounds(period)
    c=con()
    if period=='all':
        field={'appointments':'appointments','setter_sales':'sales','closer_sales':'closer_sales'}[kind]
        rows=c.execute(f'SELECT user_id,{field} value FROM stats WHERE guild_id=? AND {field}>0 ORDER BY {field} DESC LIMIT 10',(guild_id,)).fetchall(); c.close(); return rows

    totals={}
    if kind=='appointments':
        rows=c.execute('SELECT setter_id user_id,COUNT(*) value FROM appointment_events WHERE guild_id=? AND local_date BETWEEN ? AND ? GROUP BY setter_id',(guild_id,start,end)).fetchall(); stat='appointments'
    elif kind=='setter_sales':
        rows=c.execute('SELECT setter_id user_id,COUNT(*) value FROM sale_events WHERE guild_id=? AND local_date BETWEEN ? AND ? GROUP BY setter_id',(guild_id,start,end)).fetchall(); stat='sales'
    else:
        rows=c.execute('SELECT closer_id user_id,COUNT(*) value FROM sale_events WHERE guild_id=? AND local_date BETWEEN ? AND ? AND closer_id>0 GROUP BY closer_id',(guild_id,start,end)).fetchall(); stat='closer_sales'
    for r in rows: totals[r['user_id']]=float(r['value'] or 0)
    adj=c.execute('SELECT user_id,SUM(amount) value FROM stat_adjustments WHERE guild_id=? AND stat_name=? AND local_date BETWEEN ? AND ? GROUP BY user_id',(guild_id,stat,start,end)).fetchall(); c.close()
    for r in adj: totals[r['user_id']]=max(0,totals.get(r['user_id'],0)+float(r['value'] or 0))
    data=sorted(((u,v) for u,v in totals.items() if v>0),key=lambda x:x[1],reverse=True)[:10]
    return [{'user_id':u,'value':int(v) if float(v).is_integer() else v} for u,v in data]

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


def period_total_for_user(guild_id,user_id,stat,start_date,end_date):
    c=con()
    if stat=='appointments':
        base=c.execute(
            'SELECT COUNT(*) v FROM appointment_events WHERE guild_id=? AND setter_id=? AND local_date BETWEEN ? AND ?',
            (guild_id,user_id,start_date,end_date)
        ).fetchone()['v']
    elif stat=='bills':
        base=c.execute(
            'SELECT COALESCE(SUM(bill_collected),0) v FROM appointment_events WHERE guild_id=? AND setter_id=? AND local_date BETWEEN ? AND ?',
            (guild_id,user_id,start_date,end_date)
        ).fetchone()['v']
    elif stat=='within_48':
        base=c.execute(
            'SELECT COALESCE(SUM(within_48),0) v FROM appointment_events WHERE guild_id=? AND setter_id=? AND local_date BETWEEN ? AND ?',
            (guild_id,user_id,start_date,end_date)
        ).fetchone()['v']
    elif stat=='same_day':
        base=c.execute(
            'SELECT COALESCE(SUM(same_day),0) v FROM appointment_events WHERE guild_id=? AND setter_id=? AND local_date BETWEEN ? AND ?',
            (guild_id,user_id,start_date,end_date)
        ).fetchone()['v']
    elif stat=='sales':
        base=c.execute(
            'SELECT COUNT(*) v FROM sale_events WHERE guild_id=? AND setter_id=? AND local_date BETWEEN ? AND ?',
            (guild_id,user_id,start_date,end_date)
        ).fetchone()['v']
    elif stat=='closer_sales':
        base=c.execute(
            'SELECT COUNT(*) v FROM sale_events WHERE guild_id=? AND closer_id=? AND local_date BETWEEN ? AND ?',
            (guild_id,user_id,start_date,end_date)
        ).fetchone()['v']
    else:
        base=0

    adj=c.execute(
        'SELECT COALESCE(SUM(amount),0) v FROM stat_adjustments '
        'WHERE guild_id=? AND user_id=? AND stat_name=? AND local_date BETWEEN ? AND ?',
        (guild_id,user_id,stat,start_date,end_date)
    ).fetchone()['v']
    c.close()
    return max(0,int(round(float(base or 0)+float(adj or 0))))

def current_week_bounds():
    today=now().date()
    start=today-timedelta(days=today.weekday())
    return start.isoformat(),today.isoformat()

def current_month_bounds():
    today=now().date()
    return today.replace(day=1).isoformat(),today.isoformat()

def current_year_bounds():
    today=now().date()
    return today.replace(month=1,day=1).isoformat(),today.isoformat()

def weekly_rank(guild_id,user_id,stat):
    start,end=current_week_bounds()
    c=con()
    user_ids={r['user_id'] for r in c.execute('SELECT user_id FROM stats WHERE guild_id=?',(guild_id,)).fetchall()}
    if stat in {'appointments','bills','within_48','same_day','sales'}:
        if stat=='sales':
            user_ids.update(r['setter_id'] for r in c.execute(
                'SELECT DISTINCT setter_id FROM sale_events WHERE guild_id=? AND local_date BETWEEN ? AND ?',
                (guild_id,start,end)
            ).fetchall())
        else:
            user_ids.update(r['setter_id'] for r in c.execute(
                'SELECT DISTINCT setter_id FROM appointment_events WHERE guild_id=? AND local_date BETWEEN ? AND ?',
                (guild_id,start,end)
            ).fetchall())
    elif stat=='closer_sales':
        user_ids.update(r['closer_id'] for r in c.execute(
            'SELECT DISTINCT closer_id FROM sale_events WHERE guild_id=? AND local_date BETWEEN ? AND ? AND closer_id>0',
            (guild_id,start,end)
        ).fetchall())
    c.close()

    ranked=[]
    for uid in user_ids:
        value=period_total_for_user(guild_id,uid,stat,start,end)
        if value>0:
            ranked.append((uid,value))
    ranked.sort(key=lambda x:(-x[1],x[0]))
    for i,(uid,value) in enumerate(ranked,1):
        if uid==user_id:
            return i,value,len(ranked)
    return None,0,len(ranked)

def mini_bar(label,value,max_value,width=12):
    if max_value<=0:
        filled=0
    else:
        filled=max(0,min(width,round((value/max_value)*width)))
    return f"{label:<10} {'█'*filled}{'░'*(width-filled)} {value}"

def current_badges_for(member):
    valid=set(DAILY+STREAK+WEEKLY)
    return [r.name for r in member.roles if r.name in valid]

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
    for g in bot.guilds:
        await refresh_leaderboard(g)

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
@app_commands.describe(
    setter='Setter on the deal',
    closer='Closer who closed it (leave blank for outside team)',
    outside_team='Turn on if the closer is from another team',
    utility='APS, SRP, etc.'
)
async def sale(
    interaction:discord.Interaction,
    setter:discord.Member,
    outside_team:bool=False,
    closer:discord.Member|None=None,
    utility:str='Unknown'
):
    if not interaction.guild: return

    if not outside_team and closer is None:
        return await interaction.response.send_message(
            '❌ Choose a closer, or turn **Outside Team** on.',
            ephemeral=True
        )

    n=now(); g=interaction.guild.id
    closer_id=0 if outside_team else closer.id

    c=con()
    c.execute(
        'INSERT INTO sale_events(guild_id,setter_id,closer_id,utility,local_date,local_hour,week_key,created_at) '
        'VALUES(?,?,?,?,?,?,?,?)',
        (g,setter.id,closer_id,utility,dkey(n.date()),n.hour,wkey(n.date()),datetime.now(timezone.utc).isoformat())
    )
    c.commit(); c.close()

    add(g,setter.id,'sales',1)
    if not outside_team:
        add(g,closer.id,'closer_sales',1)

    e=discord.Embed(
        title='🚨 NEW SALE',
        description='**CHOSEN GENESIS +1** 🔥',
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(name='🔥 Setter',value=setter.mention)
    e.add_field(name='🤝 Closer',value='**Outside Team**' if outside_team else closer.mention)
    e.add_field(name='⚡ Utility',value=utility.upper())

    await interaction.response.send_message('Sale logged ✅',ephemeral=True)
    await main(interaction.guild,embed=e)

    # Outside-team closers never receive closer stats, streaks, or daily closer badges.
    if not outside_team:
        count=closer_sales_today(g,closer.id)
        if count>=1: await add_role(interaction.guild,closer,'💥 Sale')
        if count==1: await main(interaction.guild,content=f'💥 **SALE BADGE!** {closer.mention} got a sale today!')
        if count>=2: await add_role(interaction.guild,closer,'🥈 2 Spot')
        if count==2: await main(interaction.guild,content=f'🥈 **2 SPOT!** {closer.mention} has **2 sales today!**')
        if count>=3: await add_role(interaction.guild,closer,'🎩 Hattrick')
        if count==3: await main(interaction.guild,content=f'🎩 **HATTRICK!** {closer.mention} has **3 sales today!** 🔥')
        if n.hour>=19:
            await add_role(interaction.guild,closer,'👻 Ghost Hunter')
            await main(interaction.guild,content=f'👻 **GHOST HUNTER!** {closer.mention} closed a deal after 7 PM!')

    await refresh_streaks(interaction.guild)
    await refresh_leaderboard(interaction.guild)


@bot.tree.command(name='goalcheck',description='Manager-only: check today\'s appointment goal count')
async def goalcheck(interaction:discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message(
            '❌ Only users with the **Manager** role can use this.',
            ephemeral=True
        )

    today=dkey()
    c=con()
    rows=c.execute(
        'SELECT setter_id user_id,COUNT(*) value FROM appointment_events '
        'WHERE guild_id=? AND local_date=? GROUP BY setter_id',
        (interaction.guild.id,today)
    ).fetchall()
    adjustments=c.execute(
        'SELECT user_id,COALESCE(SUM(amount),0) value FROM stat_adjustments '
        'WHERE guild_id=? AND stat_name=? AND local_date=? GROUP BY user_id',
        (interaction.guild.id,'appointments',today)
    ).fetchall()
    c.close()

    data={}
    for r in rows:
        data[r['user_id']]={'logs':float(r['value'] or 0),'adjustments':0}
    for r in adjustments:
        data.setdefault(r['user_id'],{'logs':0,'adjustments':0})
        data[r['user_id']]['adjustments']=float(r['value'] or 0)

    lines=[]
    for uid,vals in data.items():
        member=interaction.guild.get_member(uid)
        name=member.display_name if member else f'<@{uid}>'
        final=max(0,vals['logs']+vals['adjustments'])
        lines.append(
            f"{name}: logs **{vals['logs']:g}**, corrections **{vals['adjustments']:+g}**, counted **{final:g}**"
        )

    total=team_daily_appointments(interaction.guild.id)
    text='\n'.join(lines) if lines else 'No appointment activity recorded today.'
    await interaction.response.send_message(
        f"**Today's goal count: {total}/{DAILY_APPOINTMENT_GOAL}**\n\n{text}",
        ephemeral=True
    )


@bot.tree.command(name='leaderboard',description='Refresh weekly, monthly, and yearly leaderboards')
async def leaderboard(interaction:discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    await refresh_leaderboard(interaction.guild)
    await interaction.followup.send('Weekly, monthly, and yearly leaderboards refreshed ✅',ephemeral=True)


@bot.tree.command(name='mystats',description='View your private performance dashboard')
async def mystats(interaction:discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)

    member=interaction.user
    start,end=current_week_bounds()
    mstart,mend=current_month_bounds()
    ystart,yend=current_year_bounds()

    # This week
    appts=period_total_for_user(interaction.guild.id,member.id,'appointments',start,end)
    bills=period_total_for_user(interaction.guild.id,member.id,'bills',start,end)
    within48=period_total_for_user(interaction.guild.id,member.id,'within_48',start,end)
    same_day=period_total_for_user(interaction.guild.id,member.id,'same_day',start,end)
    setter_sales=period_total_for_user(interaction.guild.id,member.id,'sales',start,end)
    closer_sales=period_total_for_user(interaction.guild.id,member.id,'closer_sales',start,end)

    # This month
    month_appts=period_total_for_user(interaction.guild.id,member.id,'appointments',mstart,mend)
    month_setter_sales=period_total_for_user(interaction.guild.id,member.id,'sales',mstart,mend)
    month_closer_sales=period_total_for_user(interaction.guild.id,member.id,'closer_sales',mstart,mend)

    # This year
    year_appts=period_total_for_user(interaction.guild.id,member.id,'appointments',ystart,yend)
    year_setter_sales=period_total_for_user(interaction.guild.id,member.id,'sales',ystart,yend)
    year_closer_sales=period_total_for_user(interaction.guild.id,member.id,'closer_sales',ystart,yend)

    bill_rate=(bills/appts*100) if appts else 0
    within_rate=(within48/appts*100) if appts else 0
    same_day_rate=(same_day/appts*100) if appts else 0

    appt_rank,_,_=weekly_rank(interaction.guild.id,member.id,'appointments')
    setter_rank,_,_=weekly_rank(interaction.guild.id,member.id,'sales')
    closer_rank,_,_=weekly_rank(interaction.guild.id,member.id,'closer_sales')

    badges=current_badges_for(member)

    graph_values=[appts,bills,within48,same_day,setter_sales,closer_sales]
    graph_max=max(graph_values) if graph_values else 0
    graph='```\n'
    graph+=mini_bar('Appts',appts,graph_max)+'\n'
    graph+=mini_bar('Bills',bills,graph_max)+'\n'
    graph+=mini_bar('48 Hours',within48,graph_max)+'\n'
    graph+=mini_bar('Same Day',same_day,graph_max)+'\n'
    graph+=mini_bar('Set Sales',setter_sales,graph_max)+'\n'
    graph+=mini_bar('Cls Sales',closer_sales,graph_max)+'\n```'

    e=discord.Embed(
        title=f'📊 {member.display_name} — My Stats',
        description='**This Week**\n'+graph,
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(
        name='📅 This Week',
        value=(
            f'Appointments: **{appts}**\n'
            f'📄 Bills: **{bills}** ({bill_rate:.0f}%)\n'
            f'⏰ Within 48h: **{within48}** ({within_rate:.0f}%)\n'
            f'⚡ Same Day: **{same_day}** ({same_day_rate:.0f}%)\n'
            f'💰 Setter Sales: **{setter_sales}**\n'
            f'🤝 Closer Sales: **{closer_sales}**'
        ),
        inline=False
    )
    e.add_field(
        name='📆 This Month',
        value=(
            f'Appointments: **{month_appts}**\n'
            f'Setter Sales: **{month_setter_sales}**\n'
            f'Closer Sales: **{month_closer_sales}**'
        ),
        inline=True
    )
    e.add_field(
        name=f'🗓️ {now().year}',
        value=(
            f'Appointments: **{year_appts}**\n'
            f'Setter Sales: **{year_setter_sales}**\n'
            f'Closer Sales: **{year_closer_sales}**'
        ),
        inline=True
    )
    e.add_field(
        name='🏆 Weekly Rank',
        value=(
            f'Appointments: **#{appt_rank}**\n' if appt_rank else 'Appointments: **Unranked**\n'
        ) + (
            f'Setter Sales: **#{setter_rank}**\n' if setter_rank else 'Setter Sales: **Unranked**\n'
        ) + (
            f'Closer Sales: **#{closer_rank}**' if closer_rank else 'Closer Sales: **Unranked**'
        ),
        inline=False
    )
    e.add_field(
        name='🏅 Current Badges',
        value='\n'.join(badges) if badges else 'No current badges',
        inline=False
    )
    e.set_footer(text='Only you can see this dashboard.')
    await interaction.response.send_message(embed=e,ephemeral=True)


@bot.tree.command(name='stats',description="Manager-only: view a rep's saved totals")
async def stats(interaction:discord.Interaction,member:discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message(
            '❌ Only users with the **Manager** role can view another member\'s detailed stats.',
            ephemeral=True
        )

    c=con()
    r=c.execute(
        'SELECT * FROM stats WHERE guild_id=? AND user_id=?',
        (interaction.guild.id,member.id)
    ).fetchone()
    c.close()
    if not r:
        return await interaction.response.send_message('No stats yet.',ephemeral=True)

    a=r['appointments']
    e=discord.Embed(title=f"📈 {member.display_name}'s Saved Totals")
    e.add_field(name='📅 Appointments',value=a)
    e.add_field(name='📄 Bills',value=f"{r['bills']} ({(r['bills']/a*100 if a else 0):.0f}%)")
    e.add_field(name='⏰ Within 48h',value=f"{r['within_48']} ({(r['within_48']/a*100 if a else 0):.0f}%)")
    e.add_field(name='⚡ Same Day',value=r['same_day'])
    e.add_field(name='💰 Setter Sales',value=r['sales'])
    e.add_field(name='🤝 Closer Sales',value=r['closer_sales'])
    await interaction.response.send_message(embed=e,ephemeral=True)


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

EDIT_DATE_CHOICES = [
    app_commands.Choice(name='Today', value='today'),
    app_commands.Choice(name='Yesterday', value='yesterday'),
    app_commands.Choice(name='Custom Date', value='custom'),
]

STAT_CHOICES = [
    app_commands.Choice(name='Appointments', value='appointments'),
    app_commands.Choice(name='Bills', value='bills'),
    app_commands.Choice(name='Within 48 Hours', value='within_48'),
    app_commands.Choice(name='Same Day', value='same_day'),
    app_commands.Choice(name='Setter Sales', value='sales'),
    app_commands.Choice(name='Closer Sales', value='closer_sales'),
]

ACTION_CHOICES = [
    app_commands.Choice(name='➕ Add', value='add'),
    app_commands.Choice(name='➖ Remove', value='remove'),
    app_commands.Choice(name='✏️ Set', value='set'),
]


DATE_CHOICES = [
    app_commands.Choice(name='Today', value='today'),
    app_commands.Choice(name='Yesterday', value='yesterday'),
    app_commands.Choice(name='Custom Date', value='custom'),
]

BACKFILL_STAT_CHOICES = [
    app_commands.Choice(name='Appointments', value='appointments'),
    app_commands.Choice(name='Bills', value='bills'),
    app_commands.Choice(name='Within 48 Hours', value='within_48'),
    app_commands.Choice(name='Same Day', value='same_day'),
    app_commands.Choice(name='Setter Sales', value='sales'),
    app_commands.Choice(name='Closer Sales', value='closer_sales'),
]

@bot.tree.command(
    name='backfillsales',
    description='Manager-only: safely add historical sales without daily badges'
)
@app_commands.describe(
    amount='Number of historical sales to add',
    date='Today, yesterday, or custom date',
    setter='Optional setter to credit',
    closer='Optional team closer to credit',
    outside_team='Turn on only if the closer was outside your team',
    count_team_goal='Should these sales add to the 30-sale team goal?',
    custom_date='Only use with Custom Date, format YYYY-MM-DD'
)
@app_commands.choices(date=DATE_CHOICES)
async def backfillsales(
    interaction:discord.Interaction,
    amount:int,
    date:app_commands.Choice[str],
    setter:discord.Member|None=None,
    closer:discord.Member|None=None,
    outside_team:bool=False,
    count_team_goal:bool=True,
    custom_date:str|None=None
):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message(
            '❌ Only users with the **Manager** role can backfill sales.',
            ephemeral=True
        )
    if amount<=0:
        return await interaction.response.send_message('Amount must be greater than 0.',ephemeral=True)

    if setter is None and closer is None and not outside_team:
        return await interaction.response.send_message(
            '❌ Choose at least a **setter** or **closer** to credit.',
            ephemeral=True
        )

    if outside_team and closer is not None:
        return await interaction.response.send_message(
            '❌ If **Outside Team** is on, leave the closer blank.',
            ephemeral=True
        )

    edit_date=resolved_edit_date(date.value,custom_date)
    if not edit_date:
        return await interaction.response.send_message(
            '❌ For Custom Date, enter the date like **2026-08-19**.',
            ephemeral=True
        )

    g=interaction.guild.id
    date_text=edit_date.isoformat()

    credited=[]

    # Credit setter only if one was supplied.
    if setter is not None:
        add(g,setter.id,'sales',amount)
        record_adjustment(g,setter.id,'sales',amount,date_text)
        credited.append(f'Setter: {setter.mention}')

    # Credit closer only if they are actually on this team.
    if closer is not None and not outside_team:
        add(g,closer.id,'closer_sales',amount)
        record_adjustment(g,closer.id,'closer_sales',amount,date_text)
        credited.append(f'Closer: {closer.mention}')
    elif outside_team:
        credited.append('Closer: **Outside Team**')

    # Team goal is optional. This prevents double-counting when you are
    # only correcting a closer number for a sale that was already counted.
    if count_team_goal:
        c=con()
        c.execute(
            'INSERT INTO team_sale_adjustments(guild_id,amount,local_date,created_at) VALUES(?,?,?,?)',
            (g,amount,date_text,datetime.now(timezone.utc).isoformat())
        )
        c.commit(); c.close()

    await refresh_leaderboard(interaction.guild)

    goal_text='Yes' if count_team_goal else 'No'
    await interaction.response.send_message(
        f'✅ Safely added **{amount} historical sale(s)** on **{date_text}**.\n'
        + '\n'.join(credited)
        + f'\nTeam 30-sale goal: **{goal_text}**\n\n'
        + 'No Sale, 2 Spot, Hattrick, or Ghost Hunter badges were triggered.',
        ephemeral=True
    )


@bot.tree.command(
    name='backfillstats',
    description='Manager-only: assign existing stats to a past date without changing the total'
)
@app_commands.describe(
    member='Member whose existing stats need a date',
    stat='Which existing stat to date',
    amount='How many of that stat happened on this date',
    date='Today, yesterday, or custom date',
    custom_date='Only use with Custom Date, format YYYY-MM-DD'
)
@app_commands.choices(
    stat=BACKFILL_STAT_CHOICES,
    date=DATE_CHOICES
)
async def backfillstats(
    interaction: discord.Interaction,
    member: discord.Member,
    stat: app_commands.Choice[str],
    amount: float,
    date: app_commands.Choice[str],
    custom_date: str|None=None
):
    if not interaction.guild:
        return await interaction.response.send_message(
            'Use this command inside the server.',
            ephemeral=True
        )

    if not is_manager(interaction.user):
        return await interaction.response.send_message(
            '❌ Only users with the **Manager** role can backfill stats.',
            ephemeral=True
        )

    if amount <= 0:
        return await interaction.response.send_message(
            'Amount must be greater than 0.',
            ephemeral=True
        )

    edit_date=resolved_edit_date(date.value,custom_date)
    if not edit_date:
        return await interaction.response.send_message(
            '❌ For Custom Date, enter the date like **2026-08-19**.',
            ephemeral=True
        )

    field=stat.value
    if field != 'hours':
        amount=int(round(amount))

    # IMPORTANT: this creates dated history only. It does NOT change the saved all-time total.
    record_adjustment(
        interaction.guild.id,
        member.id,
        field,
        amount,
        edit_date.isoformat()
    )

    await restore_daily(interaction.guild)
    await refresh_streaks(interaction.guild)
    await refresh_leaderboard(interaction.guild)

    labels={
        'appointments':'Appointments',
        'bills':'Bills',
        'within_48':'Within 48 Hours',
        'same_day':'Same Day',
        'sales':'Setter Sales',
        'closer_sales':'Closer Sales',
    }

    await interaction.response.send_message(
        f"✅ Backfilled **{amount:g} {labels[field]}** for {member.mention} on "
        f"**{edit_date.isoformat()}**. Their saved all-time total was not changed.",
        ephemeral=True
    )


@bot.tree.command(name='editstats',description='Manager-only: correct stats and leaderboard history')
@app_commands.describe(
    member='Member whose stats you want to change',
    stat='Which stat to change',
    action='Add, remove, or set',
    amount='Amount to change',
    date='When should this correction count?',
    custom_date='Only for Custom Date: YYYY-MM-DD'
)
@app_commands.choices(stat=STAT_CHOICES, action=ACTION_CHOICES, date=EDIT_DATE_CHOICES)
async def editstats(
    interaction: discord.Interaction,
    member: discord.Member,
    stat: app_commands.Choice[str],
    action: app_commands.Choice[str],
    amount: float,
    date: app_commands.Choice[str],
    custom_date: str|None=None
):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message('❌ Only users with the **Manager** role can modify stats.',ephemeral=True)
    if amount < 0:
        return await interaction.response.send_message('Amount must be 0 or higher. Choose **Remove** to subtract.',ephemeral=True)

    edit_date=resolved_edit_date(date.value,custom_date)
    if not edit_date:
        return await interaction.response.send_message('❌ For Custom Date, enter the date like **2026-08-19**.',ephemeral=True)

    field=stat.value
    allowed={'appointments','bills','within_48','same_day','sales','closer_sales','pitches','hours'}
    if field not in allowed:
        return await interaction.response.send_message('Invalid stat.',ephemeral=True)

    c=con(); c.execute('INSERT OR IGNORE INTO stats(guild_id,user_id) VALUES(?,?)',(interaction.guild.id,member.id))
    r=c.execute(f'SELECT {field} value FROM stats WHERE guild_id=? AND user_id=?',(interaction.guild.id,member.id)).fetchone()
    current=float(r['value']) if r else 0.0

    if action.value=='add': new_value=current+amount
    elif action.value=='remove': new_value=max(0,current-amount)
    else: new_value=max(0,amount)

    if field!='hours': new_value=int(round(new_value))
    delta=new_value-current

    c.execute(f'UPDATE stats SET {field}=? WHERE guild_id=? AND user_id=?',(new_value,interaction.guild.id,member.id)); c.commit(); c.close()
    record_adjustment(interaction.guild.id,member.id,field,delta,edit_date.isoformat())

    await restore_daily(interaction.guild)
    await refresh_streaks(interaction.guild)
    await refresh_leaderboard(interaction.guild)

    labels={'appointments':'Appointments','bills':'Bills','within_48':'Within 48 Hours','same_day':'Same Day','sales':'Setter Sales','closer_sales':'Closer Sales','pitches':'Pitches','hours':'Hours'}
    await interaction.response.send_message(
        f"✅ {member.mention}'s **{labels[field]}** is now **{new_value:g}**. The {delta:+g} correction counts on **{edit_date.isoformat()}**.",
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
