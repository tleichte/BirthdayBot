import db
import date_helper
from date_helper import Birthday
import discord
import json
import asyncio
import re
import discord
from discord import User, Member, Guild, Message, TextChannel
from discord.ext import tasks
from discord.ext.commands import Bot, Context, Command
import datetime
import traceback

# OPEN INITIAL FILES
try:
    with open("config.json", 'r') as config_json:
        config = json.load(config_json)
except:
    print("Config not found!")
    exit(-1)

def get_context_prefix(ctx: Context):
    if ctx.guild is None:
        return config["default_prefix"]
    return get_guild_prefix(ctx.guild.id)

def get_prefix(bot: Bot, message: Message):
    if message.guild is None:
        return config["default_prefix"]
    return get_guild_prefix(message.guild.id)

def get_guild_prefix(guildid:int):
    prefix = db.get_guild_prefix(guildid)
    if prefix is None:
        return config["default_prefix"]
    return prefix


intents = discord.Intents.all()
bot = Bot(command_prefix=get_prefix, intents=intents)
bot.remove_command('help')


# COMMANDS

@bot.group()
async def birthday(ctx: Context):
    if ctx.invoked_subcommand is None:
        await respond_generic_error(ctx)

@birthday.command()
async def help(ctx: Context):
    
    with open("help.json", 'r') as help_json:
        help_obj = json.load(help_json)
    
    help_embed: discord.Embed = discord.Embed()
    
    color_obj = help_obj["color"]
    help_embed.colour = discord.Color.from_rgb(color_obj["r"], color_obj["g"], color_obj["b"])
    
    author_obj = help_obj["author"]
    help_embed.set_author(name=author_obj["name"], icon_url=author_obj["icon_url"], url=author_obj["url"])

    help_embed.title = help_obj["title"]
    help_embed.description = help_obj["description"]


    prefix = get_context_prefix(ctx)

    entries = help_obj['entries']
    for entry in entries:
        help_embed.add_field(name=prefix+entry['command'], value=entry['description'], inline=False)

    help_embed.set_footer(text=help_obj["footer"])

    await ctx.send(embed=help_embed)

@birthday.command()
async def set_time(ctx:Context, time_str:str):
    if not await check_admin(ctx):
        return

    
    if not re.match(r"^([01]?\d|2[0-3]):[0-6]\d$", time_str):
        await respond(ctx, "Time must match 24hr 00:00 format.")
        return

    objects = time_str.split(":")
    hour = int(objects[0])
    minute = int(objects[1])

    db.set_time(ctx.guild.id, hour, minute)

    #send to database
    await respond(ctx, f"Successfully set the announcement time to {hour:02}:{minute:02}")

@birthday.command()
async def set_channel(ctx:Context):
    if not await check_admin(ctx):
        return
    
    db.set_channel(ctx.guild.id, ctx.channel.id)

    await respond(ctx, ":thumbsup: Got it! I'll make sure to let everyone know here.")

@birthday.command()
async def disable_notify(ctx:Context):
    if not await check_admin(ctx):
        return

    db.remove_channel(ctx.guild.id)

    await respond(ctx, f":shushing_face: Got it, I wont bother everyone. If you change your mind, just set the announcement channel again with *{get_context_prefix(ctx)}birthday set_channel*")

@birthday.command()
async def get(ctx: Context, *, member: Member):

    if (member.id == bot.user.id):
        await respond(ctx, f"I don't really have a *birthday*, but my most recent update was on {config['last_update']} :robot:")
        return

    if (member.bot):
        await respond(ctx, f":robot: I'd look inside **{member.display_name}'s** code to tell you, but I don't think they'd be a fan of that. :grimacing:")
        return

    birthday_obj : Birthday = db.get_birthday(member.id)
    if birthday_obj is None:
        await respond(ctx, f":shrug: Sorry, I wish I knew! **{member.display_name}** hasn't told me their birthday yet.")
        return
    
    out_str = f"**{member.display_name}**'s birthday is **{birthday_obj}**."

    if ctx.guild is not None and db.has_notify(ctx.guild.id):
        if birthday_obj.hasAge:
            curr_date = datetime.utcnow().date()
            if birthday_obj.month == curr_date.month and birthday_obj.day == curr_date.day:
                out_str += f" They are turning {date_helper.get_age(birthday_obj):,} today! :tada:"
            else:
                out_str += f" I'll be sure let you know when they turn {date_helper.get_age(birthday_obj)+1:,}! :tada:"
        else:
            out_str += " I'll be sure to let you know then! :tada:"
    
    await respond(ctx, out_str)

