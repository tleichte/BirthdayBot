import enum
from tokenize import maybe
import db
import date_helper
from date_helper import Birthday, BirthdayParseException, BirthdayMonth
import discord
import json
import asyncio
import re
import discord
from discord import app_commands, Interaction, User, Member, Guild, Message, TextChannel
from discord.ext import tasks
from discord.ext.commands import Bot
import datetime
import traceback

# OPEN INITIAL FILES
try:
    with open("config.json", 'r') as config_json:
        config = json.load(config_json)
except:
    print("Config not found!")
    exit(-1)

class MyBot(Bot):
    async def setup_hook(self):
        
        self.tree.add_command(BirthdayGroup(name="birthday", description="Birthday Command Group"))

        await self.tree.sync()
        
        check_guilds.start()


intents = discord.Intents.default()
intents.members = True
bot = MyBot(command_prefix="!", intents=intents)
bot.remove_command('help')


# COMMANDS

class BirthdayGroup(app_commands.Group):

    @app_commands.command(description="Shows the help dialog")
    async def help(self, interaction: Interaction):
        
        with open("help.json", 'r') as help_json:
            help_obj = json.load(help_json)
        
        help_embed: discord.Embed = discord.Embed()
        
        color_obj = help_obj["color"]
        help_embed.colour = discord.Color.from_rgb(color_obj["r"], color_obj["g"], color_obj["b"])

        help_embed.title = help_obj["title"]
        help_embed.description = help_obj["description"]

        for command in bot.tree.walk_commands():
            if not isinstance(command, app_commands.Group):
                help_embed.add_field(name="/" + command.qualified_name, value=command.description, inline=False)

        help_embed.set_footer(text=help_obj["footer"])

        await interaction.response.send_message(embed=help_embed)

    @app_commands.command(description="[Admin] Sets the UTC 24hr time for announcing birthdays for this server. Defaults to 12:00 UTC")
    @app_commands.guild_only()
    async def set_time(self, interaction:Interaction, time_str:str):
        if not await check_admin(interaction):
            return

        
        if not re.match(r"^([01]?\d|2[0-3]):[0-6]\d$", time_str):
            await respond(interaction, "Time must match 24hr 00:00 format.", ephemeral=True)
            return

        objects = time_str.split(":")
        hour = int(objects[0])
        minute = int(objects[1])

        db.set_time(interaction.guild.id, hour, minute)

        #send to database
        await respond(interaction, f"Successfully set the announcement time to {hour:02}:{minute:02}", ephemeral=True)

    @app_commands.command(description="[Admin] Uses this channel to announce birthdays. No announcements will be made until this is done.")
    @app_commands.guild_only()
    async def set_channel(self, interaction:Interaction):
        if not await check_admin(interaction):
            return
        
        db.set_channel(interaction.guild.id, interaction.channel.id)

        await respond(interaction, ":thumbsup: Got it! I'll make sure to let everyone know in this channel.", ephemeral=True)

    @app_commands.command(description="[Admin] Disables birthday notifications for this server")
    @app_commands.guild_only()
    async def disable_notify(self, interaction:Interaction):
        if not await check_admin(interaction):
            return

        db.remove_channel(interaction.guild.id)

        await respond(interaction, f":shushing_face: Got it, I wont bother everyone. If you change your mind, just set the announcement channel again with */birthday set_channel*", ephemeral=True)

    @app_commands.command(description="Shows a given member's birthday")
    @app_commands.guild_only()
    async def get(self, interaction:Interaction, member: User):

        if (member.id == bot.user.id):
            await respond(interaction, f"I don't really have a *birthday*, but my most recent update was on {config['last_update']} :robot:", ephemeral=True)
            return

        if (member.bot):
            await respond(interaction, f":robot: I'd look inside **{member.display_name}'s** code to tell you, but I don't think they'd be a fan of that. :grimacing:", ephemeral=True)
            return

        birthday_obj : Birthday = db.get_birthday(member.id)
        if birthday_obj is None:
            await respond(interaction, f":shrug: Sorry, I wish I knew! **{member.display_name}** hasn't told me their birthday yet.", ephemeral=True)
            return
        
        out_str = f"**{member.display_name}**'s birthday is **{birthday_obj}**."

        if interaction.guild is not None and db.has_notify(interaction.guild.id):
            if birthday_obj.hasAge:
                curr_date = datetime.datetime.utcnow().date()
                if birthday_obj.month == curr_date.month and birthday_obj.day == curr_date.day:
                    out_str += f" They are turning {date_helper.get_age(birthday_obj):,} today! :tada:"
                else:
                    out_str += f" I'll be sure let you know when they turn {date_helper.get_age(birthday_obj)+1:,}! :tada:"
            else:
                out_str += " I'll be sure to let you know then! :tada:"
        
        await respond(interaction, out_str, ephemeral=True)

    @app_commands.command(description="Sets your birthday. Year not required, but necessary for age. Remembered across all servers.")
    async def set(self, interaction: Interaction, month: BirthdayMonth, day: app_commands.Range[int, 0, 31], year:int = None):

        if interaction.user.bot:
            await respond(interaction, ":face_with_raised_eyebrow::mag_right: 010110010110111101110101001000000110001101100001011011100010011101110100001000000110011001101111011011110110110000100000011011010110010100101110")
            return

        # Parse birthday, then set
        try:
            birthday = date_helper.get_bday_if_valid(month, day, year)
        except BirthdayParseException as bday_exception:
            await respond(interaction, bday_exception.message, ephemeral=True)
            return
        
        db.save_birthday(interaction.user.id, birthday)

        save_user_guilds(interaction.user.id)

        out_str = f":memo: **{birthday}**, got it!"
        if interaction.guild is not None and db.has_notify(interaction.guild.id):
            out_str += " I'll be sure to let everyone know when it's your birthday."
        out_str += " :thumbsup:"

        await respond(interaction, out_str, ephemeral=True)

    @app_commands.command(description="Shows all birthdays for this server")
    @app_commands.guild_only()
    async def all(self, interaction: Interaction):
        if not await check_server(interaction):
            return

        birthdays = db.get_all_birthdays(interaction.guild.id)

        if (len(birthdays) == 0):
            await respond(interaction, "I don't know any birthdays! Use **/birthday set** to set yours!", ephemeral=True)
            return

        out_str = ""
        for birthday_tuple in birthdays:
            member: Member = interaction.guild.get_member(birthday_tuple[0])
            birthday: Birthday = birthday_tuple[1]
            out_str += f"**{member.display_name}**: {birthday}"
            # Remove year from immediate display
            # if (birthday.hasAge):
            #     out_str += f" ({date_helper.get_age(birthday)} yrs old)"
            out_str += "\n"
            
        await respond(interaction, f":mag_right::notepad_spiral: Here are all the birthdays I know:\n{out_str}", ephemeral=True)


    @app_commands.command(description="Shows the next birthday for this server")
    @app_commands.guild_only()
    async def next(self, interaction: Interaction):
        if not await check_server(interaction):
            return

        birthdays = db.get_all_birthdays(interaction.guild.id)

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
                await respond(interaction, f"I don't know anyone's birthday! Use */birthday help* to see how to add yours!", ephemeral=True)
                return

        member: Member = interaction.guild.get_member(next_birthday_tuple[0])
        next_birthday : Birthday = next_birthday_tuple[1]

        out_str = f":calendar_spiral: Mark your calendars, The next birthday is **{member.display_name}** ({next_birthday})!"
     
        if next_birthday.hasAge:
            out_str += f" They will be turning {date_helper.get_age(next_birthday)+1}."

        await respond(interaction, out_str, ephemeral=True)


    @app_commands.command(description="Removes your birthday from the bot")
    async def remove(self, interaction: Interaction):
        if db.get_birthday(interaction.user.id) is None:
            await respond(interaction, "I didn't know your birthday anyway, so no harm no foul, right? :shrug:", ephemeral=True)
            return

        db.remove_birthday(interaction.user.id)
        await respond(interaction, ":cry: Sorry to see you go! I removed your birthday from my list.", ephemeral=True)

