import os, sqlite3, random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import discord
from discord import app_commands
from discord.ext import commands, tasks

TOKEN=os.getenv('DISCORD_TOKEN')
DATA_PATH=os.getenv('DATA_PATH','genesis.db')
GUILD_ID=os.getenv('GUILD_ID')
TZ=ZoneInfo(os.getenv('TIMEZONE','America/Phoenix'))

DAILY=['🩸 First Blood','🦉 Night Owl','👻 Ghost Hunter','🎯 Point Man','📄 Bounty Hunter','⚡ Same Day Savage','⏰ Speed Demon','💥 Sale','🥈 2 Spot','🎩 Hattrick']
STREAK=['🔥 Hot Streak','🧊 Ice Cold']
WEEKLY=['👑 Setter King','👑 Closer King']

BADGE_DESCRIPTIONS = {
    '🩸 First Blood':'First appointment of the day.',
    '🦉 Night Owl':'Last appointment of the evening.',
    '👻 Ghost Hunter':'Sale after 7 PM.',
    '🎯 Point Man':'One daily winner. Minimum 2 appointments; quality breaks ties.',
    '📄 Bounty Hunter':'Most bills collected that day.',
    '⚡ Same Day Savage':'Most same-day appointments that day.',
    '⏰ Speed Demon':'Most appointments within 48 hours that day.',
    '💥 Sale':'1 sale in a day.',
    '🥈 2 Spot':'2 sales in a day.',
    '🎩 Hattrick':'3 sales in a day.',
    '🔥 Hot Streak':'Appointment on 5 straight workdays.',
    '🧊 Ice Cold':'Sale on 3 straight workdays.',
    '👑 Setter King':'Most setter sales for the week; appointments break ties.',
    '👑 Closer King':'Most closer sales for the week.'
}

BADGE_POINT_VALUES = {
    '🩸 First Blood':1,
    '🦉 Night Owl':1,
    '👻 Ghost Hunter':1,
    '🎯 Point Man':1,
    '📄 Bounty Hunter':1,
    '⚡ Same Day Savage':1,
    '⏰ Speed Demon':1,
    '💥 Sale':1,
    '🥈 2 Spot':1,
    '🎩 Hattrick':1,
    '🔥 Hot Streak':1,
    '🧊 Ice Cold':1,
}

APPOINTMENT_ANNOUNCEMENTS = [
    ("📅 APPOINTMENT ON THE BOARD", "Another opportunity created. Keep stacking."),
    ("🚪 DOORS → OPPORTUNITIES", "Another one added to the calendar."),
    ("🔥 KEEP STACKING", "Chosen Genesis adds another appointment."),
    ("🎯 TARGET ACQUIRED", "Another appointment is officially on the board."),
    ("⚡ MOMENTUM", "Another opportunity created for the team."),
    ("📈 BOARD MOVING", "The appointment count keeps climbing."),
]

SALE_ANNOUNCEMENTS = [
    ("🚨 NEW SALE", "**CHOSEN GENESIS +1** 🔥"),
    ("💰 BAG SECURED", "Another one closed for Chosen Genesis."),
    ("☀️ ANOTHER ONE DOWN", "Chosen Genesis keeps rolling. +1 sale."),
    ("🔥 DEAL CLOSED", "Another one officially on the board."),
    ("📈 BOARD MOVING", "Chosen Genesis adds another sale."),
    ("⚡ CASHED IN", "Another opportunity turned into a deal."),
]


WELCOME_MESSAGES = [
    ("🚨 NEW RECRUIT", "Welcome {mention} to **Chosen Genesis**. 🫡\n\nThe board is at zero. Time to earn your name.\n\n**Everybody welcome them in. 🔥**"),
    ("🪖 REINFORCEMENTS HAVE ARRIVED", "{mention} just joined **Chosen Genesis**.\n\nShow them how we do things around here. 🫡"),
    ("👀 WHO LET THIS GUY IN?", "Welcome {mention} to **Chosen Genesis** 😂🔥\n\n**Team, show some love.**"),
    ("🔥 WELCOME TO CHOSEN GENESIS", "{mention} is officially in.\n\n**Drop a 🫡 and welcome them to the team.**"),
    ("⚔️ ANOTHER ONE JOINS THE RANKS", "{mention}, welcome to **Chosen Genesis**.\n\nNew name. Fresh board. Let's work. 🔥"),
]


DAILY_AWARD_CLOSERS = [
    "Another day in the books. **Who's taking the badges tomorrow? 👀**",
    "Clock's out. Results are in. **Tomorrow the board goes back up for grabs. 🔥**",
    "That's a wrap for **Chosen Genesis**. Crowns earned. Badges claimed. **Run it back tomorrow. 🫡**",
    "The doors are closed. **The scoreboard isn't lying.** See y'all tomorrow. 😈",
    "Today's winners are official. **Enjoy it tonight — tomorrow nobody cares. 😂🔥**",
    "Badges locked. Bragging rights secured. **Tomorrow we start from zero.**",
    "**Chosen Genesis** clocked out with **{sales} sales** and **{appointments} appointments**. Who's coming for the board tomorrow? 👑",
    "Day complete. Some people earned badges. **Some people earned motivation. 😂**",
    "The board is final. **Talk your talk tonight — you've got to defend it tomorrow. 👀**",
    "That's game. Winners enjoy it. **Everybody else knows what time it is tomorrow. 🔥**",
]

PRESSURE_COPY = {
    '🎯 Point Man': [
        "🎯 **POINT MAN RACE**\n{names} are tied at **{value} appointments**.\n\n**Somebody break it. 👀**",
        "🎯 **DEADLOCK AT THE TOP**\n{names} are sitting at **{value} appointments**.\n\n**Who's taking Point Man? 😈**",
        "🎯 **POINT MAN IS UP FOR GRABS**\n{names} are tied at **{value}**.\n\n**Next appointment changes the board.**",
    ],
    '📄 Bounty Hunter': [
        "📄 **BOUNTY HUNTER DEADLOCK**\n{names} are tied with **{value} bills**.\n\n**Somebody go break the tie.**",
        "📄 **THE BOUNTY IS OPEN**\n{names} are tied at **{value} bills**.\n\n**Who's collecting the next one? 👀**",
        "📄 **BILL RACE**\n{names} are neck-and-neck with **{value}**.\n\n**Go take it.**",
    ],
    '⚡ Same Day Savage': [
        "⚡ **SAME DAY RACE**\n{names} are tied at **{value} same-days**.\n\n**Next one takes the lead.**",
        "⚡ **SAVAGE BADGE IS OPEN**\n{names} are tied with **{value} same-days**.\n\n**Who's separating themselves? 👀**",
        "⚡ **TIE GAME**\n{names} both have **{value} same-days**.\n\n**Somebody apply pressure.**",
    ],
    '⏰ Speed Demon': [
        "⏰ **SPEED DEMON RACE**\n{names} are tied at **{value} within-48 appointments**.\n\n**Who's moving first? 👀**",
        "⏰ **TOO CLOSE TO CALL**\n{names} are tied with **{value}**.\n\n**Next one could take Speed Demon.**",
        "⏰ **SPEED CHECK**\n{names} are neck-and-neck at **{value}**.\n\n**Pick up the pace. 😈**",
    ],
}

# Minimum totals before a tie is worth interrupting the chat.
PRESSURE_MINIMUMS = {
    '🎯 Point Man': 3,
    '📄 Bounty Hunter': 2,
    '⚡ Same Day Savage': 2,
    '⏰ Speed Demon': 2,
}

def pressure_key(badge):
    return ''.join(ch for ch in badge if ch.isalnum() or ch=='_')

def daily_metric_snapshot(g,metric):
    c=con()
    today=dkey()
    if metric=='appointments':
        rows=c.execute(
            'SELECT setter_id user_id,COUNT(*) value FROM appointment_events WHERE guild_id=? AND local_date=? GROUP BY setter_id',
            (g,today)
        ).fetchall(); stat='appointments'
    elif metric=='bills':
        rows=c.execute(
            'SELECT setter_id user_id,COALESCE(SUM(bill_collected),0) value FROM appointment_events WHERE guild_id=? AND local_date=? GROUP BY setter_id',
            (g,today)
        ).fetchall(); stat='bills'
    elif metric=='same_day':
        rows=c.execute(
            'SELECT setter_id user_id,COALESCE(SUM(same_day),0) value FROM appointment_events WHERE guild_id=? AND local_date=? GROUP BY setter_id',
            (g,today)
        ).fetchall(); stat='same_day'
    else:
        rows=c.execute(
            'SELECT setter_id user_id,COALESCE(SUM(within_48),0) value FROM appointment_events WHERE guild_id=? AND local_date=? GROUP BY setter_id',
            (g,today)
        ).fetchall(); stat='within_48'
    totals={r['user_id']:float(r['value'] or 0) for r in rows}
    adj=c.execute(
        'SELECT user_id,COALESCE(SUM(amount),0) value FROM stat_adjustments WHERE guild_id=? AND stat_name=? AND local_date=? GROUP BY user_id',
        (g,stat,today)
    ).fetchall()
    c.close()
    for r in adj:
        totals[r['user_id']]=max(0,totals.get(r['user_id'],0)+float(r['value'] or 0))
    totals={u:int(v) for u,v in totals.items() if v>0}
    if not totals:
        return [],0
    high=max(totals.values())
    return [u for u,v in totals.items() if v==high],high