@birthday.command()
async def set(ctx: Context, *, birthday_str: str):

    if ctx.author.bot:
        await respond(ctx, ":face_with_raised_eyebrow::mag_right: 010110010110111101110101001000000110001101100001011011100010011101110100001000000110011001101111011011110110110000100000011011010110010100101110", False)
        return

    # Parse birthday, then set
    birthday = date_helper.parse_birthday(birthday_str)

    if birthday is None:
        await respond(ctx, f":grey_question: Sorry, I don't understand that date. Make sure it's a valid birthdate and it follows a valid format. (Type *{get_context_prefix(ctx)}birthday help* to see valid formats)")
        return
    
    db.save_birthday(ctx.author.id, birthday)

    save_user_guilds(ctx.author.id)

    out_str = f":memo: **{birthday}**, got it!"
    if ctx.guild is not None and db.has_notify(ctx.guild.id):
        out_str += " I'll be sure to let everyone know when it's your birthday."
    out_str += " :thumbsup:"

    await respond(ctx, out_str)

@birthday.command()
async def all(ctx: Context):
    if not await check_server(ctx):
        return

    birthdays = db.get_all_birthdays(ctx.guild.id)

    out_str = ""
    for birthday_tuple in birthdays:
        member: Member = ctx.guild.get_member(birthday_tuple[0])
        birthday: Birthday = birthday_tuple[1]
        out_str += f"**{member.display_name}**: {birthday}"
        if (birthday.hasAge):
            out_str += f" ({date_helper.get_age(birthday)} yrs old)"
        out_str += "\n"
        
    await respond(ctx, f":mag_right::notepad_spiral: Here are all the birthdays I know:\n{out_str}")


@birthday.command()
async def next(ctx: Context):
    if not await check_server(ctx):
        return

    birthdays = db.get_all_birthdays(ctx.guild.id)

    # relies on this being in order

    curr_datetime = datetime.datetime.utcnow()
    curr_month = curr_datetime.date().month
    curr_day = curr_datetime.date().day

    next_birthday_tuple = None

    for birthday_tuple in birthdays:
        birthday : Birthday = birthday_tuple[1]
        if (birthday.month == curr_month and birthday.day > curr_day) or birthday.month > curr_month:
            next_birthday_tuple = birthday_tuple
            break
    
    if next_birthday_tuple is None:
        if len(birthdays) > 0:
            next_birthday_tuple = birthdays[0]
        else:
            # No birthdays
            await respond(ctx, f"I don't know anyone's birthday! Type *{get_guild_prefix(ctx.guild.id)}birthday help* to see how to add yours!")
            return

    member: Member = ctx.guild.get_member(next_birthday_tuple[0])
    next_birthday : Birthday = next_birthday_tuple[1]

    out_str = f":calendar_spiral: Mark your calendars, The next birthday is **{member.display_name}** ({next_birthday})!"
    
    if next_birthday.hasAge:
        out_str += f" They will be turning {date_helper.get_age(next_birthday)+1}."

    await respond(ctx, out_str)


@birthday.command()
async def remove(ctx: Context):
    if db.get_birthday(ctx.author.id) is None:
        await respond(ctx, "I didn't know your birthday anyway, so no harm no foul, right? :shrug:", False)
        return

    db.remove_birthday(ctx.author.id)
    await respond(ctx, ":cry: Sorry to see you go! I removed your birthday from my list.")


@birthday.command()
async def bedtime(ctx: Context):
    if await bot.is_owner(ctx.author):
        print("Owner verified, shutting down")
        check_guilds.cancel()
        await ctx.send(":yawning_face: :sleeping:")
        await bot.close()
        print("Shutdown Complete.")
    else:
        print("User doesn't have kill permission.")
        await respond(ctx, ":triumph: You're not the boss of me.")

@birthday.command()
async def set_prefix(ctx:Context, prefix:str):
    if not await check_admin(ctx):
        return

    if len(prefix) > 3 or len(prefix) < 1:
        await respond(ctx, "Prefix must be between 1-3 characters!", False)
    else:
        db.set_guild_prefix(ctx.guild.id, prefix)
        await respond(ctx, f":thumbsup: Successfully set prefix to \"{prefix}\". Type *{prefix}birthday help* to see all the commands with this prefix.")

@birthday.command()
async def ping(ctx):
    await ctx.send(f":ping_pong: Pong! ({round(bot.latency*1000)}ms)")


# EVENTS
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} - {bot.user.id}")

    db.init()

    db.clear_user_guilds()

    guild: Guild
    member: Member
    for guild in bot.guilds:
        
        print(f"Adding guild: {guild.id} (Num members: {len(guild.members)})")

        db.add_guild(guild.id)
        
        for member in guild.members:
            db.save_user_guild(member.id, guild.id)


    db.print_initial_data()

@bot.event
async def on_command(ctx:Context):
    print(f"Command \"{ctx.command}\" received from {ctx.author} - {ctx.author.id}")