@bot.tree.command(description="[Owner] Shuts down the bot")
@app_commands.dm_only()
async def bedtime(interaction: Interaction):
    if await bot.is_owner(interaction.user):
        print("Owner verified, shutting down")
        check_guilds.cancel()
        await respond(interaction, ":yawning_face: :sleeping:", ephemeral=True)
        await bot.close()
        print("Shutdown Complete.")
    else:
        print("User doesn't have kill permission.")
        await respond(interaction, ":triumph: You're not the boss of me.", ephemeral=True)

@bot.tree.command(description="Shows the bot's ping")
async def ping(interaction: Interaction):
    await respond(interaction, f":ping_pong: Pong! ({round(bot.latency*1000)}ms)", ephemeral=True)


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
async def on_guild_join(guild: Guild):

    print(f"Added to guild {guild.id}")

    member: Member
    db.add_guild(guild.id)
    for member in guild.members:
        db.save_user_guild(member.id, guild.id)
    
    if guild.system_channel is not None:
        await guild.system_channel.send(f":wave: Hey, I'm Birthday Bot! Use */birthday help* to learn all of my commands.")

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

async def respond(interaction: Interaction, message: str, ephemeral:bool = False):
    if interaction.response.is_done():
        await interaction.edit_original_response(content=message)
    else:
        await interaction.response.send_message(message, ephemeral=ephemeral)

def is_member_admin(member:Member):
    return member.guild_permissions.administrator

async def check_admin(interaction: Interaction):
    if not await check_server(interaction):
        return False
    if not is_member_admin(interaction.user):
        await respond(interaction, ":triumph: You're not my admin, I don't have to listen to you!", ephemeral=True)
        return False
    return True

async def check_server(interaction: Interaction):
    if interaction.guild is None:
        await respond(interaction, ":cowboy: Hold it right there, partner! You need to be in a server for this command to work!", ephemeral=True)
        return False
    return True

def print_command(command: str, user:User):
    print(f"{user.display_name} - {command}")

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
    while datetime.datetime.utcnow().time().second != 0:
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

if __name__ == "__main__":
    # Run
    bot.run(config['token'])