async def maybe_pressure_message(guild,badge,metric):
    leaders,value=daily_metric_snapshot(guild.id,metric)
    if len(leaders)<2 or value<PRESSURE_MINIMUMS.get(badge,2):
        return

    # One tie-pressure post per badge per day. The bot starts the conversation
    # and then gets out of the way.
    key=f"pressure_{pressure_key(badge)}_{dkey()}"
    if meta_get(guild.id,key):
        return

    names=[]
    for uid in leaders[:4]:
        member=guild.get_member(uid)
        names.append(member.mention if member else f'<@{uid}>')
    text=random.choice(PRESSURE_COPY[badge]).format(
        names=' and '.join(names),
        value=value
    )
    await main(guild,content=text)
    meta_set(guild.id,key,'1')

async def maybe_night_owl_watch(guild,new_holder_id):
    # Night Owl chatter only starts in the evening.
    if now().hour < 18:
        return

    today=dkey()
    holder=guild.get_member(new_holder_id)
    if not holder:
        return

    holder_key=f'night_owl_live_holder_{today}'
    old_raw=meta_get(guild.id,holder_key)
    old_id=int(old_raw) if old_raw and str(old_raw).isdigit() else None

    # First evening holder: one "watch" message maximum.
    watch_key=f'night_owl_watch_{today}'
    stolen_key=f'night_owl_stolen_{today}'

    if old_id is None:
        meta_set(guild.id,holder_key,str(new_holder_id))
        if not meta_get(guild.id,watch_key):
            await main(
                guild,
                content=f'🦉 **NIGHT OWL WATCH**\n{holder.mention} currently has the latest appointment of the night.\n\n**Are they keeping it… or is somebody stealing it? 👀**'
            )
            meta_set(guild.id,watch_key,'1')
        return

    if old_id==new_holder_id:
        return

    # Only one steal message for the whole night to avoid bot spam.
    meta_set(guild.id,holder_key,str(new_holder_id))
    if not meta_get(guild.id,stolen_key):
        old=guild.get_member(old_id)
        old_text=old.mention if old else f'<@{old_id}>'
        await main(
            guild,
            content=f'🦉 **NIGHT OWL STOLEN**\n{holder.mention} just took the latest appointment from {old_text}.\n\n**Clock’s still running. 😈**'
        )
        meta_set(guild.id,stolen_key,'1')

def pick_announcement(pool):
    return random.choice(pool)


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
    CREATE TABLE IF NOT EXISTS badge_awards(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      guild_id INTEGER,user_id INTEGER,badge_name TEXT,award_key TEXT,created_at TEXT,
      UNIQUE(guild_id,user_id,badge_name,award_key));
    CREATE TABLE IF NOT EXISTS personal_records(
      guild_id INTEGER,user_id INTEGER,record_name TEXT,best_value INTEGER DEFAULT 0,
      PRIMARY KEY(guild_id,user_id,record_name));
    CREATE TABLE IF NOT EXISTS record_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      guild_id INTEGER,user_id INTEGER,record_name TEXT,value INTEGER,
      local_date TEXT,week_key TEXT,created_at TEXT);
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



def award_badge_count(g,u,badge_name,award_key):
    if not u or not award_key: return False
    c=con()
    cur=c.execute(
        'INSERT OR IGNORE INTO badge_awards(guild_id,user_id,badge_name,award_key,created_at) VALUES(?,?,?,?,?)',
        (g,u,badge_name,str(award_key),datetime.now(timezone.utc).isoformat())
    )
    changed=cur.rowcount>0
    c.commit(); c.close()
    return changed

def badge_counts(g,u):
    c=con()
    rows=c.execute(
        'SELECT badge_name,COUNT(*) c FROM badge_awards WHERE guild_id=? AND user_id=? GROUP BY badge_name',
        (g,u)
    ).fetchall()
    c.close()
    return {r['badge_name']:int(r['c']) for r in rows}

def last_setter_for_date(g,date_text):
    c=con()
    r=c.execute(
        'SELECT setter_id FROM appointment_events WHERE guild_id=? AND local_date=? ORDER BY id DESC LIMIT 1',
        (g,date_text)
    ).fetchone()
    c.close()
    return r['setter_id'] if r else None

async def set_live_night_owl(guild,date_text=None):
    date_text=date_text or dkey()
    uid=last_setter_for_date(guild.id,date_text)
    await set_holders(guild,'🦉 Night Owl',[uid] if uid else [])
    return uid

async def finalize_night_owl(guild,date_obj,set_role=True):
    date_text=date_obj.isoformat()
    uid=last_setter_for_date(guild.id,date_text)
    if not uid:
        return None
    if award_badge_count(guild.id,uid,'🦉 Night Owl',date_text):
        await announce_badge_milestone(guild,uid,'🦉 Night Owl')
    if set_role:
        await set_holders(guild,'🦉 Night Owl',[uid])
    return uid

async def finalize_previous_day_badges(guild):
    # Backup only: if the bot missed 9 PM, preserve yesterday's Night Owl in
    # badge history without showing yesterday's role throughout the new day.
    yesterday=now().date()-timedelta(days=1)
    key='night_owl_finalized'
    if meta_get(guild.id,key)==yesterday.isoformat():
        return
    await finalize_night_owl(guild,yesterday,set_role=False)
    meta_set(guild.id,key,yesterday.isoformat())


BADGE_MILESTONES = {5,10,25,50,100}

def badge_count_for(g,u,badge_name):
    c=con()
    r=c.execute(
        'SELECT COUNT(*) c FROM badge_awards WHERE guild_id=? AND user_id=? AND badge_name=?',
        (g,u,badge_name)
    ).fetchone()
    c.close()
    return int(r['c'] or 0)

async def announce_badge_milestone(guild,user_id,badge_name):
    count=badge_count_for(guild.id,user_id,badge_name)
    if count not in BADGE_MILESTONES:
        return
    member=guild.get_member(user_id)
    if not member:
        return
    await main(
        guild,
        content=f'🏅 **BADGE MILESTONE!** {member.mention} just earned **{badge_name}** for the **{count}th time!**'
    )

def get_personal_best(g,u,record_name):
    c=con()
    r=c.execute(
        'SELECT best_value FROM personal_records WHERE guild_id=? AND user_id=? AND record_name=?',
        (g,u,record_name)
    ).fetchone()
    c.close()
    return int(r['best_value']) if r else 0

def set_personal_best(g,u,record_name,value):
    c=con()
    c.execute(
        'INSERT INTO personal_records(guild_id,user_id,record_name,best_value) VALUES(?,?,?,?) '
        'ON CONFLICT(guild_id,user_id,record_name) DO UPDATE SET best_value=excluded.best_value',
        (g,u,record_name,int(value))
    )
    c.commit(); c.close()

def log_record_event(g,u,record_name,value,date_text):
    try:
        d=datetime.strptime(date_text,'%Y-%m-%d').date()
    except ValueError:
        d=now().date()
        date_text=d.isoformat()
    c=con()
    c.execute(
        'INSERT INTO record_events(guild_id,user_id,record_name,value,local_date,week_key,created_at) VALUES(?,?,?,?,?,?,?)',
        (g,u,record_name,int(value),date_text,wkey(d),datetime.now(timezone.utc).isoformat())
    )
    c.commit(); c.close()

async def check_daily_personal_best(guild,user_id,record_name,current_value,label,emoji):
    old=get_personal_best(guild.id,user_id,record_name)

    # Initialize silently the first time so the bot does not call a person's
    # very first single appointment/sale a "personal best".
    # Don't establish or announce appointment personal bests until the rep
    # reaches at least 3 appointments in a day. This prevents 1-2 appointments
    # from becoming a misleading "personal best" for reps with incomplete history.
    if record_name=='daily_appointments' and current_value<=2:
        return

    if old==0:
        set_personal_best(guild.id,user_id,record_name,current_value)
        return

    if current_value<=old:
        return

    set_personal_best(guild.id,user_id,record_name,current_value)
    log_record_event(guild.id,user_id,record_name,current_value,dkey())
    member=guild.get_member(user_id)
    if member:
        await main(
            guild,
            content=f'{emoji} **NEW PERSONAL BEST!** {member.mention} just hit **{current_value} {label} in one day!** Previous best: **{old}**.'
        )

def setter_sales_today(g,u):
    today=dkey()
    c=con()
    n=c.execute(
        'SELECT COUNT(*) c FROM sale_events WHERE guild_id=? AND setter_id=? AND local_date=?',
        (g,u,today)
    ).fetchone()['c']
    a=c.execute(
        'SELECT COALESCE(SUM(amount),0) v FROM stat_adjustments WHERE guild_id=? AND user_id=? AND stat_name=? AND local_date=?',
        (g,u,'sales',today)
    ).fetchone()['v']
    c.close()
    return max(0,int(n+(a or 0)))

def appointments_today_for_user(g,u):
    return period_total_for_user(g,u,'appointments',dkey(),dkey())

def has_any_sale_credit(g,u,kind):
    c=con()
    if kind=='setter':
        r=c.execute('SELECT COUNT(*) c FROM sale_events WHERE guild_id=? AND setter_id=?',(g,u)).fetchone()
        a=c.execute('SELECT COALESCE(SUM(amount),0) v FROM stat_adjustments WHERE guild_id=? AND user_id=? AND stat_name=?',(g,u,'sales')).fetchone()
    else:
        r=c.execute('SELECT COUNT(*) c FROM sale_events WHERE guild_id=? AND closer_id=?',(g,u)).fetchone()
        a=c.execute('SELECT COALESCE(SUM(amount),0) v FROM stat_adjustments WHERE guild_id=? AND user_id=? AND stat_name=?',(g,u,'closer_sales')).fetchone()
    c.close()
    return int((r['c'] or 0)+(a['v'] or 0))

