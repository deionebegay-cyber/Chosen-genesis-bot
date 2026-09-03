import os, sqlite3, random, calendar
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
import discord
from discord import app_commands
from discord.ext import commands, tasks

TOKEN=os.getenv('DISCORD_TOKEN')
DATA_PATH=os.getenv('DATA_PATH','genesis.db')
GUILD_ID=os.getenv('GUILD_ID')
TZ=ZoneInfo('America/Phoenix')

# Setter check-in standards.
# Regular setters: 10:00 AM target with a 20-minute grace period.
# Earned Freedom: 4+ setter deals in the PREVIOUS month allows check-in through
# 11:35 AM (11:30 target + 5-minute grace) for the entire current month.
REGULAR_CHECKIN_HOUR=10
REGULAR_CHECKIN_MINUTE=0
REGULAR_GRACE_MINUTES=20
FREEDOM_REQUIRED_DEALS=4
FREEDOM_CUTOFF_HOUR=11
FREEDOM_CUTOFF_MINUTE=30
FREEDOM_GRACE_MINUTES=5

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
    CREATE TABLE IF NOT EXISTS checkins(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      guild_id INTEGER,user_id INTEGER,local_date TEXT,local_time TEXT,
      photo_url TEXT,photo_filename TEXT,created_at TEXT,
      UNIQUE(guild_id,user_id,local_date));
    CREATE TABLE IF NOT EXISTS checkouts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      guild_id INTEGER,user_id INTEGER,local_date TEXT,local_time TEXT,
      photo_url TEXT,photo_filename TEXT,created_at TEXT,
      UNIQUE(guild_id,user_id,local_date));
    CREATE TABLE IF NOT EXISTS checkout_records(
      guild_id INTEGER,user_id INTEGER,local_date TEXT,status TEXT,
      checkout_time TEXT,created_at TEXT,
      PRIMARY KEY(guild_id,user_id,local_date));
    CREATE TABLE IF NOT EXISTS member_state(
      guild_id INTEGER,user_id INTEGER,joined_date TEXT,
      onboarding INTEGER DEFAULT 1,graduated_date TEXT,
      PRIMARY KEY(guild_id,user_id));
    CREATE TABLE IF NOT EXISTS attendance_records(
      guild_id INTEGER,user_id INTEGER,local_date TEXT,status TEXT,
      checkin_time TEXT,earned_freedom INTEGER DEFAULT 0,created_at TEXT,
      PRIMARY KEY(guild_id,user_id,local_date));
    CREATE TABLE IF NOT EXISTS weekly_credit_overrides(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      guild_id INTEGER,user_id INTEGER,role_type TEXT,amount INTEGER,
      source_date TEXT,credit_week_key TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS challenges(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      guild_id INTEGER,name TEXT,challenge_type TEXT,scope TEXT,metric TEXT,
      terms TEXT,goal INTEGER,prize TEXT,end_mode TEXT,end_behavior TEXT,
      deadline_at TEXT,status TEXT DEFAULT 'active',winner_id INTEGER,
      created_by INTEGER,created_at TEXT,ended_at TEXT,
      channel_id INTEGER,message_id INTEGER);
    CREATE TABLE IF NOT EXISTS challenge_participants(
      challenge_id INTEGER,user_id INTEGER,score INTEGER DEFAULT 0,
      PRIMARY KEY(challenge_id,user_id));
    CREATE TABLE IF NOT EXISTS challenge_adjustments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      challenge_id INTEGER,guild_id INTEGER,user_id INTEGER,amount INTEGER,
      reason TEXT,adjusted_by INTEGER,created_at TEXT);
    CREATE TABLE IF NOT EXISTS greenie_progress(
      guild_id INTEGER,user_id INTEGER,
      pitch_url TEXT,pitch_filename TEXT,pitch_submitted_at TEXT,
      pitch_approved INTEGER DEFAULT 0,pitch_approved_by INTEGER,pitch_approved_at TEXT,
      graduation_requested INTEGER DEFAULT 0,graduation_requested_at TEXT,
      PRIMARY KEY(guild_id,user_id));
    CREATE TABLE IF NOT EXISTS bootcamp_submissions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      guild_id INTEGER,user_id INTEGER,submitted_at TEXT,
      status TEXT DEFAULT 'pending',reviewed_by INTEGER,reviewed_at TEXT);
    CREATE TABLE IF NOT EXISTS pitch_submissions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      guild_id INTEGER,user_id INTEGER,video_url TEXT,filename TEXT,
      submitted_at TEXT,status TEXT DEFAULT 'pending',
      reviewed_by INTEGER,reviewed_at TEXT,rejection_reason TEXT);
    ''')
    # Appointment photo support (safe migration for existing Railway databases).
    appt_cols={r['name'] for r in c.execute('PRAGMA table_info(appointment_events)')}
    if 'photo_url' not in appt_cols:
        c.execute('ALTER TABLE appointment_events ADD COLUMN photo_url TEXT')
    if 'photo_filename' not in appt_cols:
        c.execute('ALTER TABLE appointment_events ADD COLUMN photo_filename TEXT')

    # migrate old v1 stats safely
    cols={r['name'] for r in c.execute('PRAGMA table_info(stats)')}
    for name,typ in [('closer_sales','INTEGER DEFAULT 0'),('bills','INTEGER DEFAULT 0'),('within_48','INTEGER DEFAULT 0'),('same_day','INTEGER DEFAULT 0')]:
        if name not in cols: c.execute(f'ALTER TABLE stats ADD COLUMN {name} {typ}')
    c.commit(); c.close()

def now(): return datetime.now(TZ)
def awards_now(): return datetime.now(ZoneInfo('America/Phoenix'))
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


def is_image_attachment(att):
    content_type=(att.content_type or '').lower()
    if content_type.startswith('image/'):
        return True
    name=(att.filename or '').lower()
    return name.endswith(('.png','.jpg','.jpeg','.webp','.gif','.heic','.heif'))

def get_today_checkin(guild_id,user_id):
    c=con()
    row=c.execute(
        'SELECT * FROM checkins WHERE guild_id=? AND user_id=? AND local_date=?',
        (guild_id,user_id,dkey())
    ).fetchone()
    c.close()
    return row

def today_checkins(guild_id):
    c=con()
    rows=c.execute(
        'SELECT * FROM checkins WHERE guild_id=? AND local_date=? ORDER BY local_time ASC,id ASC',
        (guild_id,dkey())
    ).fetchall()
    c.close()
    return rows

CHECKOUT_EARLIEST_HOUR=19
CHECKOUT_EARLIEST_MINUTE=50

def get_today_checkout(guild_id,user_id):
    c=con()
    row=c.execute(
        'SELECT * FROM checkouts WHERE guild_id=? AND user_id=? AND local_date=?',
        (guild_id,user_id,dkey())
    ).fetchone()
    c.close()
    return row

def today_checkouts(guild_id):
    c=con()
    rows=c.execute(
        'SELECT * FROM checkouts WHERE guild_id=? AND local_date=? ORDER BY id ASC',
        (guild_id,dkey())
    ).fetchall()
    c.close()
    return rows

def checkout_is_open(dt=None):
    dt=dt or now()
    return minutes_since_midnight(dt.hour,dt.minute) >= minutes_since_midnight(
        CHECKOUT_EARLIEST_HOUR,CHECKOUT_EARLIEST_MINUTE
    )

def upsert_checkout_record(guild,member,date_text,status,checkout_time=None):
    # Only graduated Setters are held accountable for checkout.
    try:
        day=datetime.strptime(date_text,'%Y-%m-%d').date()
    except ValueError:
        return
    if not is_workday(day) or is_greenie(member) or not has_named_role(member,'Setter'):
        return

    c=con()
    c.execute(
        'INSERT INTO checkout_records(guild_id,user_id,local_date,status,checkout_time,created_at) '
        'VALUES(?,?,?,?,?,?) '
        'ON CONFLICT(guild_id,user_id,local_date) DO UPDATE SET '
        'status=excluded.status,checkout_time=excluded.checkout_time',
        (
            guild.id,member.id,date_text,status,checkout_time,
            datetime.now(timezone.utc).isoformat()
        )
    )
    c.commit(); c.close()

def finalize_missed_checkouts_for_date(guild,date_obj):
    if not is_workday(date_obj):
        return
    date_text=date_obj.isoformat()
    for member in guild.members:
        if member.bot or not has_named_role(member,'Setter') or is_greenie(member):
            continue
        c=con()
        row=c.execute(
            'SELECT 1 FROM checkouts WHERE guild_id=? AND user_id=? AND local_date=? LIMIT 1',
            (guild.id,member.id,date_text)
        ).fetchone()
        c.close()
        if not row:
            upsert_checkout_record(guild,member,date_text,'missed',None)


def ensure_member_state(guild_id,user_id,joined_date=None):
    joined_date=joined_date or dkey()
    c=con()
    c.execute(
        'INSERT OR IGNORE INTO member_state(guild_id,user_id,joined_date,onboarding) VALUES(?,?,?,1)',
        (guild_id,user_id,joined_date)
    )
    c.commit(); c.close()

def get_member_state(guild_id,user_id):
    ensure_member_state(guild_id,user_id)
    c=con()
    row=c.execute(
        'SELECT * FROM member_state WHERE guild_id=? AND user_id=?',
        (guild_id,user_id)
    ).fetchone()
    c.close()
    return row

def is_onboarding(guild_id,user_id):
    row=get_member_state(guild_id,user_id)
    return bool(row and int(row['onboarding'] or 0)==1)

def is_workday(date_obj=None):
    date_obj=date_obj or now().date()
    return date_obj.weekday()!=6  # Sunday off

def upsert_attendance(guild,member,date_text,status,checkin_time=None):
    try:
        d=datetime.strptime(date_text,'%Y-%m-%d').date()
    except ValueError:
        return

    # Never create attendance accountability records for Greenies.
    if not is_workday(d) or is_greenie(member) or not has_named_role(member,'Setter'):
        return
    earned=1 if has_earned_freedom(guild.id,member.id) else 0
    c=con()
    c.execute(
        'INSERT INTO attendance_records(guild_id,user_id,local_date,status,checkin_time,earned_freedom,created_at) '
        'VALUES(?,?,?,?,?,?,?) '
        'ON CONFLICT(guild_id,user_id,local_date) DO UPDATE SET '
        'status=excluded.status,checkin_time=excluded.checkin_time,earned_freedom=excluded.earned_freedom',
        (guild.id,member.id,date_text,status,checkin_time,earned,datetime.now(timezone.utc).isoformat())
    )
    c.commit(); c.close()

def attendance_status_for_checkin(guild,member,dt):
    if not is_workday(dt.date()):
        return 'off_day'

    # Greenie role is the source of truth:
    # Greenies may still check in and log production, but attendance does not
    # count until they graduate and become a Setter.
    if is_greenie(member):
        return 'greenie'

    # Attendance accountability applies to Setters only.
    if not has_named_role(member,'Setter'):
        return 'not_applicable'

    status,_,_=checkin_status_for_member(guild,member,dt)
    return 'late' if status=='late' else 'on_time'

def finalize_missed_checkins_for_date(guild,date_obj):
    if not is_workday(date_obj):
        return
    date_text=date_obj.isoformat()
    for member in guild.members:
        if member.bot or not has_named_role(member,'Setter'):
            continue
        if is_greenie(member):
            continue
        c=con()
        row=c.execute(
            'SELECT 1 FROM checkins WHERE guild_id=? AND user_id=? AND local_date=? LIMIT 1',
            (guild.id,member.id,date_text)
        ).fetchone()
        c.close()
        if not row:
            upsert_attendance(guild,member,date_text,'missed',None)

def current_week_key():
    return wkey(now().date())

def weekly_override_total(g,user_id,role_type,wk):
    c=con()
    row=c.execute(
        'SELECT COALESCE(SUM(amount),0) v FROM weekly_credit_overrides '
        'WHERE guild_id=? AND user_id=? AND role_type=? AND credit_week_key=?',
        (g,user_id,role_type,wk)
    ).fetchone()
    c.close()
    return int(row['v'] or 0)


def has_named_role(member,name):
    return isinstance(member,discord.Member) and any(r.name.lower()==name.lower() for r in member.roles)

def is_greenie(member):
    return has_named_role(member,'Greenie')

def ensure_greenie_progress(guild_id,user_id):
    c=con()
    c.execute(
        'INSERT OR IGNORE INTO greenie_progress(guild_id,user_id) VALUES(?,?)',
        (guild_id,user_id)
    )
    c.commit(); c.close()

def greenie_progress(guild_id,user_id):
    ensure_greenie_progress(guild_id,user_id)
    c=con()
    row=c.execute(
        'SELECT * FROM greenie_progress WHERE guild_id=? AND user_id=?',
        (guild_id,user_id)
    ).fetchone()
    c.close()
    return row

def latest_pitch_submission(guild_id,user_id):
    c=con()
    row=c.execute(
        'SELECT * FROM pitch_submissions WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 1',
        (guild_id,user_id)
    ).fetchone()
    c.close()
    return row

def pending_pitch_submission(guild_id,user_id):
    c=con()
    row=c.execute(
        "SELECT * FROM pitch_submissions WHERE guild_id=? AND user_id=? AND status='pending' ORDER BY id DESC LIMIT 1",
        (guild_id,user_id)
    ).fetchone()
    c.close()
    return row

def pitch_history_count(guild_id,user_id):
    c=con()
    row=c.execute(
        'SELECT COUNT(*) c FROM pitch_submissions WHERE guild_id=? AND user_id=?',
        (guild_id,user_id)
    ).fetchone()
    c.close()
    return int(row['c'] or 0)

def approved_bootcamp_count(guild_id,user_id):
    c=con()
    row=c.execute(
        "SELECT COUNT(*) c FROM bootcamp_submissions WHERE guild_id=? AND user_id=? AND status='approved'",
        (guild_id,user_id)
    ).fetchone()
    c.close()
    return int(row['c'] or 0)

def pending_bootcamp_count(guild_id,user_id):
    c=con()
    row=c.execute(
        "SELECT COUNT(*) c FROM bootcamp_submissions WHERE guild_id=? AND user_id=? AND status='pending'",
        (guild_id,user_id)
    ).fetchone()
    c.close()
    return int(row['c'] or 0)

def greenie_ready(guild_id,user_id):
    p=greenie_progress(guild_id,user_id)
    return approved_bootcamp_count(guild_id,user_id)>=3 and bool(int(p['pitch_approved'] or 0))

def greenie_stats(guild_id,user_id):
    c=con()
    vals={}
    for metric in ['appointments','sales','bills','same_day','within_48','checkins']:
        if metric=='checkins':
            row=c.execute(
                'SELECT COUNT(*) v FROM checkins WHERE guild_id=? AND user_id=?',
                (guild_id,user_id)
            ).fetchone()
        else:
            row=c.execute(
                'SELECT COALESCE(SUM(value),0) v FROM stats WHERE guild_id=? AND user_id=? AND metric=?',
                (guild_id,user_id,metric)
            ).fetchone()
        vals[metric]=int(row['v'] or 0)
    c.close()
    return vals

def greenie_status_embed(guild,member):
    p=greenie_progress(guild.id,member.id)
    approved=approved_bootcamp_count(guild.id,member.id)
    pending=pending_bootcamp_count(guild.id,member.id)
    stats=greenie_stats(guild.id,member.id)
    pitch_submitted=bool(p['pitch_url'])
    pitch_approved=bool(int(p['pitch_approved'] or 0))
    requested=bool(int(p['graduation_requested'] or 0))
    ready=approved>=3 and pitch_approved
    pitch_attempts=pitch_history_count(guild.id,member.id)
    latest_pitch=latest_pitch_submission(guild.id,member.id)

    next_steps=[]
    if approved<3:
        next_steps.append(f'Complete **{3-approved} more approved bootcamp{"s" if 3-approved!=1 else ""}**')
    if not pitch_submitted:
        next_steps.append('Submit your **pitch video**')
    elif not pitch_approved:
        next_steps.append('Get your **pitch approved by a Manager**')
    if ready and not requested:
        next_steps.append('Use **/graduation_request**')
    elif ready and requested:
        next_steps.append('Waiting for **Manager graduation approval**')

    e=discord.Embed(
        title=f'🎓 GREENIE STATUS — {member.display_name.upper()}',
        description='New setter onboarding progress.',
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(
        name='🏕️ TRAINING',
        value=(
            f'Bootcamps: **{approved}/3 approved**'
            + (f' • **{pending} pending**' if pending else '') + '\n'
            f'Pitch Submitted: **{"✅" if pitch_submitted else "❌"}**\n'
            f'Pitch Attempts: **{pitch_attempts}**\n'
            f'Pitch Approved: **{"✅" if pitch_approved else "❌"}**\n'
            + (
                f'Latest Pitch: **Rejected** — {latest_pitch["rejection_reason"]}\n'
                if latest_pitch and latest_pitch['status']=='rejected' and latest_pitch['rejection_reason']
                else ''
            )
            + f'Graduation Request: **{"✅ Submitted" if requested else "Not submitted"}**'
        ),
        inline=False
    )
    e.add_field(
        name='📊 PRODUCTION WHILE TRAINING',
        value=(
            f'📅 Appointments: **{stats["appointments"]}**\n'
            f'💰 Setter Sales: **{stats["sales"]}**\n'
            f'📄 Bills: **{stats["bills"]}**\n'
            f'⚡ Same-Days: **{stats["same_day"]}**\n'
            f'⏰ Within 48 Hours: **{stats["within_48"]}**'
        ),
        inline=False
    )
    e.add_field(
        name='📸 CHECK-INS',
        value=f'Completed: **{stats["checkins"]}**\n🛡️ Attendance Accountability: **Starts when promoted to Setter**',
        inline=False
    )
    e.add_field(
        name='➡️ NEXT STEP',
        value='\n'.join(f'• {x}' for x in next_steps) if next_steps else '✅ Ready for manager graduation.',
        inline=False
    )
    e.set_footer(text='Chosen Genesis Bootcamp')
    return e

async def bootcamp_channel(guild):
    return discord.utils.get(guild.text_channels,name='bootcamp')

async def post_greenie_status(guild,member):
    ch=await bootcamp_channel(guild)
    if ch:
        try:
            await ch.send(embed=greenie_status_embed(guild,member))
        except (discord.Forbidden,discord.HTTPException):
            pass

def greenie_pipeline_text(guild):
    lines=[]
    for member in guild.members:
        if member.bot or not is_greenie(member):
            continue
        p=greenie_progress(guild.id,member.id)
        bc=approved_bootcamp_count(guild.id,member.id)
        stats=greenie_stats(guild.id,member.id)
        pitch='✅' if int(p['pitch_approved'] or 0) else ('⏳' if p['pitch_url'] else '❌')
        lines.append(
            f'**{member.display_name}** — 🏕️ {bc}/3 • 🎥 {pitch} • '
            f'📅 {stats["appointments"]} apps • 💰 {stats["sales"]} sales'
        )
    return '\n'.join(lines[:10])

def previous_month_bounds(d=None):
    d=d or now().date()
    first=d.replace(day=1)
    prev_end=first-timedelta(days=1)
    prev_start=prev_end.replace(day=1)
    return prev_start.isoformat(),prev_end.isoformat()

def previous_month_setter_deals(guild_id,user_id):
    start,end=previous_month_bounds()
    return period_total_for_user(guild_id,user_id,'sales',start,end)

def has_earned_freedom(guild_id,user_id):
    return previous_month_setter_deals(guild_id,user_id) >= FREEDOM_REQUIRED_DEALS

def minutes_since_midnight(hour,minute):
    return hour*60+minute

def checkin_status_for_member(guild,member,checkin_dt):
    is_setter=any(r.name.lower()=='setter' for r in member.roles)
    if not is_setter:
        return 'not_applicable',None,None

    actual=minutes_since_midnight(checkin_dt.hour,checkin_dt.minute)

    # Monday (0) and Thursday (3) are meeting days.
    # Hard 4:00 PM cutoff: 4:00 is on time; 4:01+ is late.
    # This overrides both the normal Setter cutoff and Earned Freedom cutoff.
    if checkin_dt.weekday() in {0,3}:
        cutoff=minutes_since_midnight(16,0)
        if actual<=cutoff:
            return 'on_time',cutoff,cutoff
        return 'late',cutoff,cutoff

    if has_earned_freedom(guild.id,member.id):
        cutoff=minutes_since_midnight(FREEDOM_CUTOFF_HOUR,FREEDOM_CUTOFF_MINUTE)
        final_cutoff=cutoff+FREEDOM_GRACE_MINUTES
        if actual<=cutoff:
            return 'freedom',cutoff,final_cutoff
        if actual<=final_cutoff:
            return 'freedom_grace',cutoff,final_cutoff
        return 'late',cutoff,final_cutoff

    cutoff=minutes_since_midnight(REGULAR_CHECKIN_HOUR,REGULAR_CHECKIN_MINUTE)
    final_cutoff=cutoff+REGULAR_GRACE_MINUTES
    if actual<=cutoff:
        return 'on_time',cutoff,final_cutoff
    if actual<=final_cutoff:
        return 'grace',cutoff,final_cutoff
    return 'late',cutoff,final_cutoff

def parse_checkin_local_datetime(row):
    return datetime.strptime(
        f"{row['local_date']} {row['local_time']}",
        '%Y-%m-%d %I:%M %p'
    )

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
    if setters and setter_count>0:
        e.add_field(
            name='👑 Setter King',
            value=f'**{names(setters)}** — {setter_count} setter sales'
                  + f' • {max((setter_appts.get(x,0) for x in setters),default=0)} appointments',
            inline=False
        )
    if closers and closer_count>0:
        e.add_field(
            name='👑 Closer King',
            value=f'**{names(closers)}** — {closer_count} sales',
            inline=False
        )
    if bill_winners and bill_count>0:
        e.add_field(
            name='📄 Most Bills',
            value=f'**{names(bill_winners)}** — {bill_count}',
            inline=True
        )
    if sd_winners and sd_count>0:
        e.add_field(
            name='⚡ Most Same Days',
            value=f'**{names(sd_winners)}** — {sd_count}',
            inline=True
        )

    total_badges=int((badge_count or 0)+(badge_daily or 0))
    if total_badges>0:
        e.add_field(
            name='🏅 Badges Earned',
            value=f'**{total_badges}**',
            inline=True
        )
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

    bounty_uid,bounty_count,_=bounty_hunter_result(guild.id,date_text)
    bounty_leaders=[bounty_uid] if bounty_uid else []
    await set_holders(guild,'📄 Bounty Hunter',bounty_leaders)
    if bounty_uid and award_badge_count(guild.id,bounty_uid,'📄 Bounty Hunter',date_text):
        await announce_badge_milestone(guild,bounty_uid,'📄 Bounty Hunter')
    final['📄 Bounty Hunter']=(bounty_leaders,bounty_count)

    same_uid,same_count=same_day_savage_result(guild.id,date_text)
    same_leaders=[same_uid] if same_uid else []
    await set_holders(guild,'⚡ Same Day Savage',same_leaders)
    if same_uid and award_badge_count(guild.id,same_uid,'⚡ Same Day Savage',date_text):
        await announce_badge_milestone(guild,same_uid,'⚡ Same Day Savage')
    final['⚡ Same Day Savage']=(same_leaders,same_count)

    speed_uid,speed_count=speed_demon_result(guild.id,date_text)
    speed_leaders=[speed_uid] if speed_uid else []
    await set_holders(guild,'⏰ Speed Demon',speed_leaders)
    if speed_uid and award_badge_count(guild.id,speed_uid,'⏰ Speed Demon',date_text):
        await announce_badge_milestone(guild,speed_uid,'⏰ Speed Demon')
    final['⏰ Speed Demon']=(speed_leaders,speed_count)

    return point_uid,point_count,final

async def post_daily_awards(guild,date_obj=None,force=False):
    date_obj=date_obj or awards_now().date()
    date_text=date_obj.isoformat()
    key=f'daily_awards_{date_text}'
    if meta_get(guild.id,key) and not force:
        return False

    appointments=daily_team_appointments_for_date(guild.id,date_text)
    sales=daily_team_sales(guild.id,date_text)

    # Don't post an empty recap on a day nobody worked.
    if appointments<=0 and sales<=0:
        if not force:
            meta_set(guild.id,key,'empty')
        return False

    point_uid,point_count,quality_badges=await finalize_daily_competitive_badges(guild,date_text)
    night_uid=await finalize_night_owl(guild,date_obj,set_role=True)
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

    sales_lines=[]
    if sale_ids:
        sales_lines.append(f'💥 **SALE:** {member_names(guild,sale_ids)}')
    if two_ids:
        sales_lines.append(f'🥈 **2 SPOT:** {member_names(guild,two_ids)}')
    if hat_ids:
        sales_lines.append(f'🎩 **HATTRICK:** {member_names(guild,hat_ids)}')
    if ghost_ids:
        sales_lines.append(f'👻 **GHOST HUNTER:** {member_names(guild,ghost_ids)}')

    if sales_lines:
        e.add_field(
            name='💰 SALES BADGES',
            value='\n'.join(sales_lines),
            inline=False
        )

    point_name=member_names(guild,[point_uid]) if point_uid else 'No winner — nobody reached 2 appointments'
    bounty_ids,bounty_val=quality_badges.get('📄 Bounty Hunter',([],0))
    same_ids,same_val=quality_badges.get('⚡ Same Day Savage',([],0))
    speed_ids,speed_val=quality_badges.get('⏰ Speed Demon',([],0))

    comp_lines=[]
    if point_uid:
        comp_lines.append(f'🎯 **POINT MAN:** {point_name} — {point_count} appointments')
    if bounty_ids:
        comp_lines.append(f'📄 **BOUNTY HUNTER:** {member_names(guild,bounty_ids)} — {bounty_val} bills')
    if same_ids:
        comp_lines.append(f'⚡ **SAME DAY SAVAGE:** {member_names(guild,same_ids)} — {same_val} same-days')
    if speed_ids:
        comp_lines.append(f'⏰ **SPEED DEMON:** {member_names(guild,speed_ids)} — {speed_val} within 48 hrs')
    if first_uid:
        comp_lines.append(f'🩸 **FIRST BLOOD:** {member_names(guild,[first_uid])}')
    if night_uid:
        comp_lines.append(f'🦉 **NIGHT OWL:** {member_names(guild,[night_uid])}')

    if comp_lines:
        e.add_field(
            name='🎯 DAILY BADGES',
            value='\n'.join(comp_lines),
            inline=False
        )

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
    return True

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

def quality_badge_single_winner(g,date_text,primary_metric,tiebreak_metrics):
    primary=daily_metric_totals_for_date(g,primary_metric,date_text)
    eligible={u:int(v) for u,v in primary.items() if v>0}
    if not eligible:
        return None,0

    best=max(eligible.values())
    tied=[u for u,v in eligible.items() if v==best]

    for metric in tiebreak_metrics:
        if len(tied)<=1:
            break
        totals=daily_metric_totals_for_date(g,metric,date_text)
        high=max(int(totals.get(u,0)) for u in tied)
        tied=[u for u in tied if int(totals.get(u,0))==high]

    if len(tied)>1:
        c=con(); reached=[]
        column={'same_day':'same_day','within_48':'within_48'}[primary_metric]
        for uid in tied:
            rows=c.execute(
                f'SELECT id,created_at,{column} value FROM appointment_events '
                'WHERE guild_id=? AND setter_id=? AND local_date=? ORDER BY id ASC',
                (g,uid,date_text)
            ).fetchall()
            running=0; reached_at='9999'; reached_id=10**18
            for r in rows:
                running+=int(r['value'] or 0)
                if running>=best:
                    reached_at=r['created_at']; reached_id=r['id']; break
            reached.append((reached_at,reached_id,uid))
        c.close()
        reached.sort(key=lambda x:(x[0],x[1],x[2]))
        tied=[reached[0][2]]

    return tied[0],best

def same_day_savage_result(g,date_text=None):
    date_text=date_text or dkey()
    return quality_badge_single_winner(g,date_text,'same_day',['appointments','bills','within_48'])

def speed_demon_result(g,date_text=None):
    date_text=date_text or dkey()
    return quality_badge_single_winner(g,date_text,'within_48',['appointments','same_day','bills'])

def bounty_hunter_result(g,date_text=None):
    date_text=date_text or dkey()

    bills=daily_metric_totals_for_date(g,'bills',date_text)
    eligible={u:int(v) for u,v in bills.items() if v>0}
    if not eligible:
        return None,0,{'appointments':0,'same_day':0,'within_48':0}

    best=max(eligible.values())
    tied=[u for u,v in eligible.items() if v==best]

    # Bounty Hunter tiebreakers:
    # 1) Most bills
    # 2) Most total appointments
    # 3) Most same-day appointments
    # 4) Most within-48-hour appointments
    # 5) Whoever reached the winning bill count first
    appts=daily_metric_totals_for_date(g,'appointments',date_text)
    same=daily_metric_totals_for_date(g,'same_day',date_text)
    within=daily_metric_totals_for_date(g,'within_48',date_text)

    if len(tied)>1:
        best_appts=max(int(appts.get(u,0)) for u in tied)
        tied=[u for u in tied if int(appts.get(u,0))==best_appts]

    if len(tied)>1:
        best_same=max(int(same.get(u,0)) for u in tied)
        tied=[u for u in tied if int(same.get(u,0))==best_same]

    if len(tied)>1:
        best_within=max(int(within.get(u,0)) for u in tied)
        tied=[u for u in tied if int(within.get(u,0))==best_within]

    if len(tied)>1:
        c=con()
        reached=[]
        for uid in tied:
            rows=c.execute(
                'SELECT id,created_at,bill_collected FROM appointment_events '
                'WHERE guild_id=? AND setter_id=? AND local_date=? '
                'ORDER BY id ASC',
                (g,uid,date_text)
            ).fetchall()

            running=0
            reached_at='9999'
            reached_id=10**18
            for r in rows:
                running += int(r['bill_collected'] or 0)
                if running>=best:
                    reached_at=r['created_at']
                    reached_id=r['id']
                    break
            reached.append((reached_at,reached_id,uid))
        c.close()

        reached.sort(key=lambda x:(x[0],x[1],x[2]))
        tied=[reached[0][2]]

    uid=tied[0]
    quality={
        'appointments':int(appts.get(uid,0)),
        'same_day':int(same.get(uid,0)),
        'within_48':int(within.get(uid,0))
    }
    return uid,best,quality


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

    # Bounty Hunter always has ONE holder.
    bounty_uid,_,_=bounty_hunter_result(guild.id,dkey())
    await set_holders(guild,'📄 Bounty Hunter',[bounty_uid] if bounty_uid else [])

    same_uid,_=same_day_savage_result(guild.id,dkey())
    speed_uid,_=speed_demon_result(guild.id,dkey())
    await set_holders(guild,'⚡ Same Day Savage',[same_uid] if same_uid else [])
    await set_holders(guild,'⏰ Speed Demon',[speed_uid] if speed_uid else [])

    # Daily competitive badge history is finalized at 10 PM instead of while
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
        sales=period_total_for_user(g,uid,'sales',start_date,end_date)+weekly_override_total(g,uid,'setter_sales',wk)
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


MONTHLY_SETTER_STANDARD = 3
COACHING_MIN_APPTS = 5

def setter_members(guild):
    return [
        m for m in guild.members
        if not m.bot and any(r.name.lower()=='setter' for r in m.roles)
    ]

def setter_period_snapshot(guild,member,start,end):
    appts=period_total_for_user(guild.id,member.id,'appointments',start,end)
    sales=period_total_for_user(guild.id,member.id,'sales',start,end)
    same=period_total_for_user(guild.id,member.id,'same_day',start,end)
    within=period_total_for_user(guild.id,member.id,'within_48',start,end)
    bills=period_total_for_user(guild.id,member.id,'bills',start,end)

    # Same-day appointments are inherently within 48 hours. Protect against
    # older records where within_48 may not have been marked on a same-day.
    effective_within=min(appts,max(within,same))
    over48=max(0,appts-effective_within)

    return {
        'member':member,
        'appointments':appts,
        'sales':sales,
        'same_day':same,
        'within_48':effective_within,
        'over_48':over48,
        'bills':bills,
        'conversion':(sales/appts*100.0) if appts else 0.0,
        'over_48_pct':(over48/appts*100.0) if appts else 0.0,
        'bill_pct':(bills/appts*100.0) if appts else 0.0,
    }

def monthly_pace_status(guild,member,as_of=None):
    as_of=as_of or now().date()
    start=as_of.replace(day=1).isoformat()
    end=as_of.isoformat()
    sales=period_total_for_user(guild.id,member.id,'sales',start,end)
    days_in_month=calendar.monthrange(as_of.year,as_of.month)[1]
    expected=MONTHLY_SETTER_STANDARD*(as_of.day/days_in_month)

    if sales>=MONTHLY_SETTER_STANDARD:
        label='✅ Standard Hit'
    elif sales>=expected:
        label='🟢 On Pace'
    elif sales+0.5>=expected:
        label='🟡 Close to Pace'
    else:
        label='🔴 Behind Pace'
    return sales,expected,label

def coaching_diagnosis(s):
    a=s['appointments']; sales=s['sales']; over=s['over_48_pct']; conv=s['conversion']; bill=s['bill_pct']

    if a<COACHING_MIN_APPTS:
        if a<=1:
            return 'Low activity — not enough volume yet to judge conversion.'
        return 'Limited sample — build more appointment volume before diagnosing conversion.'

    flags=[]
    if over>=40:
        flags.append(f'{over:.0f}% of appointments are over 48 hours — focus on pulling appointments closer')
    elif over>=25:
        flags.append(f'{over:.0f}% are over 48 hours — appointment timing is worth watching')

    if sales==0:
        if over<40:
            flags.append('no closed deals from solid activity — review appointment quality, handoff, and close outcomes')
        else:
            flags.append('no closed deals yet — review both appointment timing and close outcomes')
    elif conv<15:
        flags.append(f'{conv:.0f}% appointment-to-sale conversion — review quality and close outcomes')
    elif conv>=35:
        flags.append(f'strong {conv:.0f}% conversion')
        if a<8:
            flags.append('more volume could create a bigger week')

    if bill<50 and a>=5:
        flags.append(f'only {bill:.0f}% of appointments have bills — review bill collection')

    if not flags:
        return 'Healthy activity/quality mix — keep monitoring conversion.'
    return ' • '.join(flags)+'.'

def manager_review_embed(guild,start,end,title,description):
    snapshots=[setter_period_snapshot(guild,m,start,end) for m in setter_members(guild)]
    snapshots.sort(key=lambda s:(-s['appointments'],-s['sales'],s['member'].display_name.lower()))

    e=discord.Embed(
        title=title,
        description=description,
        timestamp=datetime.now(timezone.utc)
    )

    top=snapshots[:5]
    top_lines=[]
    for i,s in enumerate(top,1):
        medal=['🥇','🥈','🥉'][i-1] if i<=3 else f'#{i}'
        top_lines.append(
            f'{medal} **{s["member"].display_name}** — **{s["appointments"]} apps** • {s["sales"]} sales'
        )
    e.add_field(
        name='🏆 TOP 5 APPOINTMENT SETTERS',
        value='\n'.join(top_lines) if top_lines else 'No setter production yet.',
        inline=False
    )

    production_lines=[]
    for s in snapshots[:10]:
        if s['appointments']<=0 and s['sales']<=0:
            continue
        production_lines.append(
            f'**{s["member"].display_name}** — {s["appointments"]} apps • {s["sales"]} sales • '
            f'{s["conversion"]:.0f}% conv\n'
            f'⚡ {s["same_day"]} same-day • ⏰ {s["within_48"]} ≤48h • '
            f'📅 {s["over_48"]} >48h ({s["over_48_pct"]:.0f}%) • 📄 {s["bills"]} bills'
        )
    e.add_field(
        name='📊 SETTER QUALITY + CONVERSION',
        value='\n'.join(production_lines)[:1024] if production_lines else 'No setter production yet.',
        inline=False
    )

    diagnosis=[]
    for s in snapshots:
        if s['appointments']<=0:
            continue
        diagnosis.append(f'**{s["member"].display_name}:** {coaching_diagnosis(s)}')
    e.add_field(
        name='🔍 COACHING DIAGNOSIS',
        value='\n'.join(diagnosis[:8])[:1024] if diagnosis else 'Not enough activity to diagnose yet.',
        inline=False
    )

    pace=[]
    for s in snapshots:
        sales,expected,label=monthly_pace_status(guild,s['member'])
        pace.append(
            f'**{s["member"].display_name}** — {sales}/{MONTHLY_SETTER_STANDARD} deals • {label}'
        )
    e.add_field(
        name=f'🎯 MONTHLY STANDARD — {MONTHLY_SETTER_STANDARD} DEALS',
        value='\n'.join(pace[:12])[:1024] if pace else 'No setters found.',
        inline=False
    )

    c=con()
    attendance_rows=c.execute(
        'SELECT user_id,status,COUNT(*) c FROM attendance_records '
        'WHERE guild_id=? AND local_date BETWEEN ? AND ? GROUP BY user_id,status',
        (guild.id,start,end)
    ).fetchall()
    c.close()
    attendance={}
    for r in attendance_rows:
        attendance.setdefault(r['user_id'],{})[r['status']]=int(r['c'] or 0)

    att_lines=[]
    for s in snapshots:
        stats=attendance.get(s['member'].id,{})
        if not stats:
            continue
        att_lines.append(
            f'**{s["member"].display_name}** — ✅ {stats.get("on_time",0)} • '
            f'⚠️ {stats.get("late",0)} • ❌ {stats.get("missed",0)}'
        )
    if att_lines:
        e.add_field(name='🕐 ATTENDANCE',value='\n'.join(att_lines)[:1024],inline=False)

    watch=[]
    for s in snapshots:
        if s['appointments']>=COACHING_MIN_APPTS:
            if s['over_48_pct']>=40:
                watch.append(f'📅 **{s["member"].display_name}** — {s["over_48_pct"]:.0f}% of apps are >48h')
            elif s['sales']==0:
                watch.append(f'🔎 **{s["member"].display_name}** — {s["appointments"]} apps / 0 sales')
            elif s['conversion']<15:
                watch.append(f'📉 **{s["member"].display_name}** — {s["conversion"]:.0f}% conversion')
            elif s['conversion']>=35 and s['appointments']<8:
                watch.append(f'📈 **{s["member"].display_name}** — strong conversion; push volume')
    if watch:
        e.add_field(name='📌 MANAGER WATCHLIST',value='\n'.join(watch[:8])[:1024],inline=False)

    greenies=greenie_pipeline_text(guild)
    if greenies:
        e.add_field(name='🆕 GREENIE PIPELINE',value=greenies[:1024],inline=False)

    e.set_footer(text='Private manager intelligence • Chosen Genesis')
    return e

async def dm_managers(guild,embed):
    managers=[
        m for m in guild.members
        if not m.bot and any(r.name.lower()=='manager' for r in m.roles)
    ]
    delivered=[]
    failed=[]
    for manager in managers:
        try:
            await manager.send(embed=embed)
            delivered.append(manager.id)
        except (discord.Forbidden,discord.HTTPException) as exc:
            failed.append(manager.id)
            print(
                f'[MANAGER DM ERROR] guild={guild.id} manager={manager.id} '
                f'error={type(exc).__name__}: {exc}'
            )
    return delivered,failed

async def send_midweek_manager_review(guild,force=False):
    # Wednesday end-of-day review covers Monday through the current moment.
    today=now().date()
    start=(today-timedelta(days=today.weekday())).isoformat()
    end=today.isoformat()
    key=wkey(today)
    meta_key='manager_midweek_sent'
    if meta_get(guild.id,meta_key)==key and not force:
        return False

    e=manager_review_embed(
        guild,start,end,
        '📊 CHOSEN GENESIS — MID-WEEK MANAGER REVIEW',
        f'Private manager review • **{start} → {end}**\nWhat needs attention before the week closes?'
    )
    delivered,failed=await dm_managers(guild,e)
    if delivered and not force:
        meta_set(guild.id,meta_key,key)
    return {
        'sent':bool(delivered),
        'delivered':len(delivered),
        'failed':len(failed),
        'embed':e
    }

async def send_weekly_manager_summary(guild,week_key,force=False):
    if meta_get(guild.id,'manager_weekly_sent')==week_key and not force:
        return False

    start,end=week_date_bounds_from_key(week_key)
    prev_end=datetime.strptime(start,'%Y-%m-%d').date()-timedelta(days=1)
    prev_wk=wkey(prev_end)

    e=manager_review_embed(
        guild,start,end,
        '📋 CHOSEN GENESIS — WEEKLY MANAGER REVIEW',
        f'Private manager review for **{week_key}**.\nProduction, quality, conversion, pace, and accountability.'
    )

    add_attendance_summary_to_embed(guild,e,start,end)

    top_setter_sales=period_rows_between(guild.id,start,end,'setter_sales',5)
    top_closer_sales=period_rows_between(guild.id,start,end,'closer_sales',5)
    e.add_field(name='💰 TOP 5 SETTER SALES',value=fmt_ranked_members(guild,top_setter_sales),inline=False)
    e.add_field(name='🤝 TOP 5 CLOSER SALES',value=fmt_ranked_members(guild,top_closer_sales),inline=False)

    current=week_member_totals(guild,week_key,'appointments')
    previous=week_member_totals(guild,prev_wk,'appointments')
    movers=[]
    for uid in set(current)|set(previous):
        diff=current.get(uid,0)-previous.get(uid,0)
        if diff:
            movers.append((uid,diff,current.get(uid,0),previous.get(uid,0)))
    movers.sort(key=lambda x:(-x[1],-x[2]))

    momentum=[]
    for uid,diff,cur,prev in movers[:5]:
        member=guild.get_member(uid)
        if member:
            momentum.append(
                f'{"⬆️" if diff>0 else "⬇️"} **{member.display_name}**: {prev} → {cur} ({diff:+d})'
            )
    if momentum:
        e.add_field(name='📈 WEEK-OVER-WEEK APPOINTMENT MOMENTUM',value='\n'.join(momentum),inline=False)

    delivered,failed=await dm_managers(guild,e)
    if delivered and not force:
        meta_set(guild.id,'manager_weekly_sent',week_key)
    return {
        'sent':bool(delivered),
        'delivered':len(delivered),
        'failed':len(failed),
        'embed':e
    }


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

    if kind!='setter':
        c2=con()
        override_users=[r['user_id'] for r in c2.execute(
            'SELECT DISTINCT user_id FROM weekly_credit_overrides WHERE guild_id=? AND role_type=? AND credit_week_key=?',
            (g,'closer_sales',wk)
        ).fetchall()]
        c2.close()
        for uid in override_users:
            totals[uid]=totals.get(uid,0)+weekly_override_total(g,uid,'closer_sales',wk)

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
    # competitive holders directly from today's saved appointment data.
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

            if badge=='📄 Bounty Hunter':
                uid,_,_=bounty_hunter_result(guild.id,dkey())
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

    ensure_member_state(member.guild.id,member.id,now().date().isoformat())

    # Every new human member starts as a Greenie.
    greenie_role=discord.utils.get(member.guild.roles,name='Greenie')
    if greenie_role is None:
        try:
            greenie_role=await member.guild.create_role(
                name='Greenie',
                reason='Chosen Genesis automatic onboarding role'
            )
        except (discord.Forbidden,discord.HTTPException):
            greenie_role=None

    if greenie_role is not None and greenie_role not in member.roles:
        try:
            await member.add_roles(greenie_role,reason='New member entered Chosen Genesis onboarding')
        except (discord.Forbidden,discord.HTTPException):
            pass

    ensure_greenie_progress(member.guild.id,member.id)

    title,description=random.choice(WELCOME_MESSAGES)
    e=discord.Embed(
        title=title,
        description=description.format(mention=member.mention),
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(
        name='🆕 GREENIE ONBOARDING',
        value=(
            'You have been added to the **Greenie** onboarding track.\n'
            'Head to **#bootcamp** to complete your training.'
        ),
        inline=False
    )
    e.set_footer(text='Chosen Genesis')
    await main(member.guild,embed=e)

    # Post their starting onboarding status in the bootcamp channel.
    try:
        await post_greenie_status(member.guild,member)
    except Exception as exc:
        print(f'[GREENIE STATUS ERROR] member={member.id} error={type(exc).__name__}: {exc}')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    for g in bot.guilds:
        for m in g.members:
            if not m.bot:
                joined=(m.joined_at.astimezone(TZ).date().isoformat() if getattr(m,'joined_at',None) else dkey())
                ensure_member_state(g.id,m.id,joined)

                # Reconcile database state FROM Discord roles.
                # Greenie = onboarding/not attendance-tracked.
                # Setter without Greenie = graduated/attendance-tracked.
                if is_greenie(m):
                    ensure_greenie_progress(g.id,m.id)
                    c=con()
                    c.execute(
                        'UPDATE member_state SET onboarding=1 WHERE guild_id=? AND user_id=?',
                        (g.id,m.id)
                    )
                    c.commit(); c.close()
                elif has_named_role(m,'Setter'):
                    c=con()
                    c.execute(
                        'UPDATE member_state SET onboarding=0 WHERE guild_id=? AND user_id=?',
                        (g.id,m.id)
                    )
                    c.commit(); c.close()
        if meta_get(g.id,'daily_date')!=dkey(): meta_set(g.id,'daily_date',dkey())
        await restore_daily(g); await refresh_daily_comp(g); await set_live_night_owl(g,dkey()); await refresh_streaks(g)
    for g in bot.guilds:
        await refresh_leaderboard(g)
        if awards_now().weekday()!=6 and awards_now().hour>=22:
            finalize_missed_checkins_for_date(g,awards_now().date())
            finalize_missed_checkouts_for_date(g,awards_now().date())
            try:
                posted=await post_daily_awards(g,awards_now().date())
                if posted:
                    print(f'[DAILY AWARDS] Posted for guild {g.id} at {awards_now().isoformat()}')
            except Exception as exc:
                print(f'[DAILY AWARDS ERROR] guild={g.id} error={type(exc).__name__}: {exc}')
            await refresh_leaderboard(g)
        # Mid-week report: Wednesday at 10:00 PM Arizona time.
        if now().weekday()==2 and now().hour>=22:
            await send_midweek_manager_review(g)
        await weekly_kings(g)
        # Restore active challenges and their live messages after Railway restarts.
        await refresh_active_challenges(g)
        # Official weekly close: Sunday 10 PM Arizona time.
        # Catch-up behavior: after Sunday 10 PM and throughout Monday, keep
        # attempting the just-finished week until at least one Manager DM succeeds.
        n=now()
        closed_week=None
        if n.weekday()==6 and n.hour>=22:
            closed_week=wkey(n.date())
        elif n.weekday()==0:
            closed_week=wkey(n.date()-timedelta(days=1))
        if closed_week:
            await weekly_recap(g,closed_week)
            await send_weekly_manager_summary(g,closed_week)
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

        # Finalize and announce the day's badges at 10 PM Arizona time.
        # Sunday is skipped as the bot's existing workday logic treats it as off.
        if awards_now().weekday()!=6 and awards_now().hour>=22:
            finalize_missed_checkouts_for_date(g,awards_now().date())
            await post_daily_awards(g,awards_now().date())

        # Mid-week manager intelligence: Wednesday at 10:00 PM Arizona time.
        if now().weekday()==2 and now().hour>=22:
            await send_midweek_manager_review(g)

        # Keep cosmetic King roles synced all week.
        await weekly_kings(g)

        # Challenge state lives in SQLite; refresh/evaluate it every cycle so
        # deadlines and message restoration survive worker restarts.
        await refresh_active_challenges(g)
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


CHALLENGE_TYPE_CHOICES = [
    app_commands.Choice(name='Daily',value='daily'),
    app_commands.Choice(name='Weekly',value='weekly'),
    app_commands.Choice(name='Custom',value='custom'),
]
CHALLENGE_SCOPE_CHOICES = [
    app_commands.Choice(name='Everyone',value='everyone'),
    app_commands.Choice(name='All Setters',value='setters'),
    app_commands.Choice(name='All Closers',value='closers'),
    app_commands.Choice(name='Selected People',value='selected'),
]
CHALLENGE_METRIC_CHOICES = [
    app_commands.Choice(name='Appointments',value='appointments'),
    app_commands.Choice(name='Setter Sales',value='setter_sales'),
    app_commands.Choice(name='Closer Sales',value='closer_sales'),
    app_commands.Choice(name='Same-Day Appointments',value='same_day'),
    app_commands.Choice(name='Within 48 Hours',value='within_48'),
    app_commands.Choice(name='Bills Collected',value='bills'),
    app_commands.Choice(name='📸 Homeowner Selfies',value='homeowner_selfie'),
]
CHALLENGE_END_CHOICES = [
    app_commands.Choice(name='Manual End',value='manual'),
    app_commands.Choice(name='Deadline',value='deadline'),
    app_commands.Choice(name='Goal Reached or Deadline',value='goal_or_deadline'),
]
CHALLENGE_BEHAVIOR_CHOICES = [
    app_commands.Choice(name='Highest Score Wins',value='highest'),
    app_commands.Choice(name='No Winner if Goal Missed',value='no_winner'),
]

def challenge_metric_label(metric):
    return {
        'appointments':'Appointments',
        'setter_sales':'Setter Sales',
        'closer_sales':'Closer Sales',
        'same_day':'Same-Days',
        'within_48':'Within 48 Hours',
        'bills':'Bills Collected',
        'homeowner_selfie':'📸 Homeowner Selfies',
    }.get(metric,metric)

def parse_challenge_deadline(date_text,time_text):
    if not date_text or not time_text:
        return None
    try:
        dt=datetime.strptime(f'{date_text.strip()} {time_text.strip()}','%Y-%m-%d %H:%M')
        return dt.replace(tzinfo=TZ)
    except ValueError:
        return None

def challenge_row(challenge_id,guild_id=None):
    c=con()
    if guild_id is None:
        row=c.execute('SELECT * FROM challenges WHERE id=?',(challenge_id,)).fetchone()
    else:
        row=c.execute('SELECT * FROM challenges WHERE id=? AND guild_id=?',(challenge_id,guild_id)).fetchone()
    c.close()
    return row

def active_challenges(guild_id):
    c=con()
    rows=c.execute(
        "SELECT * FROM challenges WHERE guild_id=? AND status='active' ORDER BY id ASC",
        (guild_id,)
    ).fetchall()
    c.close()
    return rows

def challenge_participant_ids(challenge_id):
    c=con()
    rows=c.execute(
        'SELECT user_id FROM challenge_participants WHERE challenge_id=? ORDER BY user_id',
        (challenge_id,)
    ).fetchall()
    c.close()
    return [r['user_id'] for r in rows]

def challenge_scores(challenge_id):
    c=con()
    rows=c.execute(
        'SELECT user_id,score FROM challenge_participants WHERE challenge_id=? ORDER BY score DESC,user_id ASC',
        (challenge_id,)
    ).fetchall()
    c.close()
    return [(r['user_id'],int(r['score'] or 0)) for r in rows]

def challenge_member_scope(guild,scope,selected):
    selected=[m for m in selected if m is not None and not m.bot]
    if scope=='selected':
        # preserve order, remove duplicates
        seen=set(); out=[]
        for m in selected:
            if m.id not in seen:
                seen.add(m.id); out.append(m)
        return out
    if scope=='setters':
        return [m for m in guild.members if not m.bot and any(r.name.lower()=='setter' for r in m.roles)]
    if scope=='closers':
        return [m for m in guild.members if not m.bot and any(r.name.lower()=='closer' for r in m.roles)]
    # Everyone means all non-manager reps with Setter and/or Closer role.
    return [
        m for m in guild.members
        if not m.bot
        and not any(r.name.lower()=='manager' for r in m.roles)
        and any(r.name.lower() in {'setter','closer'} for r in m.roles)
    ]

def challenge_score_line(guild,uid,score,goal=None,index=None):
    member=guild.get_member(uid)
    name=member.display_name if member else f'<@{uid}>'
    prefix=['🥇','🥈','🥉'][index] if index is not None and index<3 else (f'#{index+1}' if index is not None else '•')
    if goal and goal>0:
        return f'{prefix} **{name}** — **{score}/{goal}**'
    return f'{prefix} **{name}** — **{score}**'

async def render_challenge(guild,ch_row,send_if_missing=True):
    scores=challenge_scores(ch_row['id'])
    goal=int(ch_row['goal'] or 0)
    deadline=ch_row['deadline_at']
    deadline_text='Manual'
    if deadline:
        try:
            dt=datetime.fromisoformat(deadline)
            deadline_text=dt.astimezone(TZ).strftime('%a %b %d • %-I:%M %p')
        except Exception:
            deadline_text=deadline

    scope_label={
        'everyone':'Everyone',
        'setters':'All Setters',
        'closers':'All Closers',
        'selected':'Selected People'
    }.get(ch_row['scope'],ch_row['scope'])

    e=discord.Embed(
        title=f'⚔️ CHOSEN GENESIS CHALLENGE — {ch_row["name"]}',
        description=(
            f'**{str(ch_row["challenge_type"]).upper()} • Challenge #{ch_row["id"]}**\n\n'
            f'👥 **Competitors:** {scope_label}\n'
            f'📊 **Tracking:** {challenge_metric_label(ch_row["metric"])}\n'
            f'📜 **Terms:** {ch_row["terms"]}\n'
            + (f'🎯 **Goal:** {goal}\n' if goal else '')
            + f'⏰ **Ends:** {deadline_text}\n'
            + (f'🏆 **Prize:** {ch_row["prize"]}\n' if ch_row['prize'] else '')
        ),
        timestamp=datetime.now(timezone.utc)
    )

    if scores:
        standings='\n'.join(
            challenge_score_line(guild,uid,score,goal,index=i)
            for i,(uid,score) in enumerate(scores[:15])
        )
    else:
        standings='No competitors.'
    e.add_field(name='🔥 CURRENT STANDINGS',value=standings,inline=False)
    e.set_footer(text='Challenge standings update automatically.')

    ch=None
    if ch_row['channel_id']:
        ch=guild.get_channel(int(ch_row['channel_id']))
    if not ch:
        ch=await channel(guild,'main-chat')
    if not ch:
        return None

    if ch_row['message_id']:
        try:
            msg=await ch.fetch_message(int(ch_row['message_id']))
            await msg.edit(embed=e)
            return msg
        except (discord.NotFound,discord.Forbidden,discord.HTTPException,ValueError):
            pass

    if not send_if_missing:
        return None

    msg=await ch.send(embed=e)
    c=con()
    c.execute(
        'UPDATE challenges SET channel_id=?,message_id=? WHERE id=?',
        (ch.id,msg.id,ch_row['id'])
    )
    c.commit(); c.close()
    return msg

def challenge_leaders(challenge_id):
    scores=challenge_scores(challenge_id)
    if not scores:
        return [],0
    best=scores[0][1]
    return [uid for uid,score in scores if score==best],best

async def finish_challenge(guild,ch_row,winner_ids=None,reason='complete',no_winner=False):
    if ch_row['status']!='active':
        return
    winner_ids=winner_ids or []
    winner_id=winner_ids[0] if len(winner_ids)==1 else None
    c=con()
    c.execute(
        "UPDATE challenges SET status='ended',winner_id=?,ended_at=? WHERE id=?",
        (winner_id,datetime.now(timezone.utc).isoformat(),ch_row['id'])
    )
    c.commit(); c.close()

    if no_winner or not winner_ids:
        result='**No winner.**'
    else:
        names=', '.join(
            (guild.get_member(uid).mention if guild.get_member(uid) else f'<@{uid}>')
            for uid in winner_ids
        )
        result=f'🏆 **Winner:** {names}'

    e=discord.Embed(
        title=f'🏁 CHALLENGE COMPLETE — {ch_row["name"]}',
        description=(
            f'{result}\n\n'
            f'📜 **Terms:** {ch_row["terms"]}\n'
            f'📊 **Final metric:** {challenge_metric_label(ch_row["metric"])}'
            + (f'\n🏆 **Prize:** {ch_row["prize"]}' if ch_row['prize'] else '')
        ),
        timestamp=datetime.now(timezone.utc)
    )
    e.set_footer(text=f'Challenge #{ch_row["id"]} • {reason}')
    await main(guild,embed=e)

async def evaluate_challenge(guild,ch_row):
    if ch_row['status']!='active':
        return
    goal=int(ch_row['goal'] or 0)
    scores=challenge_scores(ch_row['id'])

    # Goal hit: first qualifying score wins immediately.
    if goal>0 and ch_row['end_mode']=='goal_or_deadline':
        reached=[(uid,score) for uid,score in scores if score>=goal]
        if reached:
            best=max(score for _,score in reached)
            winners=[uid for uid,score in reached if score==best]
            await finish_challenge(guild,ch_row,winners,'goal reached')
            return

    # Deadline reached.
    if ch_row['deadline_at'] and ch_row['end_mode'] in {'deadline','goal_or_deadline'}:
        try:
            deadline=datetime.fromisoformat(ch_row['deadline_at'])
            if deadline.tzinfo is None:
                deadline=deadline.replace(tzinfo=TZ)
            if now()>=deadline.astimezone(TZ):
                leaders,best=challenge_leaders(ch_row['id'])
                if ch_row['end_mode']=='goal_or_deadline' and goal>0 and best<goal and ch_row['end_behavior']=='no_winner':
                    await finish_challenge(guild,ch_row,[],f'deadline reached • top score {best}',no_winner=True)
                else:
                    await finish_challenge(guild,ch_row,leaders,'deadline reached')
                return
        except Exception:
            pass

async def update_challenges_for_event(guild,user_id,metric,amount=1):
    if not user_id or amount<=0:
        return
    relevant=[]
    c=con()
    for ch in c.execute(
        "SELECT c.* FROM challenges c JOIN challenge_participants p ON p.challenge_id=c.id "
        "WHERE c.guild_id=? AND c.status='active' AND c.metric=? AND p.user_id=?",
        (guild.id,metric,user_id)
    ).fetchall():
        relevant.append(ch)
        c.execute(
            'UPDATE challenge_participants SET score=score+? WHERE challenge_id=? AND user_id=?',
            (amount,ch['id'],user_id)
        )
    c.commit(); c.close()

    for ch in relevant:
        fresh=challenge_row(ch['id'],guild.id)
        await render_challenge(guild,fresh)
        await evaluate_challenge(guild,fresh)

async def refresh_active_challenges(guild):
    for ch in active_challenges(guild.id):
        await render_challenge(guild,ch)
        await evaluate_challenge(guild,ch)



BADGE_REPORT_PERIOD_CHOICES = [
    app_commands.Choice(name='This Week',value='this_week'),
    app_commands.Choice(name='Last Week',value='last_week'),
    app_commands.Choice(name='This Month',value='this_month'),
    app_commands.Choice(name='Last Month',value='last_month'),
]

def badge_report_bounds(period):
    today=now().date()
    if period=='this_week':
        start=today-timedelta(days=today.weekday()); end=today; label='THIS WEEK'
    elif period=='last_week':
        this_start=today-timedelta(days=today.weekday())
        end=this_start-timedelta(days=1); start=end-timedelta(days=6); label='LAST WEEK'
    elif period=='this_month':
        start=today.replace(day=1); end=today; label='THIS MONTH'
    else:
        this_start=today.replace(day=1)
        end=this_start-timedelta(days=1); start=end.replace(day=1); label='LAST MONTH'
    return start.isoformat(),end.isoformat(),label

def badge_counts_between(guild_id,user_id,start_date,end_date):
    c=con()
    rows=c.execute(
        'SELECT badge_name,COUNT(*) c FROM badge_awards '
        'WHERE guild_id=? AND user_id=? AND (award_key BETWEEN ? AND ? OR created_at BETWEEN ? AND ?) '
        'GROUP BY badge_name',
        (guild_id,user_id,start_date,end_date,f'{start_date}T00:00:00',f'{end_date}T23:59:59.999999')
    ).fetchall()
    c.close()
    return {r['badge_name']:int(r['c'] or 0) for r in rows}

def all_badge_totals_between(guild,start_date,end_date):
    out=[]
    for member in guild.members:
        if member.bot:
            continue
        counts=badge_counts_between(guild.id,member.id,start_date,end_date)
        total=sum(counts.values())
        if total:
            out.append((member,total,counts))
    out.sort(key=lambda x:(-x[1],x[0].display_name.lower()))
    return out



TEAM_REPORT_PERIOD_CHOICES = [
    app_commands.Choice(name='This Week',value='this_week'),
    app_commands.Choice(name='Last Week',value='last_week'),
    app_commands.Choice(name='This Month',value='this_month'),
    app_commands.Choice(name='Last Month',value='last_month'),
]

def team_report_bounds(period):
    today=now().date()
    if period=='this_week':
        start=today-timedelta(days=today.weekday())
        end=today
        label='THIS WEEK'
    elif period=='last_week':
        this_start=today-timedelta(days=today.weekday())
        end=this_start-timedelta(days=1)
        start=end-timedelta(days=6)
        label='LAST WEEK'
    elif period=='this_month':
        start=today.replace(day=1)
        end=today
        label='THIS MONTH'
    else:
        this_start=today.replace(day=1)
        end=this_start-timedelta(days=1)
        start=end.replace(day=1)
        label='LAST MONTH'
    return start.isoformat(),end.isoformat(),label

def team_quality_totals(guild_id,start,end):
    c=con()
    r=c.execute(
        'SELECT COUNT(*) appts,'
        'COALESCE(SUM(same_day),0) same_day,'
        'COALESCE(SUM(within_48),0) within_48,'
        'COALESCE(SUM(bill_collected),0) bills '
        'FROM appointment_events WHERE guild_id=? AND local_date BETWEEN ? AND ?',
        (guild_id,start,end)
    ).fetchone()
    sales=c.execute(
        'SELECT COUNT(*) c FROM sale_events WHERE guild_id=? AND local_date BETWEEN ? AND ?',
        (guild_id,start,end)
    ).fetchone()['c']
    closer_sales=c.execute(
        'SELECT COUNT(*) c FROM sale_events WHERE guild_id=? AND closer_id>0 AND local_date BETWEEN ? AND ?',
        (guild_id,start,end)
    ).fetchone()['c']
    c.close()

    appts=int(r['appts'] or 0)
    same_day=int(r['same_day'] or 0)
    within_48=int(r['within_48'] or 0)
    bills=int(r['bills'] or 0)
    over_48=max(0,appts-within_48)

    return {
        'appointments':appts,
        'setter_sales':int(sales or 0),
        'closer_sales':int(closer_sales or 0),
        'same_day':same_day,
        'within_48':within_48,
        'over_48':over_48,
        'bills':bills,
    }

def pct(n,d):
    return 0 if not d else round((n/d)*100)


MANUAL_BADGE_CHOICES = [app_commands.Choice(name=x,value=x) for x in DAILY+STREAK+WEEKLY]


@bot.tree.command(name='teamreport',description='Manager-only: instantly view team performance')
@app_commands.describe(period='Choose the report period')
@app_commands.choices(period=TEAM_REPORT_PERIOD_CHOICES)
async def teamreport(interaction:discord.Interaction,period:app_commands.Choice[str]):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message(
            '❌ Only users with the **Manager** role can use this.',
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    try:
        start,end,label=team_report_bounds(period.value)
        q=team_quality_totals(interaction.guild.id,start,end)

        top_appts=period_rows_between(interaction.guild.id,start,end,'appointments',5)
        top_setters=period_rows_between(interaction.guild.id,start,end,'setter_sales',5)
        top_closers=period_rows_between(interaction.guild.id,start,end,'closer_sales',5)

        snapshots=[
            setter_period_snapshot(interaction.guild,m,start,end)
            for m in setter_members(interaction.guild)
        ]
        snapshots.sort(
            key=lambda s:(-s['appointments'],-s['sales'],s['member'].display_name.lower())
        )

        e=discord.Embed(
            title='📈 CHOSEN GENESIS — INSTANT TEAM REPORT',
            description=f'**{label}** • {start} → {end}',
            timestamp=datetime.now(timezone.utc)
        )

        e.add_field(
            name='📊 TEAM TOTALS',
            value=(
                f'📅 Appointments: **{q["appointments"]}**\n'
                f'💰 Setter Sales: **{q["setter_sales"]}**\n'
                f'🤝 Closer Sales: **{q["closer_sales"]}**\n'
                f'🎯 Appt → Sale: **{pct(q["setter_sales"],q["appointments"])}%**'
            ),
            inline=False
        )

        e.add_field(
            name='⚡ APPOINTMENT QUALITY',
            value=(
                f'⚡ Same Day: **{q["same_day"]} ({pct(q["same_day"],q["appointments"])}%)**\n'
                f'⏰ Within 48: **{q["within_48"]} ({pct(q["within_48"],q["appointments"])}%)**\n'
                f'📆 Over 48: **{q["over_48"]} ({pct(q["over_48"],q["appointments"])}%)**\n'
                f'📄 Bills: **{q["bills"]} ({pct(q["bills"],q["appointments"])}%)**'
            ),
            inline=False
        )

        e.add_field(
            name='📅 TOP 5 APPOINTMENT SETTERS',
            value=fmt_ranked_members(interaction.guild,top_appts)[:1024],
            inline=False
        )
        e.add_field(
            name='💰 TOP 5 SETTER SALES',
            value=fmt_ranked_members(interaction.guild,top_setters)[:1024],
            inline=False
        )
        e.add_field(
            name='🤝 TOP 5 CLOSER SALES',
            value=fmt_ranked_members(interaction.guild,top_closers)[:1024],
            inline=False
        )

        # Keep the instant report compact enough for Discord's embed limits.
        watch=[]
        for s in snapshots:
            if s['appointments'] < COACHING_MIN_APPTS:
                continue
            if s['over_48_pct'] >= 40:
                watch.append(
                    f'📅 **{s["member"].display_name}** — {s["over_48_pct"]:.0f}% of apps >48h'
                )
            elif s['sales'] == 0:
                watch.append(
                    f'🔎 **{s["member"].display_name}** — {s["appointments"]} apps / 0 sales'
                )
            elif s['conversion'] < 15:
                watch.append(
                    f'📉 **{s["member"].display_name}** — {s["conversion"]:.0f}% conversion'
                )
            elif s['conversion'] >= 35 and s['appointments'] < 8:
                watch.append(
                    f'📈 **{s["member"].display_name}** — strong conversion; push volume'
                )

        if watch:
            e.add_field(
                name='📌 MANAGER WATCHLIST',
                value='\n'.join(watch[:6])[:1024],
                inline=False
            )

        pace=[]
        for s in snapshots[:10]:
            sales,expected,pace_label=monthly_pace_status(interaction.guild,s['member'])
            pace.append(
                f'**{s["member"].display_name}** — {sales}/{MONTHLY_SETTER_STANDARD} • {pace_label}'
            )
        if pace:
            e.add_field(
                name=f'🎯 MONTHLY {MONTHLY_SETTER_STANDARD}-DEAL STANDARD',
                value='\n'.join(pace)[:1024],
                inline=False
            )

        e.set_footer(text='Private instant manager view • Run /teamreport anytime')

        await interaction.followup.send(embed=e,ephemeral=True)

    except Exception as exc:
        print(
            f'[TEAMREPORT ERROR] guild={interaction.guild.id} '
            f'user={interaction.user.id} error={type(exc).__name__}: {exc}'
        )
        await interaction.followup.send(
            '⚠️ I hit an error generating the team report. The error was logged so it can be diagnosed.',
            ephemeral=True
        )


@bot.tree.command(name='midweekreview',description='Manager-only: send the current mid-week intelligence review to manager DMs')
async def midweekreview(interaction:discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message('❌ Only users with the **Manager** role can use this.',ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    result=await send_midweek_manager_review(interaction.guild,force=True)
    if result.get('sent'):
        await interaction.followup.send(
            f'✅ Mid-week review delivered to **{result["delivered"]}** Manager DM(s).',
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            '⚠️ The report was generated, but I could not DM any Managers. '
            'They may have DMs from server members turned off. Use `/teamreport` for the private in-Discord version.',
            ephemeral=True
        )


@bot.tree.command(name='weeklyreview',description='Manager-only: send the current week intelligence review to manager DMs')
async def weeklyreview(interaction:discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message('❌ Only users with the **Manager** role can use this.',ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    wk=wkey(now().date())
    result=await send_weekly_manager_summary(interaction.guild,wk,force=True)
    if result and result.get('delivered',0)>0:
        await interaction.followup.send(
            f'✅ Weekly review sent to **{result["delivered"]}** Manager DM(s).',
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            '⚠️ The weekly review could not be delivered to any Manager DMs. '
            'Check that Managers allow DMs from the server.',
            ephemeral=True
        )


@bot.tree.command(name='challenge',description='Manager-only: create a Chosen Genesis challenge')
@app_commands.describe(
    name='Unique challenge name',
    challenge_type='Daily, weekly, or custom',
    competitors='Who is competing?',
    metric='What stat should the bot track?',
    terms='Write the challenge rules/terms',
    goal='Optional number needed to win',
    prize='Optional prize',
    end_mode='How the challenge ends',
    end_behavior='If goal is missed by deadline, what happens?',
    deadline_date='Optional deadline date: YYYY-MM-DD',
    deadline_time='Optional deadline time: HH:MM (24-hour Arizona time)',
    person1='Selected competitor 1',
    person2='Selected competitor 2',
    person3='Selected competitor 3',
    person4='Selected competitor 4',
    person5='Selected competitor 5'
)
@app_commands.choices(
    challenge_type=CHALLENGE_TYPE_CHOICES,
    competitors=CHALLENGE_SCOPE_CHOICES,
    metric=CHALLENGE_METRIC_CHOICES,
    end_mode=CHALLENGE_END_CHOICES,
    end_behavior=CHALLENGE_BEHAVIOR_CHOICES
)
async def challenge(
    interaction:discord.Interaction,
    name:str,
    challenge_type:app_commands.Choice[str],
    competitors:app_commands.Choice[str],
    metric:app_commands.Choice[str],
    terms:str,
    end_mode:app_commands.Choice[str],
    end_behavior:app_commands.Choice[str],
    goal:int|None=None,
    prize:str|None=None,
    deadline_date:str|None=None,
    deadline_time:str|None=None,
    person1:discord.Member|None=None,
    person2:discord.Member|None=None,
    person3:discord.Member|None=None,
    person4:discord.Member|None=None,
    person5:discord.Member|None=None
):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message('❌ Only users with the **Manager** role can use this.',ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    scope=competitors.value
    selected=[person1,person2,person3,person4,person5]
    members=challenge_member_scope(interaction.guild,scope,selected)
    if scope=='selected' and not members:
        return await interaction.followup.send('❌ Select at least one competitor.',ephemeral=True)
    if not members:
        return await interaction.followup.send('❌ I could not find any eligible competitors for that scope.',ephemeral=True)

    deadline=None
    if end_mode.value in {'deadline','goal_or_deadline'}:
        deadline=parse_challenge_deadline(deadline_date,deadline_time)
        if deadline is None:
            return await interaction.followup.send(
                '❌ This end mode needs both a valid **deadline date (YYYY-MM-DD)** and **time (HH:MM)**.',
                ephemeral=True
            )
        if deadline<=now():
            return await interaction.followup.send('❌ The deadline must be in the future.',ephemeral=True)

    if end_mode.value=='goal_or_deadline' and (goal is None or goal<=0):
        return await interaction.followup.send('❌ Goal Reached mode needs a goal greater than 0.',ephemeral=True)
    if goal is not None and goal<=0:
        return await interaction.followup.send('❌ Goal must be greater than 0.',ephemeral=True)

    c=con()
    cur=c.execute(
        'INSERT INTO challenges(guild_id,name,challenge_type,scope,metric,terms,goal,prize,end_mode,end_behavior,deadline_at,status,created_by,created_at) '
        'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (
            interaction.guild.id,name.strip()[:80],challenge_type.value,scope,metric.value,
            terms.strip()[:800],goal,prize.strip()[:250] if prize else None,
            end_mode.value,end_behavior.value,deadline.isoformat() if deadline else None,
            'active',interaction.user.id,datetime.now(timezone.utc).isoformat()
        )
    )
    challenge_id=cur.lastrowid
    for member in members:
        c.execute(
            'INSERT OR IGNORE INTO challenge_participants(challenge_id,user_id,score) VALUES(?,?,0)',
            (challenge_id,member.id)
        )
    c.commit(); c.close()

    ch_row=challenge_row(challenge_id,interaction.guild.id)
    await render_challenge(interaction.guild,ch_row)
    await interaction.followup.send(
        f'✅ **{name}** created as Challenge **#{challenge_id}** with **{len(members)}** competitor(s).',
        ephemeral=True
    )



@bot.tree.command(name='challenge_adjust',description='Manager-only: adjust a competitor score in one challenge')
@app_commands.describe(
    challenge_id='Challenge number shown on the challenge post',
    member='Competitor whose challenge score should change',
    amount='Points to add or subtract, e.g. 1 or -1',
    reason='Optional reason for the adjustment'
)
async def challenge_adjust(
    interaction:discord.Interaction,
    challenge_id:int,
    member:discord.Member,
    amount:int,
    reason:str|None=None
):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message(
            '❌ Only users with the **Manager** role can use this.',
            ephemeral=True
        )
    if amount==0:
        return await interaction.response.send_message(
            '❌ Adjustment cannot be 0. Use a positive number to add points or a negative number to remove them.',
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)
    ch_row=challenge_row(challenge_id,interaction.guild.id)
    if not ch_row:
        return await interaction.followup.send('❌ Challenge not found.',ephemeral=True)
    if ch_row['status']!='active':
        return await interaction.followup.send('⚠️ You can only adjust an active challenge.',ephemeral=True)
    if member.id not in challenge_participant_ids(challenge_id):
        return await interaction.followup.send(
            '❌ That person is not a competitor in this challenge.',
            ephemeral=True
        )

    c=con()
    current=c.execute(
        'SELECT score FROM challenge_participants WHERE challenge_id=? AND user_id=?',
        (challenge_id,member.id)
    ).fetchone()
    old_score=int(current['score'] or 0)
    new_score=max(0,old_score+amount)
    applied=new_score-old_score

    c.execute(
        'UPDATE challenge_participants SET score=? WHERE challenge_id=? AND user_id=?',
        (new_score,challenge_id,member.id)
    )
    c.execute(
        'INSERT INTO challenge_adjustments(challenge_id,guild_id,user_id,amount,reason,adjusted_by,created_at) '
        'VALUES(?,?,?,?,?,?,?)',
        (
            challenge_id,interaction.guild.id,member.id,applied,
            reason.strip()[:300] if reason else None,
            interaction.user.id,datetime.now(timezone.utc).isoformat()
        )
    )
    c.commit(); c.close()

    fresh=challenge_row(challenge_id,interaction.guild.id)
    await render_challenge(interaction.guild,fresh)
    await evaluate_challenge(interaction.guild,fresh)

    sign='+' if applied>0 else ''
    reason_text=f' • {reason.strip()[:150]}' if reason and reason.strip() else ''
    await interaction.followup.send(
        f'✅ **{member.display_name}**: **{old_score} → {new_score}** '
        f'({sign}{applied}) in **{ch_row["name"]}**.{reason_text}',
        ephemeral=True
    )


@bot.tree.command(name='challenge_status',description='View the current status of a challenge')
@app_commands.describe(challenge_id='Challenge number shown on the challenge post')
async def challenge_status(interaction:discord.Interaction,challenge_id:int):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    ch_row=challenge_row(challenge_id,interaction.guild.id)
    if not ch_row:
        return await interaction.followup.send('❌ Challenge not found.',ephemeral=True)

    scores=challenge_scores(challenge_id)
    goal=int(ch_row['goal'] or 0)
    lines='\n'.join(
        challenge_score_line(interaction.guild,uid,score,goal,index=i)
        for i,(uid,score) in enumerate(scores[:20])
    ) or 'No competitors.'

    e=discord.Embed(
        title=f'⚔️ {ch_row["name"]} — Challenge #{challenge_id}',
        description=f'**Status:** {str(ch_row["status"]).upper()}\n📜 {ch_row["terms"]}',
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(name='CURRENT STANDINGS',value=lines,inline=False)
    await interaction.followup.send(embed=e,ephemeral=True)


@bot.tree.command(name='challenge_end',description='Manager-only: manually end one challenge')
@app_commands.describe(
    challenge_id='Challenge number',
    result='leader, winner, or no_winner',
    winner='Required only when result is winner'
)
@app_commands.choices(result=[
    app_commands.Choice(name='Declare Current Leader',value='leader'),
    app_commands.Choice(name='Choose Winner Manually',value='winner'),
    app_commands.Choice(name='End With No Winner',value='no_winner'),
])
async def challenge_end(
    interaction:discord.Interaction,
    challenge_id:int,
    result:app_commands.Choice[str],
    winner:discord.Member|None=None
):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message('❌ Only users with the **Manager** role can use this.',ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    ch_row=challenge_row(challenge_id,interaction.guild.id)
    if not ch_row:
        return await interaction.followup.send('❌ Challenge not found.',ephemeral=True)
    if ch_row['status']!='active':
        return await interaction.followup.send('⚠️ That challenge is already ended.',ephemeral=True)

    if result.value=='no_winner':
        await finish_challenge(interaction.guild,ch_row,[],'manager ended',no_winner=True)
    elif result.value=='winner':
        if winner is None:
            return await interaction.followup.send('❌ Choose a winner.',ephemeral=True)
        if winner.id not in challenge_participant_ids(challenge_id):
            return await interaction.followup.send('❌ That person is not a competitor in this challenge.',ephemeral=True)
        await finish_challenge(interaction.guild,ch_row,[winner.id],'manager selected winner')
    else:
        leaders,_=challenge_leaders(challenge_id)
        if not leaders:
            return await interaction.followup.send('❌ There is no current leader yet.',ephemeral=True)
        await finish_challenge(interaction.guild,ch_row,leaders,'manager declared current leader')

    await interaction.followup.send(f'✅ Challenge **#{challenge_id}** ended.',ephemeral=True)



@bot.tree.command(name='badges',description='Manager-only: privately view badge totals by period')
@app_commands.describe(period='Choose the time period',member='Optional: choose one person. Leave blank to see everyone.')
@app_commands.choices(period=BADGE_REPORT_PERIOD_CHOICES)
async def badges(interaction:discord.Interaction,period:app_commands.Choice[str],member:discord.Member|None=None):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message('❌ Only users with the **Manager** role can use this.',ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    start,end,label=badge_report_bounds(period.value)

    if member is not None:
        counts=badge_counts_between(interaction.guild.id,member.id,start,end)
        total=sum(counts.values())
        lines=[f'**{badge}** — {count}' for badge,count in sorted(counts.items(),key=lambda x:(-x[1],x[0]))]

        e=discord.Embed(
            title=f'🏅 {member.display_name.upper()} — BADGES',
            description=f'**{label}** • {start} → {end}',
            timestamp=datetime.now(timezone.utc)
        )
        e.add_field(name='TOTAL',value=f'**{total} badge{"s" if total!=1 else ""}**',inline=False)
        e.add_field(name='BREAKDOWN',value='\n'.join(lines) if lines else 'No badges earned in this period.',inline=False)
        e.set_footer(text='Private Manager View • Chosen Genesis')
        return await interaction.followup.send(embed=e,ephemeral=True)

    results=all_badge_totals_between(interaction.guild,start,end)
    ranking=[]
    for i,(m,total,_) in enumerate(results[:20],1):
        prefix=['🥇','🥈','🥉'][i-1] if i<=3 else f'#{i}'
        ranking.append(f'{prefix} **{m.display_name}** — **{total}**')

    e=discord.Embed(
        title='🏆 CHOSEN GENESIS — BADGE TOTALS',
        description=f'**{label}** • {start} → {end}',
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(name='ALL REPS',value='\n'.join(ranking) if ranking else 'No badges earned in this period.',inline=False)
    e.set_footer(text='Private Manager View • Add a member to /badges for a breakdown')
    await interaction.followup.send(embed=e,ephemeral=True)

@bot.tree.command(name='givebadge',description='Manager-only: add a badge to someone’s history/count')
@app_commands.describe(
    member='Who gets the badge',
    badge='Badge to give',
    announce='Announce the manual award?'
)
@app_commands.choices(badge=MANUAL_BADGE_CHOICES)
async def givebadge(
    interaction:discord.Interaction,
    member:discord.Member,
    badge:app_commands.Choice[str],
    announce:bool=True
):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message(
            '❌ Only users with the **Manager** role can use this.',
            ephemeral=True
        )

    # Acknowledge immediately so Discord never times the command out.
    await interaction.response.defer(ephemeral=True)

    badge_name=badge.value
    manual_key=f'manual:{dkey()}:{interaction.id}'

    added=award_badge_count(
        interaction.guild.id,
        member.id,
        badge_name,
        manual_key
    )

    if not added:
        return await interaction.followup.send(
            f'⚠️ That manual **{badge_name}** award was already recorded.',
            ephemeral=True
        )

    # IMPORTANT:
    # Manual awards are history/count only. Do NOT assign the Discord badge role.
    # Live roles are reserved for the actual daily/weekly winners so manually
    # correcting someone's badge count cannot change the leaderboard.
    await announce_badge_milestone(
        interaction.guild,
        member.id,
        badge_name
    )

    await interaction.followup.send(
        f'✅ Added **{badge_name}** to {member.mention}’s badge history/count.\n'
        f'It **will not change the live daily leaderboard**.',
        ephemeral=True
    )

    if announce:
        await main(
            interaction.guild,
            content=f'🏅 **MANAGER BADGE AWARD** — {member.mention} earned **{badge_name}**!'
        )


@bot.tree.command(name='removebadge',description='Manager-only: remove one recorded badge award')
@app_commands.describe(
    member='Who loses one recorded badge',
    badge='Badge to remove',
    announce='Announce the correction?'
)
@app_commands.choices(badge=MANUAL_BADGE_CHOICES)
async def removebadge(
    interaction:discord.Interaction,
    member:discord.Member,
    badge:app_commands.Choice[str],
    announce:bool=False
):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message(
            '❌ Only users with the **Manager** role can use this.',
            ephemeral=True
        )

    # Defer first. The old command refreshed the leaderboard before responding,
    # which could exceed Discord's interaction timeout and show
    # "Application did not respond."
    await interaction.response.defer(ephemeral=True)

    badge_name=badge.value
    c=con()

    # Prefer removing a manual award first. If there is no manual correction,
    # remove the most recent recorded award for that badge.
    row=c.execute(
        'SELECT rowid,award_key FROM badge_awards '
        'WHERE guild_id=? AND user_id=? AND badge_name=? '
        'ORDER BY CASE WHEN award_key LIKE ? THEN 0 ELSE 1 END, '
        'created_at DESC,rowid DESC LIMIT 1',
        (
            interaction.guild.id,
            member.id,
            badge_name,
            'manual:%'
        )
    ).fetchone()

    if row:
        c.execute('DELETE FROM badge_awards WHERE rowid=?',(row['rowid'],))
        c.commit()
    c.close()

    if not row:
        return await interaction.followup.send(
            f'⚠️ No recorded **{badge_name}** award found for {member.mention}.',
            ephemeral=True
        )

    # Do NOT remove the Discord role here. Live badge roles are controlled by
    # the automatic daily/weekly competition system, not manual history edits.
    remaining=badge_count_for(
        interaction.guild.id,
        member.id,
        badge_name
    )

    await interaction.followup.send(
        f'✅ Removed one recorded **{badge_name}** from {member.mention}.\n'
        f'Remaining count: **{remaining}**. The live leaderboard was not changed.',
        ephemeral=True
    )

    if announce:
        await main(
            interaction.guild,
            content=f'🛠️ **BADGE CORRECTION** — one **{badge_name}** award was removed from {member.mention}.'
        )



@bot.tree.command(name='dailyawards',description='Manager-only: post or re-post today’s Daily Awards')
async def dailyawards(interaction:discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message(
            '❌ Only users with the **Manager** role can use this.',
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)
    az=awards_now()
    posted=await post_daily_awards(interaction.guild,az.date(),force=True)

    if posted:
        await interaction.followup.send(
            f'✅ Daily Awards posted for **{az.strftime("%B %d")}**.',
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            '⚠️ I found **0 appointments and 0 sales** for today, so there was nothing to post.',
            ephemeral=True
        )


@bot.tree.command(name='bootcamp',description='Greenie: submit a bootcamp attendance for manager approval')
async def bootcamp_submit(interaction:discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_greenie(interaction.user):
        return await interaction.response.send_message('❌ This command is for members with the **Greenie** role.',ephemeral=True)
    if approved_bootcamp_count(interaction.guild.id,interaction.user.id)>=3:
        return await interaction.response.send_message('✅ You already have all **3/3 approved bootcamps**.',ephemeral=True)

    # One pending bootcamp at a time prevents duplicate submissions/spam.
    if pending_bootcamp_count(interaction.guild.id,interaction.user.id)>0:
        return await interaction.response.send_message(
            '⏳ You already have a **pending bootcamp** waiting for Manager approval.',
            ephemeral=True
        )

    c=con()
    c.execute(
        "INSERT INTO bootcamp_submissions(guild_id,user_id,submitted_at,status) VALUES(?,?,?,'pending')",
        (interaction.guild.id,interaction.user.id,datetime.now(timezone.utc).isoformat())
    )
    c.commit(); c.close()

    await interaction.response.send_message(
        '🏕️ Bootcamp submitted. A **Manager must approve it** before it counts toward your 3 required bootcamps.',
        ephemeral=True
    )
    ch=await bootcamp_channel(interaction.guild)
    if ch:
        await ch.send(
            f'🏕️ **BOOTCAMP APPROVAL NEEDED**\n{interaction.user.mention} submitted a bootcamp attendance.\n'
            f'Current approved: **{approved_bootcamp_count(interaction.guild.id,interaction.user.id)}/3**'
        )


@bot.tree.command(name='approvebootcamp',description='Manager-only: approve one pending Greenie bootcamp')
@app_commands.describe(member='Greenie whose pending bootcamp you are approving')
async def approvebootcamp(interaction:discord.Interaction,member:discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message('❌ Only Managers can approve bootcamps.',ephemeral=True)
    if not is_greenie(member):
        return await interaction.response.send_message('❌ That member does not have the **Greenie** role.',ephemeral=True)

    c=con()
    row=c.execute(
        "SELECT id FROM bootcamp_submissions WHERE guild_id=? AND user_id=? AND status='pending' ORDER BY id ASC LIMIT 1",
        (interaction.guild.id,member.id)
    ).fetchone()
    if not row:
        c.close()
        return await interaction.response.send_message('❌ That Greenie has no pending bootcamp submission.',ephemeral=True)
    if approved_bootcamp_count(interaction.guild.id,member.id)>=3:
        c.close()
        return await interaction.response.send_message('✅ They already have 3/3 approved bootcamps.',ephemeral=True)

    c.execute(
        "UPDATE bootcamp_submissions SET status='approved',reviewed_by=?,reviewed_at=? WHERE id=?",
        (interaction.user.id,datetime.now(timezone.utc).isoformat(),row['id'])
    )
    c.commit(); c.close()

    count=approved_bootcamp_count(interaction.guild.id,member.id)
    await interaction.response.send_message(f'✅ Approved. {member.mention} is now at **{count}/3 bootcamps**.',ephemeral=True)
    await post_greenie_status(interaction.guild,member)


@bot.tree.command(name='pitchvideo',description='Greenie: submit your pitch video for manager approval')
@app_commands.describe(video='Upload your pitch video')
async def pitchvideo(interaction:discord.Interaction,video:discord.Attachment):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_greenie(interaction.user):
        return await interaction.response.send_message('❌ This command is for members with the **Greenie** role.',ephemeral=True)

    if pending_pitch_submission(interaction.guild.id,interaction.user.id):
        return await interaction.response.send_message(
            '⏳ You already have a **pitch waiting for Manager review**. Wait for approval/rejection before submitting another.',
            ephemeral=True
        )

    ensure_greenie_progress(interaction.guild.id,interaction.user.id)
    submitted_at=datetime.now(timezone.utc).isoformat()

    c=con()
    cur=c.execute(
        "INSERT INTO pitch_submissions(guild_id,user_id,video_url,filename,submitted_at,status) "
        "VALUES(?,?,?,?,?,'pending')",
        (interaction.guild.id,interaction.user.id,video.url,video.filename,submitted_at)
    )
    submission_id=cur.lastrowid

    # Current-status table points at newest submission, but history remains intact.
    c.execute(
        'UPDATE greenie_progress SET pitch_url=?,pitch_filename=?,pitch_submitted_at=?,'
        'pitch_approved=0,pitch_approved_by=NULL,pitch_approved_at=NULL,'
        'graduation_requested=0,graduation_requested_at=NULL '
        'WHERE guild_id=? AND user_id=?',
        (video.url,video.filename,submitted_at,interaction.guild.id,interaction.user.id)
    )
    c.commit(); c.close()

    await interaction.response.send_message(
        f'🎥 Pitch **#{submission_id}** submitted for **Manager approval**.',
        ephemeral=True
    )

    ch=await bootcamp_channel(interaction.guild)
    if ch:
        e=discord.Embed(
            title='🎥 PITCH APPROVAL NEEDED',
            description=(
                f'{interaction.user.mention} submitted pitch **#{submission_id}**.\n'
                f'**File:** {video.filename}\n'
                f'**Attempt:** {pitch_history_count(interaction.guild.id,interaction.user.id)}'
            ),
            timestamp=datetime.now(timezone.utc)
        )
        e.add_field(name='Video',value=video.url,inline=False)
        await ch.send(embed=e)


@bot.tree.command(name='approvepitch',description='Manager-only: approve a Greenie pitch video')
@app_commands.describe(member='Greenie whose pending pitch you are approving')
async def approvepitch(interaction:discord.Interaction,member:discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message('❌ Only Managers can approve pitch videos.',ephemeral=True)
    if not is_greenie(member):
        return await interaction.response.send_message('❌ That member is not currently a Greenie.',ephemeral=True)

    submission=pending_pitch_submission(interaction.guild.id,member.id)
    if not submission:
        return await interaction.response.send_message('❌ That Greenie has no pending pitch submission.',ephemeral=True)

    reviewed_at=datetime.now(timezone.utc).isoformat()
    c=con()
    c.execute(
        "UPDATE pitch_submissions SET status='approved',reviewed_by=?,reviewed_at=?,rejection_reason=NULL WHERE id=?",
        (interaction.user.id,reviewed_at,submission['id'])
    )
    c.execute(
        'UPDATE greenie_progress SET pitch_url=?,pitch_filename=?,pitch_submitted_at=?,'
        'pitch_approved=1,pitch_approved_by=?,pitch_approved_at=? '
        'WHERE guild_id=? AND user_id=?',
        (
            submission['video_url'],submission['filename'],submission['submitted_at'],
            interaction.user.id,reviewed_at,interaction.guild.id,member.id
        )
    )
    c.commit(); c.close()

    await interaction.response.send_message(
        f'✅ {member.mention}’s pitch **#{submission["id"]}** is approved.',
        ephemeral=True
    )
    await post_greenie_status(interaction.guild,member)


@bot.tree.command(name='rejectpitch',description='Manager-only: reject a Greenie pitch and give a reason')
@app_commands.describe(
    member='Greenie whose pending pitch you are rejecting',
    reason='What they need to fix before resubmitting'
)
async def rejectpitch(interaction:discord.Interaction,member:discord.Member,reason:str):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message('❌ Only Managers can reject pitch videos.',ephemeral=True)
    if not is_greenie(member):
        return await interaction.response.send_message('❌ That member is not currently a Greenie.',ephemeral=True)

    submission=pending_pitch_submission(interaction.guild.id,member.id)
    if not submission:
        return await interaction.response.send_message('❌ That Greenie has no pending pitch submission.',ephemeral=True)

    reviewed_at=datetime.now(timezone.utc).isoformat()
    clean_reason=reason.strip()[:500]

    c=con()
    c.execute(
        "UPDATE pitch_submissions SET status='rejected',reviewed_by=?,reviewed_at=?,rejection_reason=? WHERE id=?",
        (interaction.user.id,reviewed_at,clean_reason,submission['id'])
    )
    c.execute(
        'UPDATE greenie_progress SET pitch_approved=0,pitch_approved_by=NULL,pitch_approved_at=NULL '
        'WHERE guild_id=? AND user_id=?',
        (interaction.guild.id,member.id)
    )
    c.commit(); c.close()

    await interaction.response.send_message(
        f'✅ Pitch **#{submission["id"]}** rejected. {member.mention} can now submit a new version.',
        ephemeral=True
    )

    ch=await bootcamp_channel(interaction.guild)
    if ch:
        e=discord.Embed(
            title='🔁 PITCH NEEDS WORK',
            description=(
                f'{member.mention} — pitch **#{submission["id"]}** was not approved.\n\n'
                f'**Manager feedback:** {clean_reason}\n\n'
                f'Use `/pitchvideo` when the updated pitch is ready.'
            ),
            timestamp=datetime.now(timezone.utc)
        )
        await ch.send(embed=e)

    await post_greenie_status(interaction.guild,member)


@bot.tree.command(name='greenie',description='View a Greenie’s onboarding progress')
@app_commands.describe(member='Greenie to view; leave blank to view yourself')
async def greenie(interaction:discord.Interaction,member:discord.Member|None=None):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    target=member or interaction.user
    if target.id!=interaction.user.id and not is_manager(interaction.user):
        return await interaction.response.send_message('❌ Only Managers can view another Greenie’s private status.',ephemeral=True)
    if not is_greenie(target):
        return await interaction.response.send_message('❌ That member is not currently a Greenie.',ephemeral=True)
    await interaction.response.send_message(embed=greenie_status_embed(interaction.guild,target),ephemeral=True)


@bot.tree.command(name='graduation_request',description='Greenie: request manager approval for graduation')
async def graduation_request(interaction:discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_greenie(interaction.user):
        return await interaction.response.send_message('❌ This command is for Greenies.',ephemeral=True)
    if not greenie_ready(interaction.guild.id,interaction.user.id):
        p=greenie_progress(interaction.guild.id,interaction.user.id)
        return await interaction.response.send_message(
            f'❌ Not ready yet. You need **3/3 approved bootcamps** and an **approved pitch**.\n'
            f'Bootcamps: **{approved_bootcamp_count(interaction.guild.id,interaction.user.id)}/3** • '
            f'Pitch approved: **{"Yes" if int(p["pitch_approved"] or 0) else "No"}**',
            ephemeral=True
        )

    c=con()
    c.execute(
        'UPDATE greenie_progress SET graduation_requested=1,graduation_requested_at=? WHERE guild_id=? AND user_id=?',
        (datetime.now(timezone.utc).isoformat(),interaction.guild.id,interaction.user.id)
    )
    c.commit(); c.close()

    await interaction.response.send_message('🎓 Graduation request submitted. **Manager approval is required.**',ephemeral=True)
    ch=await bootcamp_channel(interaction.guild)
    if ch:
        await ch.send(
            f'🎓 **READY FOR GRADUATION**\n{interaction.user.mention} has completed:\n'
            f'✅ 3/3 approved bootcamps\n✅ Pitch submitted + approved\n\n'
            f'**Manager:** use `/graduation` when approved.'
        )


@bot.tree.command(name='graduation',description='Manager-only: graduate an approved Greenie to Setter')
@app_commands.describe(member='Greenie who completed onboarding')
async def graduation(interaction:discord.Interaction,member:discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message('❌ Only users with the **Manager** role can use this.',ephemeral=True)
    if not is_greenie(member):
        return await interaction.response.send_message('❌ That member does not currently have the **Greenie** role.',ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    ensure_member_state(interaction.guild.id,member.id)
    p=greenie_progress(interaction.guild.id,member.id)
    bootcamps=approved_bootcamp_count(interaction.guild.id,member.id)

    if bootcamps<3 or not int(p['pitch_approved'] or 0):
        return await interaction.followup.send(
            f'❌ {member.mention} has not completed the graduation requirements.\n'
            f'🏕️ Bootcamps: **{bootcamps}/3**\n'
            f'🎥 Pitch approved: **{"Yes" if int(p["pitch_approved"] or 0) else "No"}**',
            ephemeral=True
        )

    if not int(p['graduation_requested'] or 0):
        return await interaction.followup.send(
            f'⏳ {member.mention} has completed the training requirements, but they still need to use '
            f'**/graduation_request** before a Manager can graduate them.',
            ephemeral=True
        )

    greenie_role=discord.utils.get(interaction.guild.roles,name='Greenie')
    setter_role=discord.utils.get(interaction.guild.roles,name='Setter')
    if setter_role is None:
        setter_role=await interaction.guild.create_role(name='Setter',reason='Chosen Genesis graduation')

    try:
        await member.add_roles(setter_role,reason='Chosen Genesis graduation')
        if greenie_role and greenie_role in member.roles:
            await member.remove_roles(greenie_role,reason='Chosen Genesis graduation')
    except discord.Forbidden:
        return await interaction.followup.send(
            '❌ I could not change the roles. Put the bot role **above Greenie and Setter** in Server Settings → Roles.',
            ephemeral=True
        )

    c=con()
    c.execute(
        'UPDATE member_state SET onboarding=0,graduated_date=? WHERE guild_id=? AND user_id=?',
        (dkey(),interaction.guild.id,member.id)
    )

    # Graduation is the exact handoff into Setter accountability. Do not carry
    # any pre-graduation attendance status into their Setter record.
    c.execute(
        'DELETE FROM attendance_records WHERE guild_id=? AND user_id=? AND local_date=?',
        (interaction.guild.id,member.id,dkey())
    )
    c.commit(); c.close()

    e=discord.Embed(
        title='🎓 CHOSEN GENESIS — GRADUATION',
        description=(
            f'{member.mention} has officially completed onboarding.\n\n'
            f'✅ 3/3 Bootcamps\n'
            f'✅ Pitch Approved\n'
            f'✅ Promoted **Greenie → Setter**\n\n'
            f'**Training wheels are off. You’re on the board now. 🔥**'
        ),
        timestamp=datetime.now(timezone.utc)
    )
    e.set_footer(text='Chosen Genesis')
    await main(interaction.guild,embed=e)
    await interaction.followup.send(
        f'✅ {member.mention} graduated. Setter accountability begins now.',
        ephemeral=True
    )




@bot.tree.command(name='checkin',description='Check in for the day with a required photo')
@app_commands.describe(photo='Upload your check-in photo')
async def checkin(interaction:discord.Interaction,photo:discord.Attachment):
    if not interaction.guild:
        return await interaction.response.send_message(
            'Use this command inside the server.',
            ephemeral=True
        )

    if not is_image_attachment(photo):
        return await interaction.response.send_message(
            '❌ Your check-in must include an image/photo.',
            ephemeral=True
        )

    existing=get_today_checkin(interaction.guild.id,interaction.user.id)
    if existing:
        return await interaction.response.send_message(
            f'✅ You already checked in today at **{existing["local_time"]}**.',
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    n=now()
    local_date=n.date().isoformat()
    local_time=n.strftime('%-I:%M %p')

    c=con()
    try:
        c.execute(
            'INSERT INTO checkins(guild_id,user_id,local_date,local_time,photo_url,photo_filename,created_at) '
            'VALUES(?,?,?,?,?,?,?)',
            (
                interaction.guild.id,
                interaction.user.id,
                local_date,
                local_time,
                photo.url,
                photo.filename,
                datetime.now(timezone.utc).isoformat()
            )
        )
        c.commit()
    except sqlite3.IntegrityError:
        c.close()
        return await interaction.followup.send(
            '✅ You already checked in today.',
            ephemeral=True
        )
    c.close()

    attendance_status=attendance_status_for_checkin(
        interaction.guild,
        interaction.user,
        n.replace(tzinfo=None)
    )
    if attendance_status in {'on_time','late'}:
        upsert_attendance(interaction.guild,interaction.user,local_date,attendance_status,local_time)

    status,_,_=checkin_status_for_member(interaction.guild,interaction.user,n.replace(tzinfo=None))
    freedom_line=''
    # Keep public check-ins clean. Greenies can check in normally without a
    # public "not tracked" label. Earned Freedom is shown only for Setters.
    if has_named_role(interaction.user,'Setter') and not is_greenie(interaction.user) and status in {'freedom','freedom_grace'}:
        deals=previous_month_setter_deals(interaction.guild.id,interaction.user.id)
        freedom_line=f'\n🔓 **Earned Freedom — {deals} deals last month**'

    e=discord.Embed(
        title='📸 CHOSEN GENESIS — CHECK IN',
        description=(
            f'🫡 **{interaction.user.mention} checked in**\n'
            f'🕐 **{local_time}**'
            f'{freedom_line}\n\n'
            '**Locked in. Let’s work. 🔥**'
        ),
        timestamp=datetime.now(timezone.utc)
    )
    e.set_image(url=photo.url)
    e.set_footer(text='Chosen Genesis')

    await main(interaction.guild,embed=e)
    await interaction.followup.send(
        f'✅ Check-in recorded for **{local_time}**.',
        ephemeral=True
    )



ATTENDANCE_PERIOD_CHOICES = [
    app_commands.Choice(name='Today',value='today'),
    app_commands.Choice(name='Yesterday',value='yesterday'),
    app_commands.Choice(name='This Week',value='this_week'),
    app_commands.Choice(name='Last Week',value='last_week'),
]

def attendance_period_bounds(value):
    today=now().date()
    if value=='today':
        return today,today,'Today'
    if value=='yesterday':
        d=today-timedelta(days=1)
        return d,d,'Yesterday'
    if value=='this_week':
        start=today-timedelta(days=today.weekday())
        return start,today,'This Week'
    if value=='last_week':
        this_start=today-timedelta(days=today.weekday())
        end=this_start-timedelta(days=1)
        start=end-timedelta(days=6)
        return start,end,'Last Week'
    return today,today,'Today'

def attendance_setters_for_period(guild,start,end):
    # Current graduated setters plus anyone with attendance history in the period.
    members={
        m.id:m for m in guild.members
        if not m.bot and has_named_role(m,'Setter') and not is_greenie(m)
    }
    c=con()
    rows=c.execute(
        'SELECT DISTINCT user_id FROM attendance_records WHERE guild_id=? AND local_date BETWEEN ? AND ?',
        (guild.id,start.isoformat(),end.isoformat())
    ).fetchall()
    c.close()
    for r in rows:
        m=guild.get_member(r['user_id'])
        if m and not m.bot:
            members[m.id]=m
    return sorted(members.values(),key=lambda m:m.display_name.lower())

def attendance_day_snapshot(guild,member,day):
    if day.weekday()==6:
        return None
    ds=day.isoformat()
    c=con()
    ar=c.execute(
        'SELECT status,checkin_time,earned_freedom FROM attendance_records '
        'WHERE guild_id=? AND user_id=? AND local_date=?',
        (guild.id,member.id,ds)
    ).fetchone()
    ci=c.execute(
        'SELECT local_time FROM checkins WHERE guild_id=? AND user_id=? AND local_date=?',
        (guild.id,member.id,ds)
    ).fetchone()
    co=c.execute(
        'SELECT status,checkout_time FROM checkout_records '
        'WHERE guild_id=? AND user_id=? AND local_date=?',
        (guild.id,member.id,ds)
    ).fetchone()
    raw_co=c.execute(
        'SELECT local_time FROM checkouts WHERE guild_id=? AND user_id=? AND local_date=?',
        (guild.id,member.id,ds)
    ).fetchone()
    c.close()

    status=(ar['status'] if ar else None)
    checkin_time=(ar['checkin_time'] if ar and ar['checkin_time'] else (ci['local_time'] if ci else None))
    checkout_status=(co['status'] if co else None)
    checkout_time=(co['checkout_time'] if co and co['checkout_time'] else (raw_co['local_time'] if raw_co else None))

    # Historical rows are the source of truth. If a raw check-in exists but the
    # finalized attendance row is absent, count it as checked in rather than missed.
    if not status and checkin_time:
        status='on_time'
    if not checkout_status and checkout_time:
        checkout_status='checked_out'

    return {
        'status':status or 'missed',
        'checkin_time':checkin_time,
        'checkout_status':checkout_status or 'missed',
        'checkout_time':checkout_time,
    }

def weekly_attendance_lines(guild,start,end):
    lines=[]
    for member in attendance_setters_for_period(guild,start,end):
        on=late=missed=checkouts=expected=0
        d=start
        while d<=end:
            if d.weekday()!=6:
                snap=attendance_day_snapshot(guild,member,d)
                expected+=1
                st=snap['status']
                if st=='late':
                    late+=1
                elif st=='missed':
                    missed+=1
                else:
                    on+=1
                if snap['checkout_status']!='missed':
                    checkouts+=1
            d+=timedelta(days=1)
        lines.append(
            f'**{member.display_name}** — ✅ {on} | ⚠️ {late} | ❌ {missed} | 🚪 {checkouts}/{expected}'
        )
    return lines

def add_attendance_summary_to_embed(guild,e,start,end):
    s=datetime.strptime(start,'%Y-%m-%d').date() if isinstance(start,str) else start
    en=datetime.strptime(end,'%Y-%m-%d').date() if isinstance(end,str) else end
    lines=weekly_attendance_lines(guild,s,en)
    if lines:
        e.add_field(
            name='🕐 ATTENDANCE SUMMARY',
            value='\n'.join(lines[:12])[:1024],
            inline=False
        )
    return e

@bot.tree.command(name='attendance',description='Manager-only: view daily or weekly setter attendance')
@app_commands.describe(period='Choose the attendance period')
@app_commands.choices(period=ATTENDANCE_PERIOD_CHOICES)
async def attendance(interaction:discord.Interaction,period:app_commands.Choice[str]):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message(
            '❌ Only users with the **Manager** role can use this.',ephemeral=True
        )
    await interaction.response.defer(ephemeral=True)
    try:
        start,end,label=attendance_period_bounds(period.value)
        e=discord.Embed(
            title='🕐 CHOSEN GENESIS — ATTENDANCE',
            description=f'**{label}** • {start.isoformat()} → {end.isoformat()}',
            timestamp=datetime.now(timezone.utc)
        )

        if start==end:
            if start.weekday()==6:
                e.add_field(name='☀️ OFF DAY',value='Sunday — no attendance accountability.',inline=False)
            else:
                rows=[]
                for member in attendance_setters_for_period(interaction.guild,start,end):
                    s=attendance_day_snapshot(interaction.guild,member,start)
                    icon='⚠️' if s['status']=='late' else ('❌' if s['status']=='missed' else '✅')
                    ci=f' • IN {s["checkin_time"]}' if s['checkin_time'] else ''
                    co_icon='🚪' if s['checkout_status']!='missed' else '❌'
                    co=f'{co_icon} OUT {s["checkout_time"]}' if s['checkout_time'] else f'{co_icon} OUT'
                    rows.append(f'{icon} **{member.display_name}**{ci} • {co}')
                e.add_field(name='SETTER ATTENDANCE',value='\n'.join(rows)[:1024] if rows else 'No tracked setters.',inline=False)
        else:
            lines=weekly_attendance_lines(interaction.guild,start,end)
            e.add_field(
                name='WEEKLY SUMMARY',
                value='\n'.join(lines)[:1024] if lines else 'No tracked setters.',
                inline=False
            )
            e.add_field(
                name='KEY',
                value='✅ On Time • ⚠️ Late • ❌ Missed • 🚪 Checkouts completed / workdays',
                inline=False
            )
        e.set_footer(text='Private Manager view • Greenies and Sundays excluded from accountability')
        await interaction.followup.send(embed=e,ephemeral=True)
    except Exception as exc:
        print(f'[ATTENDANCE ERROR] guild={interaction.guild.id} error={type(exc).__name__}: {exc}')
        await interaction.followup.send('⚠️ I hit an error generating attendance. Check Railway logs for ATTENDANCE ERROR.',ephemeral=True)


@bot.tree.command(name='checkins',description='Manager-only: see today’s setter check-ins')
async def checkins(interaction:discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message('❌ Only users with the **Manager** role can use this.',ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    if not is_workday(now().date()):
        e=discord.Embed(
            title='📋 CHOSEN GENESIS — TODAY’S SETTER CHECK-INS',
            description='☀️ **Sunday is an off day. No attendance tracking today.**',
            timestamp=datetime.now(timezone.utc)
        )
        return await interaction.followup.send(embed=e,ephemeral=True)

    rows=today_checkins(interaction.guild.id)
    by_user={r['user_id']:r for r in rows}
    on_time=[]; late=[]; missed=[]

    # Only graduated Setters are part of attendance accountability.
    setters=[
        m for m in interaction.guild.members
        if not m.bot and has_named_role(m,'Setter') and not is_greenie(m)
    ]

    for member in setters:

        row=by_user.get(member.id)
        if row:
            dt=parse_checkin_local_datetime(row)
            status=attendance_status_for_checkin(interaction.guild,member,dt)
            if status=='late':
                late.append(f'⚠️ **{member.display_name}** — {row["local_time"]}')
            else:
                freedom=' 🔓' if has_earned_freedom(interaction.guild.id,member.id) else ''
                on_time.append(f'✅ **{member.display_name}** — {row["local_time"]}{freedom}')
        else:
            current_minutes=minutes_since_midnight(now().hour,now().minute)

            # Monday/Thursday meeting days use a hard 4:00 PM cutoff.
            if now().weekday() in {0,3}:
                miss_after=minutes_since_midnight(16,0)
            elif has_earned_freedom(interaction.guild.id,member.id):
                miss_after=minutes_since_midnight(FREEDOM_CUTOFF_HOUR,FREEDOM_CUTOFF_MINUTE)+FREEDOM_GRACE_MINUTES
            else:
                miss_after=minutes_since_midnight(REGULAR_CHECKIN_HOUR,REGULAR_CHECKIN_MINUTE)+REGULAR_GRACE_MINUTES

            if current_minutes>miss_after:
                missed.append(f'❌ **{member.display_name}**')
                upsert_attendance(interaction.guild,member,dkey(),'missed',None)

    e=discord.Embed(
        title='📋 CHOSEN GENESIS — TODAY’S SETTER CHECK-INS',
        description=(
            f'**{now().strftime("%A, %B %d")}**\n'
            + (
                '📅 Meeting Day — hard check-in cutoff: **4:00 PM**'
                if now().weekday() in {0,3}
                else 'Regular final cutoff: **10:20 AM**\nEarned Freedom final cutoff: **11:35 AM**'
            )
        ),
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(name='✅ ON TIME',value='\n'.join(on_time) or 'None',inline=False)
    e.add_field(name='⚠️ LATE',value='\n'.join(late) or 'None',inline=False)
    e.add_field(name='❌ MISSED',value='\n'.join(missed) or 'None',inline=False)
    e.set_footer(text='Private manager view • Chosen Genesis')
    await interaction.followup.send(embed=e,ephemeral=True)




@bot.tree.command(name='checkout',description='Check out for the day with a required photo')
@app_commands.describe(photo='Upload your checkout photo')
async def checkout(interaction:discord.Interaction,photo:discord.Attachment):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)

    if not is_image_attachment(photo):
        return await interaction.response.send_message(
            '❌ Your checkout must include an image/photo.',
            ephemeral=True
        )

    existing=get_today_checkout(interaction.guild.id,interaction.user.id)
    if existing:
        return await interaction.response.send_message(
            f'✅ You already checked out today at **{existing["local_time"]}**.',
            ephemeral=True
        )

    n=now()

    # Earned Freedom Setters (4+ setter deals last month) can check out at 4:00 PM.
    # All other graduated Setters can check out at 7:50 PM.
    if has_named_role(interaction.user,'Setter') and not is_greenie(interaction.user):
        earned_freedom=has_earned_freedom(interaction.guild.id,interaction.user.id)
        earliest_minutes=minutes_since_midnight(16,0) if earned_freedom else minutes_since_midnight(
            CHECKOUT_EARLIEST_HOUR,CHECKOUT_EARLIEST_MINUTE
        )
        current_minutes=minutes_since_midnight(n.hour,n.minute)

        if current_minutes < earliest_minutes:
            cutoff='4:00 PM' if earned_freedom else '7:50 PM'
            freedom_note=' 🔓 Earned Freedom' if earned_freedom else ''
            return await interaction.response.send_message(
                f'⏰ Your checkout opens at **{cutoff}**.{freedom_note}',
                ephemeral=True
            )

    await interaction.response.defer(ephemeral=True)

    local_date=n.date().isoformat()
    local_time=n.strftime('%-I:%M %p')

    c=con()
    try:
        c.execute(
            'INSERT INTO checkouts(guild_id,user_id,local_date,local_time,photo_url,photo_filename,created_at) '
            'VALUES(?,?,?,?,?,?,?)',
            (
                interaction.guild.id,interaction.user.id,local_date,local_time,
                photo.url,photo.filename,datetime.now(timezone.utc).isoformat()
            )
        )
        c.commit()
    except sqlite3.IntegrityError:
        c.close()
        return await interaction.followup.send('✅ You already checked out today.',ephemeral=True)
    c.close()

    # Greenies can participate in the photo ritual, but only Setters are tracked.
    if has_named_role(interaction.user,'Setter') and not is_greenie(interaction.user) and is_workday(n.date()):
        upsert_checkout_record(
            interaction.guild,interaction.user,local_date,'completed',local_time
        )

    e=discord.Embed(
        title='🌙 CHOSEN GENESIS — CHECK OUT',
        description=(
            f'✅ **{interaction.user.mention} checked out**\n'
            f'🕐 **{local_time}**\n\n'
            '**Day in the books. 🔥**'
        ),
        timestamp=datetime.now(timezone.utc)
    )
    e.set_image(url=photo.url)
    e.set_footer(text='Chosen Genesis')

    await main(interaction.guild,embed=e)
    await interaction.followup.send(
        f'✅ Checkout recorded for **{local_time}**.',
        ephemeral=True
    )


@bot.tree.command(name='checkouts',description='Manager-only: see today’s setter checkouts')
async def checkouts(interaction:discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message('Use this command inside the server.',ephemeral=True)
    if not is_manager(interaction.user):
        return await interaction.response.send_message(
            '❌ Only users with the **Manager** role can use this.',
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    if not is_workday(now().date()):
        e=discord.Embed(
            title='🌙 CHOSEN GENESIS — TODAY’S CHECKOUTS',
            description='☀️ **Sunday is an off day. No checkout accountability today.**',
            timestamp=datetime.now(timezone.utc)
        )
        return await interaction.followup.send(embed=e,ephemeral=True)

    rows=today_checkouts(interaction.guild.id)
    by_user={r['user_id']:r for r in rows}
    setters=[
        m for m in interaction.guild.members
        if not m.bot and has_named_role(m,'Setter') and not is_greenie(m)
    ]

    completed=[]
    pending=[]
    missed=[]
    after_finalization=now().hour>=22

    for member in setters:
        row=by_user.get(member.id)
        if row:
            completed.append(f'✅ **{member.display_name}** — {row["local_time"]}')
        elif after_finalization:
            missed.append(f'❌ **{member.display_name}**')
            upsert_checkout_record(interaction.guild,member,dkey(),'missed',None)
        else:
            pending.append(f'⏳ **{member.display_name}**')

    e=discord.Embed(
        title='🌙 CHOSEN GENESIS — TODAY’S SETTER CHECKOUTS',
        description='Regular Setter: **7:50 PM** • 🔓 Earned Freedom (4+ deals last month): **4:00 PM**.',
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(
        name='✅ CHECKED OUT',
        value='\n'.join(completed) if completed else 'None yet.',
        inline=False
    )
    if pending:
        e.add_field(
            name='⏳ NOT CHECKED OUT YET',
            value='\n'.join(pending),
            inline=False
        )
    if missed:
        e.add_field(
            name='❌ MISSED CHECKOUT',
            value='\n'.join(missed),
            inline=False
        )
    e.set_footer(text='Private manager view • Chosen Genesis')
    await interaction.followup.send(embed=e,ephemeral=True)


@bot.tree.command(name='appointment',description='Log a new appointment')
@app_commands.describe(
    setter='Who set it',
    bill_collected='Did you collect the electric bill?',
    within_48_hours='Is it within 48 hours?',
    same_day='Is it same day?',
    photo='Optional photo (for example, a homeowner selfie)',
    message='Optional custom message to add to the announcement'
)
async def appointment(
    interaction:discord.Interaction,
    setter:discord.Member,
    bill_collected:bool,
    within_48_hours:bool,
    same_day:bool,
    photo:discord.Attachment|None=None,
    message:str|None=None
):
    if not interaction.guild: return
    n=now(); g=interaction.guild.id

    if photo is not None and not is_image_attachment(photo):
        return await interaction.response.send_message(
            '❌ The optional appointment photo needs to be an image.',
            ephemeral=True
        )

    photo_url=photo.url if photo is not None else None
    photo_filename=photo.filename if photo is not None else None

    c=con()
    c.execute(
        'INSERT INTO appointment_events(guild_id,setter_id,bill_collected,within_48,same_day,local_date,week_key,created_at,photo_url,photo_filename) '
        'VALUES(?,?,?,?,?,?,?,?,?,?)',
        (g,setter.id,int(bill_collected),int(within_48_hours),int(same_day),dkey(n.date()),wkey(n.date()),datetime.now(timezone.utc).isoformat(),photo_url,photo_filename)
    )
    c.commit(); c.close()

    add(g,setter.id,'appointments',1)
    if bill_collected: add(g,setter.id,'bills',1)
    if within_48_hours: add(g,setter.id,'within_48',1)
    if same_day: add(g,setter.id,'same_day',1)

    # Challenge Mode: one appointment can count toward multiple active challenges.
    await update_challenges_for_event(interaction.guild,setter.id,'appointments',1)
    if bill_collected:
        await update_challenges_for_event(interaction.guild,setter.id,'bills',1)
    if same_day:
        await update_challenges_for_event(interaction.guild,setter.id,'same_day',1)
    if within_48_hours:
        await update_challenges_for_event(interaction.guild,setter.id,'within_48',1)
    if photo is not None:
        # A photo attached to the appointment counts +1 only for active
        # Homeowner Selfie challenges the setter is participating in.
        await update_challenges_for_event(interaction.guild,setter.id,'homeowner_selfie',1)

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
    if photo is not None:
        e.add_field(name='📸 Photo',value='✅ Attached',inline=False)
        e.set_image(url=photo.url)

    await interaction.response.send_message('Appointment logged ✅',ephemeral=True)
    await main(interaction.guild,embed=e)

    await check_daily_personal_best(
        interaction.guild,setter.id,'daily_appointments',
        appointments_today_for_user(g,setter.id),'appointments','📈'
    )

    if first_setter(g)==setter.id:
        first_blood_new=award_badge_count(g,setter.id,'🩸 First Blood',dkey())
        if first_blood_new:
            await announce_badge_milestone(interaction.guild,setter.id,'🩸 First Blood')
            await main(
                interaction.guild,
                content=f'🩸 **FIRST BLOOD!** {setter.mention} set the first appointment of the day!'
            )
        await set_holders(interaction.guild,'🩸 First Blood',[setter.id])

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


async def apply_daily_sale_badges(guild,member,count,ghost_hunter=False):
    g=guild.id; today=dkey()
    for threshold,badge,label in [(1,'💥 Sale','💥 **SALE BADGE!**'),(2,'🥈 2 Spot','🥈 **2 SPOT!**'),(3,'🎩 Hattrick','🎩 **HATTRICK!**')]:
        if count>=threshold:
            await add_role(guild,member,badge)
        if count==threshold and award_badge_count(g,member.id,badge,today):
            await announce_badge_milestone(guild,member.id,badge)
            await main(guild,content=f'{label} {member.mention} has **{count} sale{"s" if count!=1 else ""} today!**')
    if ghost_hunter:
        await add_role(guild,member,'👻 Ghost Hunter')
        if award_badge_count(g,member.id,'👻 Ghost Hunter',today):
            await announce_badge_milestone(guild,member.id,'👻 Ghost Hunter')
            await main(guild,content=f'👻 **GHOST HUNTER!** {member.mention} was part of a deal closed after 7 PM!')


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

    await update_challenges_for_event(interaction.guild,setter.id,'setter_sales',1)
    if not outside_team:
        await update_challenges_for_event(interaction.guild,closer.id,'closer_sales',1)

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

    # Sale badges belong to BOTH people on the deal.
    setter_count=setter_sales_today(g,setter.id)
    await apply_daily_sale_badges(interaction.guild,setter,setter_count,ghost_hunter=(n.hour>=19))

    if not outside_team:
        closer_count=closer_sales_today(g,closer.id)
        await apply_daily_sale_badges(interaction.guild,closer,closer_count,ghost_hunter=(n.hour>=19))

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


@bot.tree.command(name='stats',description='Privately view another member’s Chosen Genesis stats')
@app_commands.describe(member='Whose stats do you want to view?')
async def stats(interaction:discord.Interaction,member:discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message(
            'Use this command inside the server.',
            ephemeral=True
        )

    # Keep lookups private so the server chat does not get flooded with stat cards.
    await interaction.response.defer(ephemeral=True)

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
    saved=c.execute(
        'SELECT * FROM stats WHERE guild_id=? AND user_id=?',
        (interaction.guild.id,member.id)
    ).fetchone()

    records=c.execute(
        'SELECT record_name,best_value FROM personal_records WHERE guild_id=? AND user_id=?',
        (interaction.guild.id,member.id)
    ).fetchall()
    c.close()

    all_appts=int(saved['appointments']) if saved else 0
    all_setter=int(saved['sales']) if saved else 0
    all_closer=int(saved['closer_sales']) if saved else 0

    counts=badge_counts(interaction.guild.id,member.id)

    badge_lines=[]
    for badge in DAILY+STREAK+WEEKLY:
        count=counts.get(badge,0)
        if count:
            badge_lines.append(f'**{badge} ×{count}**')
    badges_text='\n'.join(badge_lines) if badge_lines else 'No badges earned yet.'

    record_map={r['record_name']:int(r['best_value'] or 0) for r in records}
    best_day=record_map.get('daily_appointments',0)
    best_setter_sales=record_map.get('daily_setter_sales',0)
    best_closer_sales=record_map.get('daily_closer_sales',0)

    record_lines=[]
    if best_day:
        record_lines.append(f'📅 Best Appointment Day: **{best_day}**')
    if best_setter_sales:
        record_lines.append(f'💰 Best Setter Sales Day: **{best_setter_sales}**')
    if best_closer_sales:
        record_lines.append(f'🤝 Best Closer Sales Day: **{best_closer_sales}**')
    records_text='\n'.join(record_lines) if record_lines else 'No personal records yet.'

    e=discord.Embed(
        title=f'📊 {member.display_name.upper()} — STATS',
        timestamp=datetime.now(timezone.utc)
    )
    e.add_field(
        name='📅 APPOINTMENTS',
        value=(
            f'Today: **{today_appts}**\n'
            f'This Week: **{week_appts}**\n'
            f'This Month: **{month_appts}**\n'
            f'This Year: **{year_appts}**'
        ),
        inline=False
    )
    e.add_field(
        name='💰 SETTER SALES',
        value=(
            f'This Week: **{week_setter}**\n'
            f'This Month: **{month_setter}**\n'
            f'This Year: **{year_setter}**'
        ),
        inline=True
    )
    e.add_field(
        name='🤝 CLOSER SALES',
        value=(
            f'This Week: **{week_closer}**\n'
            f'This Month: **{month_closer}**\n'
            f'This Year: **{year_closer}**'
        ),
        inline=True
    )
    e.add_field(
        name='🏅 BADGES',
        value=badges_text,
        inline=False
    )
    e.add_field(
        name='🏆 PERSONAL RECORDS',
        value=records_text,
        inline=False
    )
    e.add_field(
        name='📊 ALL-TIME',
        value=(
            f'Appointments: **{all_appts}**\n'
            f'Setter Sales: **{all_setter}**\n'
            f'Closer Sales: **{all_closer}**'
        ),
        inline=False
    )
    e.set_footer(text='Private lookup — only you can see this.')
    await interaction.followup.send(embed=e,ephemeral=True)


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
