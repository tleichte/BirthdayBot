import sqlite3
from date_helper import Birthday


conn : sqlite3.Connection = None 


def init():
    global conn
    conn = sqlite3.connect(r"./db/birthday.db")
    
    _execute_command("""
        CREATE TABLE IF NOT EXISTS "birthdays" (
            userid INTEGER UNIQUE,
            month INTEGER,
            day INTEGER,
            year INTEGER,
            PRIMARY KEY("userid")
        )
    """)

    _execute_command("""
        CREATE TABLE IF NOT EXISTS "guild_data" (
            guildid INTEGER,
            notify_time_hr INTEGER,
            notify_time_min INTEGER,
            notify_channel INTEGER,
            prefix TEXT,
            PRIMARY KEY(guildid)
        )
    """)

    _execute_command("""
        CREATE TABLE IF NOT EXISTS "guilds" (
            userid INTEGER,
            guildid INTEGER,
            PRIMARY KEY(userid,guildid)
        )
    """)

# Execute command without data back. Commits immediately after executing
def _execute_command(command: str, params: tuple = None):
    cursor = conn.cursor()

    try:
        if params is None:
            cursor.execute(command)
        else:
            cursor.execute(command, params)
        
        conn.commit()  
    except Exception as e:
        print("Failed to execute db command!")
        print("Command: \"{}\"".format(command))
        print("Parameters: \"{}\"".format(params))
        print("{}\n\n".format(e))
    
    cursor.close()

# Execute command to get data. Does not commit anything.
def _get_data(command: str, params: tuple = None):
    cursor = conn.cursor()

    rows = []
    try:
        if params is None:
            cursor.execute(command)
        else:
            cursor.execute(command, params)
        rows = cursor.fetchall()
    except Exception as e:
        print("Failed to get db data!")
        print("Command: \"{}\"".format(command))
        print("Params: \"{}\"".format(params))
        print("{}\n\n".format(e))

    
    cursor.close()
    return rows


def _get_single_row(command: str, params: tuple = None):
    data = _get_data(command, params)
    if data is None or len(data) == 0:
        return None
    return data[0]

def _get_single_value(command: str, params: tuple = None):
    data = _get_single_row(command, params)
    if data is None:
        return None
    return data[0]

def add_guild(guildid: int, replace:bool = False):
    if replace:
        _execute_command("""
            delete from guild_data where guildid=?
        """, (guildid,))
    
    _execute_command("""
        insert or ignore into guild_data  
            (guildid, notify_time_hr, notify_time_min)
        values (?,?,?)
    """, (guildid, 12, 0))

def get_guild_prefix(guildid: int):
    return _get_single_value("""
        select
            prefix
        from
            guild_data
        where
            guildid = ?
    """, (guildid,))

def set_guild_prefix(guildid: int, prefix: str):
    _execute_command("""
        update or ignore
            guild_data
        set
            prefix = ?
        where
            guildid = ?
    """, (prefix, guildid))

def set_guild_announce_time(guildid: int, time_hr: int, time_min: int):
    _execute_command("""
        update
            guild_data
        set
            notify_time_hr=?,
            notify_time_min=?,
        where
            guildid=?
    """, (time_hr, time_min, guildid))

def get_guild_data(guildid: int):
    data = _get_single_row("""
        select
            notify_time_hr,
            notify_time_min,
            notify_channel
        from
            guild_data
        where
            guildid = ?
    """, (guildid,))
    channel = None
    if data[2] is not None:
        channel = int(data[2])
    return {
        "hr": int(data[0]),
        "min": int(data[1]),
        "channel": channel
    }

def print_initial_data():
    numData = _get_single_value("select count() from birthdays")
    print("Found {} birthdays.".format(numData)) 
    

def user_has_birthday(userid: int):
    count = _get_single_value("select count() from birthdays where userid=?", (userid,))
    return count > 0

def save_user_guild(userid: int, guildid: int):
    if user_has_birthday(userid):
        _execute_command("insert or ignore into guilds (userid, guildid) values (?,?)", (userid, guildid))

def clear_user_guilds():
    _execute_command("delete from guilds")

def remove_user_guild(userid: int, guildid: int):
    _execute_command("delete from guilds where userid=? and guildid=?", (userid, guildid))

def remove_guild(guildid: int):
    _execute_command("delete from guilds where guildid=?", (guildid,))
    _execute_command("delete from guild_data where guildid=?", (guildid,))

def save_birthday(userid: int, birthday: Birthday):
    _execute_command("insert or replace into birthdays values(?,?,?,?)", (userid, birthday.month, birthday.day, birthday.year))

def get_birthday(userid: int):
    data = _get_single_row("""
        select
            month,
            day,
            year
        from
            birthdays
        where
            userid = ?
    """, (userid,))
    if data is None:
        return None
    return Birthday(data[0], data[1], data[2])

def remove_birthday(userid: int):
    _execute_command("delete from guilds where userid=?", (userid,))
    _execute_command("delete from birthdays where userid=?", (userid,))

def get_all_birthdays(guildid: int):
    data = _get_data("""
        select 
            userid,
            month,
            day,
            year
        from
            birthdays
        where 
            userid in (
                select userid from guilds where guildid = ?
            )
        order by 
            month asc, 
            day asc
    """, (guildid,))

    birthdays = []

    for row in data:
        userid = row[0]
        month = row[1]
        day = row[2]
        year = row[3]
        birthdays.append((userid, Birthday(month, day, year)))

    return birthdays


def get_todays_birthdays(guildid: int, month: int, day: int):
    data = _get_data("""
        select 
            userid,
            month,
            day,
            year
        from
            birthdays
        where
            userid in (
                select userid from guilds where guildid = ?
            )
            and month = ?
            and day = ?
    """, (guildid, month, day))

    birthdays = []
    for row in data:
        birthdays.append((row[0], Birthday(row[1], row[2], row[3])))
    return birthdays

def set_time(guildid: int, hour: int, minute: int):
    _execute_command("""
        update 
            guild_data
        set
            notify_time_hr = ?,
            notify_time_min = ?
        where
            guildid = ?
    """, (hour, minute, guildid))

def set_channel(guildid: int, channelid: int):
    _execute_command("""
        update 
            guild_data
        set
            notify_channel = ?
        where
            guildid = ?
    """, (channelid,guildid))

def remove_channel(guildid: int):
    _execute_command("""
        update 
            guild_data
        set
            notify_channel = null
        where
            guildid = ?
    """, (guildid,))

def has_notify(guildid: int):
    value = _get_single_value("""
        select
            notify_channel
        from 
            guild_data
        where
            guildid = ?
    """, (guildid,))

    return value is not None