async def check_first_sale(guild,user_id,kind):
    # Only announce when total credited sales reaches exactly 1.
    total=has_any_sale_credit(guild.id,user_id,kind)
    if total!=1:
        return
    key=f'first_sale_{kind}_{user_id}'
    if meta_get(guild.id,key):
        return
    meta_set(guild.id,key,'1')
    member=guild.get_member(user_id)
    if not member:
        return
    if kind=='setter':
        await main(guild,content=f'💰 **FIRST SALE!** {member.mention} just got their first setter sale for **Chosen Genesis**! 🔥')
    else:
        await main(guild,content=f'🤝 **FIRST CLOSE!** {member.mention} just got their first closer sale for **Chosen Genesis**! 🔥')

def week_date_bounds_from_key(week_key):
    year=int(week_key[:4]); week=int(week_key[-2:])
    start=date.fromisocalendar(year,week,1)
    end=date.fromisocalendar(year,week,7)
    return start.isoformat(),end.isoformat()

def team_week_total(g,week_key,kind):
    start,end=week_date_bounds_from_key(week_key)
    c=con()
    if kind=='appointments':
        base=c.execute(
            'SELECT COUNT(*) c FROM appointment_events WHERE guild_id=? AND local_date BETWEEN ? AND ?',
            (g,start,end)
        ).fetchone()['c']
        adj=c.execute(
            'SELECT COALESCE(SUM(amount),0) v FROM stat_adjustments WHERE guild_id=? AND stat_name=? AND local_date BETWEEN ? AND ?',
            (g,'appointments',start,end)
        ).fetchone()['v']
    else:
        base=c.execute(
            'SELECT COUNT(*) c FROM sale_events WHERE guild_id=? AND local_date BETWEEN ? AND ?',
            (g,start,end)
        ).fetchone()['c']
        adj=c.execute(
            'SELECT COALESCE(SUM(amount),0) v FROM team_sale_adjustments WHERE guild_id=? AND local_date BETWEEN ? AND ?',
            (g,start,end)
        ).fetchone()['v']
    c.close()
    return max(0,int((base or 0)+(adj or 0)))

def week_metric_winners(g,week_key,metric):
    start,end=week_date_bounds_from_key(week_key)
    c=con(); totals={}
    if metric=='bills':
        rows=c.execute(
            'SELECT setter_id user_id,COALESCE(SUM(bill_collected),0) value FROM appointment_events '
            'WHERE guild_id=? AND local_date BETWEEN ? AND ? GROUP BY setter_id',
            (g,start,end)
        ).fetchall()
        stat='bills'
    elif metric=='same_day':
        rows=c.execute(
            'SELECT setter_id user_id,COALESCE(SUM(same_day),0) value FROM appointment_events '
            'WHERE guild_id=? AND local_date BETWEEN ? AND ? GROUP BY setter_id',
            (g,start,end)
        ).fetchall()
        stat='same_day'
    else:
        c.close(); return [],0
    for r in rows:
        totals[r['user_id']]=float(r['value'] or 0)
    adj=c.execute(
        'SELECT user_id,COALESCE(SUM(amount),0) value FROM stat_adjustments '
        'WHERE guild_id=? AND stat_name=? AND local_date BETWEEN ? AND ? GROUP BY user_id',
        (g,stat,start,end)
    ).fetchall()
    c.close()
    for r in adj:
        totals[r['user_id']]=max(0,totals.get(r['user_id'],0)+float(r['value'] or 0))
    totals={u:v for u,v in totals.items() if v>0}
    if not totals:
        return [],0
    best=max(totals.values())
    return [u for u,v in totals.items() if v==best],int(best)