@bot.event
async def on_command_error(ctx:Context, error:discord.ext.commands.CommandError):

    cmd: Command = ctx.command

    if cmd is None:
        print("Unrecognized command detected; ignoring")
        return

    print(f"Command error! Message: \"{ctx.message.content}\", Error type: {type(error)}")
    if isinstance(error, (discord.ext.commands.BadArgument, discord.ext.commands.CommandNotFound, discord.ext.commands.MissingRequiredArgument)):
        await respond_generic_error(ctx)
    else:
        traceback.print_exception(type(error),error,error.__traceback__)
        await respond(ctx, f"Sorry, something went wrong... I feel like I have butterflies... no, bugs, in my stomach. :sick:", False)

@bot.event
async def on_guild_join(guild: Guild):

    print(f"Added to guild {guild.id}")

    member: Member
    db.add_guild(guild.id)
    for member in guild.members:
        db.save_user_guild(member.id, guild.id)
    
    if guild.system_channel is not None:
        await guild.system_channel.send(f":wave: Hey, I'm Birthday Bot! Type *{get_guild_prefix(guild.id)}birthday help* to learn all of my commands.")

@bot.event
async def on_guild_remove(guild: Guild):
    db.remove_guild(guild.id)

@bot.event
async def on_member_remove(member: Member):
    db.remove_user_guild(member.id, member.guild.id)

@bot.event
async def on_member_join(member: Member):
    db.save_user_guild(member.id, member.guild.id)


# HELPERS

def save_user_guilds(userid: int):
    guild: Guild
    for guild in bot.guilds:
        if guild.get_member(userid) is not None:
            db.save_user_guild(userid, guild.id)

async def respond(ctx: Context, message: str, check_thanks=True):
    await ctx.send(f"{ctx.author.mention}\n{message}")

    if check_thanks:
        def is_thanks(message: Message):
            return message.author is ctx.message.author and "thank" in message.content.lower()

        try:
            await bot.wait_for('message', check=is_thanks, timeout=7.0)
        except asyncio.TimeoutError:
            print("No thanks received :/")
            return

        await respond(ctx, ":wink: You're welcome!", False)

def is_member_admin(member:Member):
    return member.guild_permissions.administrator

async def check_admin(ctx: Context):
    if not await check_server(ctx):
        return False
    if not is_member_admin(ctx.author):
        await respond(ctx, ":triumph: You're not my admin, I don't have to listen to you!", False)
        return False
    return True

async def check_server(ctx: Context):
    if ctx.guild is None:
        await ctx.send(":cowboy: Hold it right there, partner! You need to be in a server for this command to work!")
        return False
    return True

def print_command(command: str, user:User):
    print(f"{command}")

async def respond_generic_error(ctx:Context):
    await respond(ctx, f":grey_question: Sorry, I didn't recognize that. Type *{get_context_prefix(ctx)}birthday help* to see what I do know.", False)

# LOOP

@tasks.loop(minutes=1)
async def check_guilds():
    curr_datetime = datetime.datetime.utcnow()
    curr_hr = curr_datetime.time().hour
    curr_min = curr_datetime.time().minute
    curr_month = curr_datetime.date().month
    curr_day = curr_datetime.date().day

    print(f"Check Guilds: Checking time: {curr_datetime.time().hour:02}:{curr_datetime.time().minute:02}")
    guild: Guild
    for guild in bot.guilds:
        data = db.get_guild_data(guild.id)
        if data["channel"] is not None and data["hr"] is curr_hr and data["min"] is curr_min:
            print(f"Checking guild {guild.id}")
            await check_for_guild_birthdays(guild, curr_month, curr_day, data["channel"])

@check_guilds.before_loop
async def before_check_guilds():
    print("Before Check Guilds: Waiting until bot ready")
    await bot.wait_until_ready()
    print("Before Check Guilds: Aligning seconds to 0")
    # Align seconds with 0
    while not datetime.datetime.utcnow().time().second is 0:
        await asyncio.sleep(1)


async def check_for_guild_birthdays(guild:Guild, month: int, day: int, channelid: int):
    birthdays = db.get_todays_birthdays(guild.id, month, day)
    if len(birthdays) > 0:
        channel: TextChannel = guild.get_channel(channelid)

        out_str = "@everyone\n:tada::confetti_ball::tada::confetti_ball::tada::confetti_ball::tada::confetti_ball::tada::confetti_ball::tada::confetti_ball:\n"
        for birthday_tuple in birthdays:
            member:Member = guild.get_member(birthday_tuple[0])
            birthday:Birthday = birthday_tuple[1]
            out_str += f":cupcake:It's {member.mention}'s birthday!"
            if birthday.hasAge:
                out_str += f" They just turned {date_helper.get_age(birthday)}!"
            out_str += ":cupcake:\n"
        out_str += ":tada::confetti_ball::tada::confetti_ball::tada::confetti_ball::tada::confetti_ball::tada::confetti_ball::tada::confetti_ball:"

        await channel.send(out_str)


        
check_guilds.start()

# Run
bot.run(config['token'])