async def weekly_recap(guild,week_key):
    if meta_get(guild.id,'weekly_recap_posted')==week_key:
        return

    appts=team_week_total(guild.id,week_key,'appointments')
    sales=team_week_total(guild.id,week_key,'sales')
    setters,setter_count,setter_appts,_=setter_king_winners(guild.id,week_key)
    closers,closer_count,_=king_winners(guild.id,week_key,'closer')
    bill_winners,bill_count=week_metric_winners(guild.id,week_key,'bills')
    sd_winners,sd_count=week_metric_winners(guild.id,week_key,'same_day')

    c=con()
    badge_count=c.execute(
        'SELECT COUNT(*) c FROM badge_awards WHERE guild_id=? AND award_key=?',
        (guild.id,week_key)
    ).fetchone()['c']
    # Daily badge award keys are dates, so also count awards whose dates fall inside the week.
    start,end=week_date_bounds_from_key(week_key)
    badge_daily=c.execute(
        'SELECT COUNT(*) c FROM badge_awards WHERE guild_id=? AND award_key BETWEEN ? AND ?',
        (guild.id,start,end)
    ).fetchone()['c']
    pb_count=c.execute(
        'SELECT COUNT(*) c FROM record_events WHERE guild_id=? AND week_key=?',
        (guild.id,week_key)
    ).fetchone()['c']
    c.close()

    def names(ids):
        return ', '.join((guild.get_member(x).display_name if guild.get_member(x) else f'<@{x}>') for x in ids) or 'No winner'

    e=discord.Embed(
        title='🏆 CHOSEN GENESIS — WEEKLY RECAP',
        description=f'**{week_key}**',
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(name='📅 Team Appointments',value=f'**{appts}**',inline=True)
    e.add_field(name='💰 Team Sales',value=f'**{sales}**',inline=True)
    e.add_field(name='🔥 Personal Bests',value=f'**{int(pb_count or 0)}** broken',inline=True)
    e.add_field(name='👑 Setter King',value=f'**{names(setters)}** — {setter_count} setter sales' + (f' • {max((setter_appts.get(x,0) for x in setters),default=0)} appointments' if setters else ''),inline=False)
    e.add_field(name='👑 Closer King',value=f'**{names(closers)}** — {closer_count} sales',inline=False)
    e.add_field(name='📄 Most Bills',value=f'**{names(bill_winners)}** — {bill_count}',inline=True)
    e.add_field(name='⚡ Most Same Days',value=f'**{names(sd_winners)}** — {sd_count}',inline=True)
    e.add_field(name='🏅 Badges Earned',value=f'**{int((badge_count or 0)+(badge_daily or 0))}**',inline=True)
    e.set_footer(text='New week. Same mission.')
    await main(guild,embed=e)
    meta_set(guild.id,'weekly_recap_posted',week_key)



def first_setter_for_date(g,date_text):
    c=con()
    r=c.execute(
        'SELECT setter_id FROM appointment_events WHERE guild_id=? AND local_date=? ORDER BY id ASC LIMIT 1',
        (g,date_text)
    ).fetchone()
    c.close()
    return r['setter_id'] if r else None

def daily_team_sales(g,date_text):
    c=con()
    base=c.execute(
        'SELECT COUNT(*) c FROM sale_events WHERE guild_id=? AND local_date=?',
        (g,date_text)
    ).fetchone()['c']
    manual=c.execute(
        'SELECT COALESCE(SUM(amount),0) v FROM team_sale_adjustments WHERE guild_id=? AND local_date=?',
        (g,date_text)
    ).fetchone()['v']
    c.close()
    return max(0,int((base or 0)+(manual or 0)))

def daily_team_appointments_for_date(g,date_text):
    totals=daily_metric_totals_for_date(g,'appointments',date_text)
    return int(sum(max(0,v) for v in totals.values()))

def sale_badge_holders_for_date(g,date_text,badge):
    c=con()
    rows=c.execute(
        'SELECT DISTINCT user_id FROM badge_awards '
        'WHERE guild_id=? AND badge_name=? AND award_key=? ORDER BY user_id',
        (g,badge,date_text)
    ).fetchall()
    c.close()
    return [r['user_id'] for r in rows]

def member_names(guild,ids):
    names=[]
    for uid in ids:
        member=guild.get_member(uid)
        names.append(member.display_name if member else f'<@{uid}>')
    return ', '.join(names) if names else 'None'

async def finalize_daily_competitive_badges(guild,date_text):
    point_uid,point_count,_=point_man_result(guild.id,date_text)
    if point_uid:
        await set_holders(guild,'🎯 Point Man',[point_uid])
        if award_badge_count(guild.id,point_uid,'🎯 Point Man',date_text):
            await announce_badge_milestone(guild,point_uid,'🎯 Point Man')
    else:
        await set_holders(guild,'🎯 Point Man',[])

    final={}
    for metric,badge in [
        ('bills','📄 Bounty Hunter'),
        ('same_day','⚡ Same Day Savage'),
        ('within_48','⏰ Speed Demon')
    ]:
        leaders=daily_leaders_for_date(guild.id,metric,date_text)
        await set_holders(guild,badge,leaders)
        for uid in leaders:
            if award_badge_count(guild.id,uid,badge,date_text):
                await announce_badge_milestone(guild,uid,badge)
        totals=daily_metric_totals_for_date(guild.id,metric,date_text)
        best=max((int(totals.get(uid,0)) for uid in leaders),default=0)
        final[badge]=(leaders,best)

    return point_uid,point_count,final

async def post_daily_awards(guild):
    date_text=dkey()
    key=f'daily_awards_{date_text}'
    if meta_get(guild.id,key):
        return

    appointments=daily_team_appointments_for_date(guild.id,date_text)
    sales=daily_team_sales(guild.id,date_text)

    # Don't post an empty recap on a day nobody worked.
    if appointments<=0 and sales<=0:
        meta_set(guild.id,key,'empty')
        return

    point_uid,point_count,quality_badges=await finalize_daily_competitive_badges(guild,date_text)
    night_uid=await finalize_night_owl(guild,now().date(),set_role=True)
    meta_set(guild.id,'night_owl_finalized',date_text)

    first_uid=first_setter_for_date(guild.id,date_text)

    sale_ids=sale_badge_holders_for_date(guild.id,date_text,'💥 Sale')
    two_ids=sale_badge_holders_for_date(guild.id,date_text,'🥈 2 Spot')
    hat_ids=sale_badge_holders_for_date(guild.id,date_text,'🎩 Hattrick')
    ghost_ids=sale_badge_holders_for_date(guild.id,date_text,'👻 Ghost Hunter')

    e=discord.Embed(
        title='🏆 CHOSEN GENESIS — DAILY AWARDS',
        description=f'**💰🔥 SALES BOARD — {sales} SALE{"S" if sales!=1 else ""} TODAY**',
        timestamp=datetime.now(timezone.utc)
    )

    sales_text=(
        f'💥 **SALE:** {member_names(guild,sale_ids)}\n'
        f'🥈 **2 SPOT:** {member_names(guild,two_ids)}\n'
        f'🎩 **HATTRICK:** {member_names(guild,hat_ids)}\n'
        f'👻 **GHOST HUNTER:** {member_names(guild,ghost_ids)}'
    )
    e.add_field(name='💰 SALES BADGES',value=sales_text,inline=False)

    point_name=member_names(guild,[point_uid]) if point_uid else 'No winner — nobody reached 2 appointments'
    bounty_ids,bounty_val=quality_badges.get('📄 Bounty Hunter',([],0))
    same_ids,same_val=quality_badges.get('⚡ Same Day Savage',([],0))
    speed_ids,speed_val=quality_badges.get('⏰ Speed Demon',([],0))

    comp_text=(
        f'🎯 **POINT MAN:** {point_name}' + (f' — {point_count} appointments' if point_uid else '') + '\n'
        f'📄 **BOUNTY HUNTER:** {member_names(guild,bounty_ids)}' + (f' — {bounty_val} bills' if bounty_ids else '') + '\n'
        f'⚡ **SAME DAY SAVAGE:** {member_names(guild,same_ids)}' + (f' — {same_val} same-days' if same_ids else '') + '\n'
        f'⏰ **SPEED DEMON:** {member_names(guild,speed_ids)}' + (f' — {speed_val} within 48 hrs' if speed_ids else '') + '\n'
        f'🩸 **FIRST BLOOD:** {member_names(guild,[first_uid] if first_uid else [])}\n'
        f'🦉 **NIGHT OWL:** {member_names(guild,[night_uid] if night_uid else [])}'
    )
    e.add_field(name='🎯 DAILY BADGES',value=comp_text,inline=False)

    e.add_field(
        name='📊 CHOSEN GENESIS TODAY',
        value=f'**{appointments} appointments • {sales} sales**',
        inline=False
    )

    closing=random.choice(DAILY_AWARD_CLOSERS).format(
        sales=sales,
        appointments=appointments
    )
    e.add_field(name='🔥 FINAL WORD',value=closing,inline=False)

    await main(guild,embed=e)
    meta_set(guild.id,key,'posted')
    await refresh_leaderboard(guild)

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
        raw=str(custom_date).strip()
        raw=(raw.replace('–','-').replace('—','-').replace('−','-').replace('‑','-').replace('‐','-'))
        raw=''.join(raw.split())
        for fmt in ('%Y-%m-%d','%m/%d/%Y'):
            try: return datetime.strptime(raw,fmt).date()
            except ValueError: pass
        return None
    return today


def daily_metric_totals_for_date(g,metric,date_text):
    c=con(); totals={}
    if metric=='appointments':
        rows=c.execute(
            'SELECT setter_id user_id,COUNT(*) value FROM appointment_events '
            'WHERE guild_id=? AND local_date=? GROUP BY setter_id',
            (g,date_text)
        ).fetchall(); stat='appointments'
    elif metric=='bills':
        rows=c.execute(
            'SELECT setter_id user_id,COALESCE(SUM(bill_collected),0) value FROM appointment_events '
            'WHERE guild_id=? AND local_date=? GROUP BY setter_id',
            (g,date_text)
        ).fetchall(); stat='bills'
    elif metric=='same_day':
        rows=c.execute(
            'SELECT setter_id user_id,COALESCE(SUM(same_day),0) value FROM appointment_events '
            'WHERE guild_id=? AND local_date=? GROUP BY setter_id',
            (g,date_text)
        ).fetchall(); stat='same_day'
    else:
        rows=c.execute(
            'SELECT setter_id user_id,COALESCE(SUM(within_48),0) value FROM appointment_events '
            'WHERE guild_id=? AND local_date=? GROUP BY setter_id',
            (g,date_text)
        ).fetchall(); stat='within_48'

    for r in rows:
        totals[r['user_id']]=float(r['value'] or 0)

    adj=c.execute(
        'SELECT user_id,COALESCE(SUM(amount),0) value FROM stat_adjustments '
        'WHERE guild_id=? AND stat_name=? AND local_date=? GROUP BY user_id',
        (g,stat,date_text)
    ).fetchall()
    c.close()

    for r in adj:
        totals[r['user_id']]=totals.get(r['user_id'],0)+float(r['value'] or 0)

    return {u:max(0,v) for u,v in totals.items()}

def daily_metric_totals(g,metric):
    return daily_metric_totals_for_date(g,metric,dkey())

def daily_leaders_for_date(g,metric,date_text):
    totals=daily_metric_totals_for_date(g,metric,date_text)
    totals={u:v for u,v in totals.items() if v>0}
    if not totals:
        return []
    best=max(totals.values())
    return [u for u,v in totals.items() if v==best]

def daily_leaders(g,metric):
    return daily_leaders_for_date(g,metric,dkey())

def point_man_result(g,date_text=None):
    date_text=date_text or dkey()
    appts=daily_metric_totals_for_date(g,'appointments',date_text)
    eligible={u:int(v) for u,v in appts.items() if v>=2}
    if not eligible:
        return None,0,{'same_day':0,'within_48':0,'bills':0}

    best=max(eligible.values())
    tied=[u for u,v in eligible.items() if v==best]

    quality={}
    same=daily_metric_totals_for_date(g,'same_day',date_text)
    within=daily_metric_totals_for_date(g,'within_48',date_text)
    bills=daily_metric_totals_for_date(g,'bills',date_text)

    # Quality tiebreakers: Same Day -> Within 48 -> Bill.
    best_same=max(int(same.get(u,0)) for u in tied)
    tied=[u for u in tied if int(same.get(u,0))==best_same]

    if len(tied)>1:
        best_within=max(int(within.get(u,0)) for u in tied)
        tied=[u for u in tied if int(within.get(u,0))==best_within]

    if len(tied)>1:
        best_bills=max(int(bills.get(u,0)) for u in tied)
        tied=[u for u in tied if int(bills.get(u,0))==best_bills]

    # Final tiebreaker: whoever reached their final appointment count first.
    if len(tied)>1:
        c=con()
        reached=[]
        for uid in tied:
            rows=c.execute(
                'SELECT created_at,id FROM appointment_events '
                'WHERE guild_id=? AND setter_id=? AND local_date=? ORDER BY id ASC',
                (g,uid,date_text)
            ).fetchall()
            # Use the event that reached the winning count; if manual adjustments
            # created the tie, fall back to the latest actual event.
            idx=min(max(best-1,0),len(rows)-1) if rows else None
            reached_at=rows[idx]['created_at'] if idx is not None else '9999'
            reached_id=rows[idx]['id'] if idx is not None else 10**18
            reached.append((reached_at,reached_id,uid))
        c.close()
        reached.sort(key=lambda x:(x[0],x[1],x[2]))
        tied=[reached[0][2]]

    uid=tied[0]
    quality={
        'same_day':int(same.get(uid,0)),
        'within_48':int(within.get(uid,0)),
        'bills':int(bills.get(uid,0))
    }
    return uid,best,quality

async def refresh_daily_comp(guild):
    # Point Man always has ONE holder and requires at least 2 appointments.
    point_uid,_,_=point_man_result(guild.id,dkey())
    await set_holders(guild,'🎯 Point Man',[point_uid] if point_uid else [])

    # Other daily quality badges can have tied holders.
    for metric,badge in [
        ('bills','📄 Bounty Hunter'),
        ('same_day','⚡ Same Day Savage'),
        ('within_48','⏰ Speed Demon')
    ]:
        leaders=daily_leaders(guild.id,metric)
        await set_holders(guild,badge,leaders)

    # Daily competitive badge history is finalized at 9 PM instead of while
    # the lead is still changing throughout the day.

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
    hot=[u for u in setters if streak(guild.id,u,'appointment_events','setter_id',5)]
    ice=[u for u in closers if streak(guild.id,u,'sale_events','closer_id',3)]
    await set_holders(guild,'🔥 Hot Streak',hot)
    await set_holders(guild,'🧊 Ice Cold',ice)
    for uid in hot:
        if award_badge_count(guild.id,uid,'🔥 Hot Streak',dkey()):
            await announce_badge_milestone(guild,uid,'🔥 Hot Streak')
    for uid in ice:
        if award_badge_count(guild.id,uid,'🧊 Ice Cold',dkey()):
            await announce_badge_milestone(guild,uid,'🧊 Ice Cold')



def week_user_total(g,wk,user_id,stat):
    start_date,end_date=week_date_bounds_from_key(wk)
    return period_total_for_user(g,user_id,stat,start_date,end_date)

def setter_king_winners(g,wk):
    # Setter King:
    # 1) Most setter sales
    # 2) If tied, most appointments
    # 3) If still tied, most badge points
    # 4) If still tied, share the crown
    start_date,end_date=week_date_bounds_from_key(wk)

    c=con()
    user_ids={r['setter_id'] for r in c.execute(
        'SELECT DISTINCT setter_id FROM sale_events WHERE guild_id=? AND local_date BETWEEN ? AND ?',
        (g,start_date,end_date)
    ).fetchall()}
    user_ids.update(r['setter_id'] for r in c.execute(
        'SELECT DISTINCT setter_id FROM appointment_events WHERE guild_id=? AND local_date BETWEEN ? AND ?',
        (g,start_date,end_date)
    ).fetchall())
    user_ids.update(r['user_id'] for r in c.execute(
        'SELECT DISTINCT user_id FROM stat_adjustments WHERE guild_id=? AND local_date BETWEEN ? AND ? AND stat_name IN (?,?)',
        (g,start_date,end_date,'sales','appointments')
    ).fetchall())
    c.close()

    rows=[]
    for uid in user_ids:
        sales=period_total_for_user(g,uid,'sales',start_date,end_date)
        appts=period_total_for_user(g,uid,'appointments',start_date,end_date)
        if sales>0:
            rows.append((uid,sales,appts,weekly_badge_points(g,uid,wk)))

    if not rows:
        return [],0,{},{}

    best_sales=max(r[1] for r in rows)
    tied=[r for r in rows if r[1]==best_sales]

    best_appts=max(r[2] for r in tied)
    tied=[r for r in tied if r[2]==best_appts]

    best_points=max(r[3] for r in tied)
    winners=[r[0] for r in tied if r[3]==best_points]

    appt_map={r[0]:r[2] for r in rows}
    point_map={r[0]:r[3] for r in rows}
    return winners,best_sales,appt_map,point_map

def month_bounds_for_date(d):
    start=d.replace(day=1)
    if start.month==12:
        next_month=start.replace(year=start.year+1,month=1,day=1)
    else:
        next_month=start.replace(month=start.month+1,day=1)
    end=next_month-timedelta(days=1)
    return start.isoformat(),end.isoformat()

def period_rows_between(guild_id,start,end,kind,limit=10):
    c=con(); totals={}
    if kind=='appointments':
        rows=c.execute(
            'SELECT setter_id user_id,COUNT(*) value FROM appointment_events '
            'WHERE guild_id=? AND local_date BETWEEN ? AND ? GROUP BY setter_id',
            (guild_id,start,end)
        ).fetchall(); stat='appointments'
    elif kind=='setter_sales':
        rows=c.execute(
            'SELECT setter_id user_id,COUNT(*) value FROM sale_events '
            'WHERE guild_id=? AND local_date BETWEEN ? AND ? GROUP BY setter_id',
            (guild_id,start,end)
        ).fetchall(); stat='sales'
    elif kind=='closer_sales':
        rows=c.execute(
            'SELECT closer_id user_id,COUNT(*) value FROM sale_events '
            'WHERE guild_id=? AND local_date BETWEEN ? AND ? AND closer_id>0 GROUP BY closer_id',
            (guild_id,start,end)
        ).fetchall(); stat='closer_sales'
    else:
        c.close(); return []

    for r in rows:
        totals[r['user_id']]=float(r['value'] or 0)

    adj=c.execute(
        'SELECT user_id,COALESCE(SUM(amount),0) value FROM stat_adjustments '
        'WHERE guild_id=? AND stat_name=? AND local_date BETWEEN ? AND ? GROUP BY user_id',
        (guild_id,stat,start,end)
    ).fetchall()
    c.close()

    for r in adj:
        totals[r['user_id']]=max(0,totals.get(r['user_id'],0)+float(r['value'] or 0))

    data=sorted(
        ((uid,val) for uid,val in totals.items() if val>0),
        key=lambda x:(-x[1],x[0])
    )[:limit]
    return [{'user_id':uid,'value':int(val) if float(val).is_integer() else val} for uid,val in data]

def team_period_total(g,start,end,kind):
    c=con()
    if kind=='appointments':
        base=c.execute(
            'SELECT COUNT(*) c FROM appointment_events WHERE guild_id=? AND local_date BETWEEN ? AND ?',
            (g,start,end)
        ).fetchone()['c']
        adj=c.execute(
            'SELECT COALESCE(SUM(amount),0) v FROM stat_adjustments '
            'WHERE guild_id=? AND stat_name=? AND local_date BETWEEN ? AND ?',
            (g,'appointments',start,end)
        ).fetchone()['v']
    else:
        base=c.execute(
            'SELECT COUNT(*) c FROM sale_events WHERE guild_id=? AND local_date BETWEEN ? AND ?',
            (g,start,end)
        ).fetchone()['c']
        adj=c.execute(
            'SELECT COALESCE(SUM(amount),0) v FROM team_sale_adjustments '
            'WHERE guild_id=? AND local_date BETWEEN ? AND ?',
            (g,start,end)
        ).fetchone()['v']
    c.close()
    return max(0,int((base or 0)+(adj or 0)))

def fmt_ranked_members(guild,rows,limit=5):
    if not rows:
        return 'No stats.'
    lines=[]
    for i,r in enumerate(rows[:limit],1):
        member=guild.get_member(r['user_id'])
        name=member.display_name if member else f'<@{r["user_id"]}>'
        lines.append(f'**#{i} {name}** — {r["value"]}')
    return '\n'.join(lines)

def week_member_totals(guild,wk,stat):
    start,end=week_date_bounds_from_key(wk)
    out={}
    for member in guild.members:
        if member.bot:
            continue
        value=period_total_for_user(guild.id,member.id,stat,start,end)
        if value>0:
            out[member.id]=value
    return out

async def send_weekly_manager_summary(guild,week_key):
    if meta_get(guild.id,'manager_weekly_sent')==week_key:
        return

    start,end=week_date_bounds_from_key(week_key)
    prev_end=datetime.strptime(start,'%Y-%m-%d').date()-timedelta(days=1)
    prev_wk=wkey(prev_end)

    appts=team_week_total(guild.id,week_key,'appointments')
    sales=team_week_total(guild.id,week_key,'sales')

    top_appts=period_rows_between(guild.id,start,end,'appointments',5)
    top_setter_sales=period_rows_between(guild.id,start,end,'setter_sales',5)
    top_closer_sales=period_rows_between(guild.id,start,end,'closer_sales',5)

    # Week-over-week appointment movement.
    current=week_member_totals(guild,week_key,'appointments')
    previous=week_member_totals(guild,prev_wk,'appointments')
    movers=[]
    for uid in set(current)|set(previous):
        diff=current.get(uid,0)-previous.get(uid,0)
        if diff!=0:
            movers.append((uid,diff,current.get(uid,0),previous.get(uid,0)))
    movers.sort(key=lambda x:(-x[1],-x[2]))

    momentum=[]
    for uid,diff,cur,prev in movers[:5]:
        member=guild.get_member(uid)
        if not member:
            continue
        arrow='⬆️' if diff>0 else '⬇️'
        momentum.append(f'{arrow} **{member.display_name}**: {prev} → {cur} ({diff:+d})')
    momentum_text='\n'.join(momentum) if momentum else 'No meaningful week-over-week changes.'

    # Low appointment activity only for members who currently have the Setter role.
    needs=[]
    for member in guild.members:
        if member.bot:
            continue
        if not any(r.name.lower()=='setter' for r in member.roles):
            continue
        val=period_total_for_user(guild.id,member.id,'appointments',start,end)
        if val<=1:
            needs.append((member.display_name,val))
    needs.sort(key=lambda x:(x[1],x[0].lower()))
    needs_text='\n'.join(f'• **{name}** — {val} appointment{"s" if val!=1 else ""}' for name,val in needs[:8]) or 'No setters at 0–1 appointments.'

    c=con()
    pb_count=c.execute(
        'SELECT COUNT(*) c FROM record_events WHERE guild_id=? AND week_key=?',
        (guild.id,week_key)
    ).fetchone()['c']
    badge_start,badge_end=week_date_bounds_from_key(week_key)
    badge_count=c.execute(
        'SELECT COUNT(*) c FROM badge_awards WHERE guild_id=? '
        'AND (award_key=? OR award_key BETWEEN ? AND ?)',
        (guild.id,week_key,badge_start,badge_end)
    ).fetchone()['c']
    c.close()

    e=discord.Embed(
        title='📋 CHOSEN GENESIS — WEEKLY MANAGER REPORT',
        description=f'Private manager report for **{week_key}**.',
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(
        name='TEAM',
        value=f'📅 Appointments: **{appts}**\n💰 Sales: **{sales}**\n🏅 Badges Earned: **{int(badge_count or 0)}**\n📈 Personal Bests: **{int(pb_count or 0)}**',
        inline=False
    )
    e.add_field(name='📅 TOP 5 APPOINTMENTS',value=fmt_ranked_members(guild,top_appts),inline=False)
    e.add_field(name='💰 TOP 5 SETTER SALES',value=fmt_ranked_members(guild,top_setter_sales),inline=False)
    e.add_field(name='🤝 TOP 5 CLOSER SALES',value=fmt_ranked_members(guild,top_closer_sales),inline=False)
    e.add_field(name='📈 WEEK-OVER-WEEK MOMENTUM',value=momentum_text,inline=False)
    e.add_field(name='⚠️ LOW SETTER ACTIVITY',value=needs_text,inline=False)
    e.set_footer(text='Private manager report • Chosen Genesis')

    managers=[
        m for m in guild.members
        if not m.bot and any(r.name.lower()=='manager' for r in m.roles)
    ]
    for manager in managers:
        try:
            await manager.send(embed=e)
        except (discord.Forbidden,discord.HTTPException):
            pass

    meta_set(guild.id,'manager_weekly_sent',week_key)

async def monthly_recap(guild,month_date):
    start,end=month_bounds_for_date(month_date)
    month_key=month_date.strftime('%Y-%m')
    if meta_get(guild.id,'monthly_recap_posted')==month_key:
        return

    appts=team_period_total(guild.id,start,end,'appointments')
    sales=team_period_total(guild.id,start,end,'sales')
    top_setters=period_rows_between(guild.id,start,end,'setter_sales',5)
    top_closers=period_rows_between(guild.id,start,end,'closer_sales',5)
    top_appts=period_rows_between(guild.id,start,end,'appointments',5)

    c=con()
    badge_count=c.execute(
        'SELECT COUNT(*) c FROM badge_awards WHERE guild_id=? AND award_key BETWEEN ? AND ?',
        (guild.id,start,end)
    ).fetchone()['c']
    pb_count=c.execute(
        'SELECT COUNT(*) c FROM record_events WHERE guild_id=? AND local_date BETWEEN ? AND ?',
        (guild.id,start,end)
    ).fetchone()['c']
    c.close()

    e=discord.Embed(
        title=f'🏆 CHOSEN GENESIS — {month_date.strftime("%B").upper()} RECAP',
        description=f'**{month_date.strftime("%B %Y")} is officially in the books.**',
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(name='📅 Total Appointments',value=f'**{appts}**',inline=True)
    e.add_field(name='💰 Total Sales',value=f'**{sales}**',inline=True)
    e.add_field(name='🔥 Personal Bests',value=f'**{int(pb_count or 0)}**',inline=True)
    e.add_field(name='💰 TOP 5 SETTERS — SALES',value=fmt_ranked_members(guild,top_setters),inline=False)
    e.add_field(name='🤝 TOP 5 CLOSERS — SALES',value=fmt_ranked_members(guild,top_closers),inline=False)
    e.add_field(name='📅 TOP 5 APPOINTMENTS',value=fmt_ranked_members(guild,top_appts),inline=False)
    e.add_field(name='🏅 Badges Earned',value=f'**{int(badge_count or 0)}**',inline=True)

    if sales>=MONTHLY_SALES_GOAL:
        finish=f'**Chosen Genesis finished at {sales}/{MONTHLY_SALES_GOAL} sales. Goal cleared. 🔥**'
    else:
        finish=f'**Chosen Genesis finished at {sales}/{MONTHLY_SALES_GOAL} sales. New month. Run it back.**'
    e.add_field(name='🎯 MONTHLY GOAL',value=finish,inline=False)
    e.set_footer(text="New month. Board resets. Who's taking it next?")
    await main(guild,embed=e)
    meta_set(guild.id,'monthly_recap_posted',month_key)


def weekly_badge_points(g,user_id,wk):
    start_date,end_date=week_date_bounds_from_key(wk)
    c=con()
    rows=c.execute(
        'SELECT badge_name,COUNT(*) c FROM badge_awards '
        'WHERE guild_id=? AND user_id=? AND award_key BETWEEN ? AND ? '
        'GROUP BY badge_name',
        (g,user_id,start_date,end_date)
    ).fetchall()
    c.close()

    total=0
    for r in rows:
        total += int(r['c'] or 0) * int(BADGE_POINT_VALUES.get(r['badge_name'],0))
    return total

def king_winners(g,wk,kind):
    if kind=='setter':
        winners,sales,appt_map,points=setter_king_winners(g,wk)
        return winners,sales,points

    leaders,production=week_winners(g,wk,kind)
    if len(leaders)<=1:
        points={u:weekly_badge_points(g,u,wk) for u in leaders}
        return leaders,production,points

    points={u:weekly_badge_points(g,u,wk) for u in leaders}
    best=max(points.values()) if points else 0
    winners=[u for u in leaders if points.get(u,0)==best]
    return winners,production,points


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
    today=now().date()
    current_week_start=today-timedelta(days=today.weekday())
    prev_week_end=current_week_start-timedelta(days=1)
    wk=wkey(prev_week_end)

    setters,setter_sales,setter_appts,setter_points=setter_king_winners(guild.id,wk)
    closers,closer_score,closer_points=king_winners(guild.id,wk,'closer')

    await set_holders(guild,'👑 Setter King',setters)
    await set_holders(guild,'👑 Closer King',closers)

    for uid in setters:
        if award_badge_count(guild.id,uid,'👑 Setter King',wk):
            await announce_badge_milestone(guild,uid,'👑 Setter King')
    for uid in closers:
        if award_badge_count(guild.id,uid,'👑 Closer King',wk):
            await announce_badge_milestone(guild,uid,'👑 Closer King')

    if meta_get(guild.id,'weekly_awarded')==wk:
        return

    if setters or closers:
        e=discord.Embed(
            title='👑 CHOSEN GENESIS — NEW WEEKLY KINGS',
            description=(
                'Last week is locked. The crowns are live for this week. 🔥\n\n'
                '**Setter King:** setter sales → appointments → badge points.\n'
                '**Closer King:** closer sales → badge points.'
            ),
            timestamp=datetime.now(timezone.utc)
        )

        if setters:
            setter_text=[]
            for uid in setters:
                setter_text.append(
                    f'<@{uid}> — **{setter_sales:g} setter sales** • '
                    f'**{setter_appts.get(uid,0)} appointments** • '
                    f'**{setter_points.get(uid,0)} badge pts**'
                )
            setter_value='\n'.join(setter_text)
        else:
            setter_value='No winner'

        if closers:
            closer_value='\n'.join(
                f'<@{uid}> — **{closer_score:g} closer sales** • **{closer_points.get(uid,0)} badge pts**'
                for uid in closers
            )
        else:
            closer_value='No winner'

        e.add_field(name='👑 Setter King',value=setter_value,inline=False)
        e.add_field(name='👑 Closer King',value=closer_value,inline=False)
        e.set_footer(text='Kings keep the crown role until the next weekly rollover.')
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
    # DAILY roles are cleared on restart/day rollover, so restore today's live
    # Night Owl from the latest appointment already saved in the database.
    await set_live_night_owl(guild,dkey())


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

    # Mobile-safe fixed-width scoreboard formatting.
    # Keep tables symmetrical, but stack Setter Sales and Closer Sales
    # vertically so long names do not wrap or truncate on phones.

    def short_name(name,width=18):
        name=str(name)
        return name if len(name)<=width else name[:width-1]+'…'

    def scoreboard(rs,label='VALUE'):
        if not rs:
            return '```text\nNo stats yet.\n```'

        lines=[f"{'RK':<4} {'NAME':<18} {label:>5}"]
        for i,r in enumerate(rs):
            member=guild.get_member(r['user_id'])
            name=member.display_name if member else f"User {r['user_id']}"
            rank=f"#{i+1}"
            lines.append(f"{rank:<4} {short_name(name):<18} {str(r['value']):>5}")

        return "```text\n" + "\n".join(lines) + "\n```"

    def badge_scoreboard():
        rows=[]
        for badge in DAILY+STREAK+WEEKLY:
            # Night Owl is live: always derive today's current holder directly
            # from the saved appointment events. This makes the leaderboard
            # accurate even after a restart or role-cache delay.
            if badge=='🦉 Night Owl':
                uid=last_setter_for_date(guild.id,dkey())
                if uid:
                    member=guild.get_member(uid)
                    holder_name=member.display_name if member else f'<@{uid}>'
                    rows.append(f"**{badge}** — {holder_name}")
                continue

            role_obj=discord.utils.get(guild.roles,name=badge)
            holders=list(role_obj.members) if role_obj else []
            if not holders:
                continue

            # Keep the badge's actual emoji visible.
            # Normal Discord text is used here because emoji widths can break
            # monospace alignment on mobile.
            holder_names=', '.join(m.display_name for m in holders)
            rows.append(f"**{badge}** — {holder_names}")

        return "\n".join(rows) if rows else "No badges claimed yet."

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

    # WEEKLY
    a=period_rows(guild.id,'week','appointments')
    s=period_rows(guild.id,'week','setter_sales')
    cl=period_rows(guild.id,'week','closer_sales')
    daily_appts=team_daily_appointments(guild.id)
    monthly_sales=team_monthly_sales(guild.id)

    daily_pct=min(100,round(daily_appts/DAILY_APPOINTMENT_GOAL*100))
    monthly_pct=min(100,round(monthly_sales/MONTHLY_SALES_GOAL*100))

    weekly=discord.Embed(
        title='🏆 Chosen Genesis — Weekly Leaderboard',
        description=(
            f'**🎯 DAILY APPOINTMENT GOAL**\n'
            f'`{progress_bar(daily_appts,DAILY_APPOINTMENT_GOAL)}`  '
            f'**{daily_appts}/{DAILY_APPOINTMENT_GOAL} • {daily_pct}%**\n\n'
            f'**💰 MONTHLY SALES GOAL**\n'
            f'`{progress_bar(monthly_sales,MONTHLY_SALES_GOAL)}`  '
            f'**{monthly_sales}/{MONTHLY_SALES_GOAL} • {monthly_pct}%**'
        ),
        timestamp=datetime.now(timezone.utc)
    )
    weekly.add_field(name='📅 THIS WEEK — APPOINTMENTS',value=scoreboard(a,'APPTS'),inline=False)
    weekly.add_field(name='💰 SETTER SALES',value=scoreboard(s,'SALES'),inline=False)
    weekly.add_field(name='🤝 CLOSER SALES',value=scoreboard(cl,'SALES'),inline=False)
    weekly.add_field(name='🏅 CURRENT BADGES',value=badge_scoreboard()+'\nUse **/badgeguide** for badge meanings.',inline=False)
    weekly.set_footer(text='Updates automatically when stats change.')

    # MONTHLY
    ma=period_rows(guild.id,'month','appointments')
    ms=period_rows(guild.id,'month','setter_sales')
    mcl=period_rows(guild.id,'month','closer_sales')

    monthly=discord.Embed(
        title='📆 Chosen Genesis — Monthly Leaderboard',
        description=f'**{now().strftime("%B %Y").upper()}**',
        timestamp=datetime.now(timezone.utc)
    )
    monthly.add_field(name='📅 APPOINTMENTS',value=scoreboard(ma,'APPTS'),inline=False)
    monthly.add_field(name='💰 SETTER SALES',value=scoreboard(ms,'SALES'),inline=False)
    monthly.add_field(name='🤝 CLOSER SALES',value=scoreboard(mcl,'SALES'),inline=False)
    monthly.set_footer(text='Updates automatically when stats change.')

    # YEARLY
    ya=period_rows(guild.id,'year','appointments')
    ys=period_rows(guild.id,'year','setter_sales')
    ycl=period_rows(guild.id,'year','closer_sales')

    yearly=discord.Embed(
        title='🏆 Chosen Genesis — Yearly Leaderboard',
        description=f'**{now().year}**',
        timestamp=datetime.now(timezone.utc)
    )
    yearly.add_field(name='📅 APPOINTMENTS',value=scoreboard(ya,'APPTS'),inline=False)
    yearly.add_field(name='💰 SETTER SALES',value=scoreboard(ys,'SALES'),inline=False)
    yearly.add_field(name='🤝 CLOSER SALES',value=scoreboard(ycl,'SALES'),inline=False)
    yearly.set_footer(text='Updates automatically when stats change.')

    # Yearly -> Monthly -> Weekly, so Weekly remains newest / first seen.
    await upsert_board('yearly_leaderboard_message_id','🏆 Chosen Genesis — Yearly Leaderboard',yearly)
    await upsert_board('monthly_leaderboard_message_id','📆 Chosen Genesis — Monthly Leaderboard',monthly)
    await upsert_board('weekly_leaderboard_message_id','🏆 Chosen Genesis — Weekly Leaderboard',weekly)


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
            prefix=medals[i] if i<3 else f"#{i+1}"
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
async def on_member_join(member):
    if member.bot:
        return
    title,description=random.choice(WELCOME_MESSAGES)
    e=discord.Embed(
        title=title,
        description=description.format(mention=member.mention),
        timestamp=datetime.now(timezone.utc)
    )
    e.set_footer(text='Chosen Genesis')
    await main(member.guild,embed=e)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    for g in bot.guilds:
        if meta_get(g.id,'daily_date')!=dkey(): meta_set(g.id,'daily_date',dkey())
        await restore_daily(g); await refresh_streaks(g)
    for g in bot.guilds:
        await refresh_leaderboard(g)
        if now().weekday()!=6 and now().hour>=21:
            await post_daily_awards(g)
            await refresh_leaderboard(g)
        await weekly_kings(g)
        if now().weekday()==0:
            prev=now().date()-timedelta(days=1)
            prev_wk=wkey(prev)
            await weekly_recap(g,prev_wk)
            await send_weekly_manager_summary(g,prev_wk)
        if now().day==1:
            prev_month_day=now().date().replace(day=1)-timedelta(days=1)
            await monthly_recap(g,prev_month_day)

@tasks.loop(minutes=2)
async def maintenance():
    for g in bot.guilds:
        await finalize_previous_day_badges(g)
        if meta_get(g.id,'daily_date')!=dkey():
            await clear_roles(g,DAILY); meta_set(g.id,'daily_date',dkey()); await restore_daily(g)
        await refresh_streaks(g)

        # Finalize and announce the day's badges at 9 PM Arizona time.
        # Sunday is skipped as the bot's existing workday logic treats it as off.
        if now().weekday()!=6 and now().hour>=21:
            await post_daily_awards(g)

        # Keep cosmetic King roles synced all week.
        await weekly_kings(g)
        if now().weekday()==0:
            prev=now().date()-timedelta(days=1)
            prev_wk=wkey(prev)
            await weekly_recap(g,prev_wk)
            await send_weekly_manager_summary(g,prev_wk)

        # On the first day of a new month, recap the month that just ended.
        if now().day==1:
            prev_month_day=now().date().replace(day=1)-timedelta(days=1)
            await monthly_recap(g,prev_month_day)

@maintenance.before_loop
async def before_maintenance(): await bot.wait_until_ready()

@bot.tree.command(name='appointment',description='Log a new appointment')
@app_commands.describe(
    setter='Who set it',
    bill_collected='Did you collect the electric bill?',
    within_48_hours='Is it within 48 hours?',
    same_day='Is it same day?',
    message='Optional custom message to add to the announcement'
)
async def appointment(
    interaction:discord.Interaction,
    setter:discord.Member,
    bill_collected:bool,
    within_48_hours:bool,
    same_day:bool,
    message:str|None=None
):
    if not interaction.guild: return
    n=now(); g=interaction.guild.id

    c=con()
    c.execute(
        'INSERT INTO appointment_events(guild_id,setter_id,bill_collected,within_48,same_day,local_date,week_key,created_at) '
        'VALUES(?,?,?,?,?,?,?,?)',
        (g,setter.id,int(bill_collected),int(within_48_hours),int(same_day),dkey(n.date()),wkey(n.date()),datetime.now(timezone.utc).isoformat())
    )
    c.commit(); c.close()

    add(g,setter.id,'appointments',1)
    if bill_collected: add(g,setter.id,'bills',1)
    if within_48_hours: add(g,setter.id,'within_48',1)
    if same_day: add(g,setter.id,'same_day',1)

    title,description=pick_announcement(APPOINTMENT_ANNOUNCEMENTS)

    # Keep all team references explicitly as Chosen Genesis.
    description=description.replace('Genesis','Chosen Genesis')
    description=description.replace('Chosen Chosen Genesis','Chosen Genesis')

    custom=''
    if message and message.strip():
        custom='\n\n'+message.strip()[:500]

    e=discord.Embed(
        title=title,
        description=description+custom,
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(name='👤 Setter',value=setter.mention,inline=False)
    e.add_field(name='📄 Bill',value='✅ Collected' if bill_collected else '❌ No')
    e.add_field(name='⏰ Within 48 Hours',value='✅ Yes' if within_48_hours else '❌ No')
    e.add_field(name='⚡ Same Day',value='✅ Yes' if same_day else '❌ No')

    await interaction.response.send_message('Appointment logged ✅',ephemeral=True)
    await main(interaction.guild,embed=e)

    await check_daily_personal_best(
        interaction.guild,setter.id,'daily_appointments',
        appointments_today_for_user(g,setter.id),'appointments','📈'
    )

    if first_setter(g)==setter.id:
        if award_badge_count(g,setter.id,'🩸 First Blood',dkey()):
            await announce_badge_milestone(interaction.guild,setter.id,'🩸 First Blood')
        await set_holders(interaction.guild,'🩸 First Blood',[setter.id])
        await main(interaction.guild,content=f'🩸 **FIRST BLOOD!** {setter.mention} set the first appointment of the day!')

    await refresh_daily_comp(interaction.guild)

    # Low-frequency competitive prompts: max one tie prompt per badge/day.
    await maybe_pressure_message(interaction.guild,'🎯 Point Man','appointments')
    await maybe_pressure_message(interaction.guild,'📄 Bounty Hunter','bills')
    await maybe_pressure_message(interaction.guild,'⚡ Same Day Savage','same_day')
    await maybe_pressure_message(interaction.guild,'⏰ Speed Demon','within_48')
    await maybe_night_owl_watch(interaction.guild,setter.id)
    await set_live_night_owl(interaction.guild,dkey())

    await refresh_streaks(interaction.guild)
    await refresh_leaderboard(interaction.guild)


@bot.tree.command(name='sale',description='Log a new sale')
@app_commands.describe(
    setter='Setter on the deal',
    closer='Closer who closed it (leave blank for outside team)',
    outside_team='Turn on if the closer is from another team',
    utility='APS, SRP, etc.',
    message='Optional message to post with the sale'
)
async def sale(
    interaction:discord.Interaction,
    setter:discord.Member,
    outside_team:bool=False,
    closer:discord.Member|None=None,
    utility:str='Unknown',
    message:str|None=None
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

    title,description=pick_announcement(SALE_ANNOUNCEMENTS)
    description=description.replace('Genesis','Chosen Genesis').replace('Chosen Chosen Genesis','Chosen Genesis')
    e=discord.Embed(title=title,description=description,timestamp=datetime.now(timezone.utc))
    e.add_field(name='🔥 Setter',value=setter.mention)
    e.add_field(name='🤝 Closer',value='**Outside Team**' if outside_team else closer.mention)
    e.add_field(name='⚡ Utility',value=utility.upper())

    if message and message.strip():
        e.description=(e.description or '')+'\n\n'+message.strip()[:500]

    await interaction.response.send_message('Sale logged ✅',ephemeral=True)
    await main(interaction.guild,embed=e)

    await check_first_sale(interaction.guild,setter.id,'setter')
    await check_daily_personal_best(
        interaction.guild,setter.id,'daily_setter_sales',
        setter_sales_today(g,setter.id),'setter sales','💰'
    )

    if not outside_team:
        await check_first_sale(interaction.guild,closer.id,'closer')
        await check_daily_personal_best(
            interaction.guild,closer.id,'daily_closer_sales',
            closer_sales_today(g,closer.id),'closer sales','🤝'
        )

    # Outside-team closers never receive closer stats, streaks, or daily closer badges.
    if not outside_team:
        count=closer_sales_today(g,closer.id)

        if count>=1:
            await add_role(interaction.guild,closer,'💥 Sale')
        if count==1:
            if award_badge_count(g,closer.id,'💥 Sale',dkey()):
                await announce_badge_milestone(interaction.guild,closer.id,'💥 Sale')
            await main(interaction.guild,content=f'💥 **SALE BADGE!** {closer.mention} got a sale today!')

        if count>=2:
            await add_role(interaction.guild,closer,'🥈 2 Spot')
        if count==2:
            if award_badge_count(g,closer.id,'🥈 2 Spot',dkey()):
                await announce_badge_milestone(interaction.guild,closer.id,'🥈 2 Spot')
            await main(interaction.guild,content=f'🥈 **2 SPOT!** {closer.mention} has **2 sales today!**')

        if count>=3:
            await add_role(interaction.guild,closer,'🎩 Hattrick')
        if count==3:
            if award_badge_count(g,closer.id,'🎩 Hattrick',dkey()):
                await announce_badge_milestone(interaction.guild,closer.id,'🎩 Hattrick')
            await main(interaction.guild,content=f'🎩 **HATTRICK!** {closer.mention} has **3 sales today!** 🔥')

        if n.hour>=19:
            await add_role(interaction.guild,closer,'👻 Ghost Hunter')
            if award_badge_count(g,closer.id,'👻 Ghost Hunter',dkey()):
                await announce_badge_milestone(interaction.guild,closer.id,'👻 Ghost Hunter')
                await main(interaction.guild,content=f'👻 **GHOST HUNTER!** {closer.mention} closed a deal after 7 PM!')

    await refresh_streaks(interaction.guild)
    await refresh_leaderboard(interaction.guild)



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
    today=now().date().isoformat()
    wstart,wend=current_week_bounds()
    mstart,mend=current_month_bounds()
    ystart,yend=current_year_bounds()

    today_appts=period_total_for_user(interaction.guild.id,member.id,'appointments',today,today)
    week_appts=period_total_for_user(interaction.guild.id,member.id,'appointments',wstart,wend)
    month_appts=period_total_for_user(interaction.guild.id,member.id,'appointments',mstart,mend)
    year_appts=period_total_for_user(interaction.guild.id,member.id,'appointments',ystart,yend)

    week_setter=period_total_for_user(interaction.guild.id,member.id,'sales',wstart,wend)
    month_setter=period_total_for_user(interaction.guild.id,member.id,'sales',mstart,mend)
    year_setter=period_total_for_user(interaction.guild.id,member.id,'sales',ystart,yend)

    week_closer=period_total_for_user(interaction.guild.id,member.id,'closer_sales',wstart,wend)
    month_closer=period_total_for_user(interaction.guild.id,member.id,'closer_sales',mstart,mend)
    year_closer=period_total_for_user(interaction.guild.id,member.id,'closer_sales',ystart,yend)

    c=con()
    saved=c.execute('SELECT * FROM stats WHERE guild_id=? AND user_id=?',(interaction.guild.id,member.id)).fetchone()
    c.close()
    all_appts=int(saved['appointments']) if saved else 0
    all_setter=int(saved['sales']) if saved else 0
    all_closer=int(saved['closer_sales']) if saved else 0

    counts=badge_counts(interaction.guild.id,member.id)
    badge_lines=[]
    for badge in DAILY+STREAK+WEEKLY:
        count=counts.get(badge,0)
        if count:
            badge_lines.append(f"**{badge} ×{count}**\n{BADGE_DESCRIPTIONS.get(badge,'')}")
    badges_text='\n\n'.join(badge_lines) if badge_lines else 'No badges earned yet.'

    e=discord.Embed(
        title=f'👤 MY STATS — {member.display_name.upper()}',
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(
        name='📅 APPOINTMENTS',
        value=(
            f'Today: **{today_appts}**\n'
            f'This Week: **{week_appts}**\n'
            f'This Month: **{month_appts}**\n'
            f'This Year: **{year_appts}**'
        ),inline=False
    )
    e.add_field(
        name='💰 SETTER SALES',
        value=(
            f'This Week: **{week_setter}**\n'
            f'This Month: **{month_setter}**\n'
            f'This Year: **{year_setter}**'
        ),inline=True
    )
    e.add_field(
        name='🤝 CLOSER SALES',
        value=(
            f'This Week: **{week_closer}**\n'
            f'This Month: **{month_closer}**\n'
            f'This Year: **{year_closer}**'
        ),inline=True
    )
    e.add_field(
        name='🏅 MY BADGES',
        value=badges_text,
        inline=False
    )
    e.add_field(
        name='📊 ALL-TIME',
        value=(
            f'Appointments: **{all_appts}**\n'
            f'Setter Sales: **{all_setter}**\n'
            f'Closer Sales: **{all_closer}**'
        ),inline=False
    )
    e.set_footer(text='Only you can see this dashboard. • Use /badgeguide for all badge meanings.')
    await interaction.response.send_message(embed=e,ephemeral=True)


@bot.tree.command(name='badgeguide',description='See every Chosen Genesis badge and what it means')
async def badgeguide(interaction:discord.Interaction):
    e=discord.Embed(
        title='🏅 CHOSEN GENESIS — BADGE GUIDE',
        description='Every badge and how it is earned.'
    )
    sections=[
        ('☀️ DAILY BADGES',DAILY),
        ('🔥 STREAK BADGES',STREAK),
        ('👑 WEEKLY BADGES',WEEKLY)
    ]
    for title,badges in sections:
        text='\n\n'.join(f'**{badge}**\n{BADGE_DESCRIPTIONS.get(badge,"")}' for badge in badges)
        e.add_field(name=title,value=text,inline=False)
    await interaction.response.send_message(embed=e,ephemeral=False)


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
    date='Historical sale date, e.g. 2026-08-01',
    setter='Optional setter to credit',
    closer='Optional team closer to credit',
    outside_team='Turn on only if the closer was outside your team',
    count_team_goal='Should these sales add to the 30-sale team goal?',
)
async def backfillsales(
    interaction:discord.Interaction,
    amount:int,
    date:str,
    setter:discord.Member|None=None,
    closer:discord.Member|None=None,
    outside_team:bool=False,
    count_team_goal:bool=True
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

    # Backfill is historical, so use one simple date field instead of
    # a Date dropdown plus a separate Custom Date field.
    raw_date=str(date).strip()
    raw_date=(raw_date.replace('–','-').replace('—','-').replace('−','-').replace('‑','-').replace('‐','-'))
    raw_date=''.join(raw_date.split())
    edit_date=None
    for fmt in ('%Y-%m-%d','%m/%d/%Y'):
        try:
            edit_date=datetime.strptime(raw_date,fmt).date()
            break
        except ValueError:
            pass
    if not edit_date:
        return await interaction.response.send_message(
            "❌ I couldn't read that date. Use **2026-08-19** or **08/19/2026**.",
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

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
    await interaction.followup.send(
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
            "❌ I couldn't read that date. Use **2026-08-19** or **08/19/2026**.",
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

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

    await interaction.followup.send(
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
        return await interaction.response.send_message("❌ I couldn't read that date. Use **2026-08-19** or **08/19/2026**.",ephemeral=True)

    field=stat.value
    allowed={'appointments','bills','within_48','same_day','sales','closer_sales','pitches','hours'}
    if field not in allowed:
        return await interaction.response.send_message('Invalid stat.',ephemeral=True)

    await interaction.response.defer(ephemeral=True)

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
    await interaction.followup.send(
        f"✅ {member.mention}'s **{labels[field]}** is now **{new_value:g}**. The {delta:+g} correction counts on **{edit_date.isoformat()}**.",
        ephemeral=True
    )


if not TOKEN: raise RuntimeError('DISCORD_TOKEN environment variable is missing')
bot.run(TOKEN)
