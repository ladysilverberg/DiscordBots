import os
import discord
import hashlib
from discord.ext import commands
from db import DB
from web_parser import HTML_Parser
from policy import Policy
from util import load_config

# User Indices
ID = 0
VALIDATED = 1
NAME = 2
TOKEN = 3

# Class Instances
sha3 = hashlib.sha3_256()
intents = discord.Intents.all()
bot = commands.Bot("!", help_command=None, intents=intents)
config = load_config()
db = DB("users.db")
web = HTML_Parser(config)
policy = Policy(config)


# ----------------------------------------------------------------------
# Command Checks
# ----------------------------------------------------------------------
def is_dm_channel(ctx):
    return isinstance(ctx.channel, discord.channel.DMChannel)

async def is_user_verified(ctx):
    user = db.create_or_get_user(ctx.message.author.id)
    if user[VALIDATED] != 1:
        await ctx.send(config["error_messages"]["user_not_verified"])
        return False
    else:
        return True

async def log_message(msg):
    channel = bot.get_channel(config["logging_channel_id"])
    await channel.send(msg)

# ----------------------------------------------------------------------
# Subroutines 
# ----------------------------------------------------------------------
async def send_manual_review_post(ctx, fflogs_url, role, name):
    user = ctx.author
    title = "Logs for Manual Review"
    description = "These logs have been flagged for manual review. Please look through them an react accordingly."
    username = user.display_name + " (" + user.name + "#" + user.discriminator + ")"

    embed = discord.Embed(title=title, url=fflogs_url, description=description, color=0xf404ec)
    embed.set_author(name=username, icon_url=user.avatar_url)
    embed.set_thumbnail(url="https://assets.rpglogs.com/img/ff/header-logo.png?v=2")
    embed.add_field(name="FFLogs Link", value=fflogs_url, inline=False)
    embed.add_field(name="User ID", value=str(user.id), inline=True)
    embed.add_field(name="Role Requested", value=role, inline=True)
    embed.add_field(name="FFXIV Name", value=name, inline=False)

    channel = bot.get_channel(config["manual_review_channel_id"])
    message = await channel.send(embed=embed)
    await message.add_reaction(config["accept_emoji"])
    await message.add_reaction(config["reject_emoji"])

async def send_info_message(ctx):
    compiled_message = '\n'.join(config["info_message"])
    await ctx.send(compiled_message)

async def add_requested_role(user, role_name):
    guild = await bot.fetch_guild(config["server_id"])
    if role_name in config["roles"]:
        role = guild.get_role(config["roles"][role_name])
        member = await guild.fetch_member(user.id)
        await member.add_roles(role)
    else:
        print("No Role ID for", role_name, "found!")

async def change_user_nickname(user, nickname):
    guild = await bot.fetch_guild(config["server_id"])
    member = await guild.fetch_member(user)
    await member.edit(nick=nickname)

async def user_has_role(user_id, role_id):
    guild = await bot.fetch_guild(config["server_id"])
    member = await guild.fetch_member(user_id)
    for role in member.roles:
        if role.id == role_id:
            return True
    return False

# ----------------------------------------------------------------------
# Bot Events
# ----------------------------------------------------------------------
@bot.event
async def on_reaction_add(reaction, user):
    if reaction.message.channel.id == config["manual_review_channel_id"]:
        if user.bot:
            return

        if len(reaction.message.embeds) > 0:
            embed = reaction.message.embeds[0]
            user_id = int(embed.fields[1].value)
            user_to_dm = await bot.fetch_user(user_id)
            fflogs_url = embed.fields[0].value
            role_requested = embed.fields[2].value

            if reaction.emoji == config["accept_emoji"]:
                reply = "The logs you provided (" + fflogs_url + ") has been manually reviewed and accepted by " + user.display_name + "!\n"
                reply += "To join our next DRS run, head to https://discord.com/channels/806471097108267028/853202849894629376/ and react accordingly."
                await user_to_dm.send(reply)
                await add_requested_role(user_to_dm, role_requested)
                await log_message(user.display_name + " manually accepted DRS logs (" + fflogs_url + ") for " + user_to_dm.name + "#" + user_to_dm.discriminator)
            elif reaction.emoji == config["reject_emoji"]:
                await user_to_dm.send("The logs you provided (" + fflogs_url + ") has been manually reviewed and rejected.\nPlease contact " + user.display_name + " for more details.")
                await log_message(user.display_name + " manually rejected DRS logs (" + fflogs_url + ") for " + user_to_dm.name + "#" + user_to_dm.discriminator)

            await reaction.message.delete()

@bot.event
async def on_member_join(member):
    await send_info_message(member)
    await member.send("**Note:** If you are not interested in running this content with us you can ignore this message.")

@bot.event
async def on_ready():
    print("Running.")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="all the logs - Rawr!"))

# ----------------------------------------------------------------------
# Bot Commands
# ----------------------------------------------------------------------
@bot.command()
@commands.check(is_dm_channel)
@commands.check(is_user_verified)
async def role(ctx, role, fflogs_url):
    user = db.create_or_get_user(ctx.message.author.id)

    if role == "drs":
        if await user_has_role(user[ID], config["roles"][role]):
            await ctx.send("You already have the DRS role!")
            return
        # Parse HTML of Logs
        await ctx.send("Checking provided logs.\nThis may take some seconds.")
        status_code, data = web.get_log_data(fflogs_url, str(user[NAME]))
        if status_code == config["error_codes"]["failure"]:
            await ctx.send(data)
        elif status_code == config["error_codes"]["success"]:
            # Check Logs According to Policy
            status_code, log_accepted = policy.check_drs_logs(data)
            if status_code == config["error_codes"]["failure"]:
                await ctx.send(log_accepted)
            elif status_code == config["error_codes"]["manual_check"]:
                await ctx.send(log_accepted)
                await send_manual_review_post(ctx, fflogs_url, role, user[NAME])
            elif status_code == config["error_codes"]["success"]:
                discord_user = ctx.message.author
                if log_accepted is True:
                    await ctx.send(config["error_messages"]["log_accepted"])
                    await add_requested_role(discord_user, role)
                    await log_message("Accepted DRS logs (" + fflogs_url + ") for " + discord_user.name + "#" + discord_user.discriminator)
                else:
                    await ctx.send(config["error_messages"]["log_rejected"])
                    await log_message("Rejected DRS logs (" + fflogs_url + ") for " + discord_user.name + "#" + discord_user.discriminator)

@bot.command()
@commands.check(is_dm_channel)
async def verify(ctx, *args):
    user = db.create_or_get_user(ctx.message.author.id)
    if user[VALIDATED] == 1:
        reply = config["error_messages"]["user_already_validated"] + str(user[NAME])
        await ctx.send(reply)
        return

    # Verify Challenge-Response Token
    if len(args) == 1:
        status_code, data = web.get_lodestone_data(args[0])
        if status_code == config["error_codes"]["failure"]:
            await ctx.send(data)
        elif status_code == config["error_codes"]["success"]:
            lodestone_name = data[0]
            token = data[1]
            lodestone_world = data[2]
            if user[TOKEN] in token:
                db.set_user_validation(user[ID], 1)
                db.set_user_name(user[ID], lodestone_name)
                db.set_user_token(user[ID], "")
                reply = config["error_messages"]["validation_success"] + lodestone_name + "\n"
                reply += "We recommend you to remove the token from your lodestone character profile now."
                await change_user_nickname(user[ID], lodestone_name + " [" + lodestone_world + "]")
                await ctx.send(reply)
            else:
                await ctx.send(config["error_messages"]["invalid_token"])

    # Generate Challenge-Response Token
    else:
        id_string = str(user[ID]).encode("utf-8")
        sha3.update(id_string)
        id_hash = sha3.hexdigest()
        random = os.urandom(16).hex()
        token = id_hash + "-" + random
        db.set_user_token(user[ID], token)
        await ctx.send(config["error_messages"]["validation_token"] + str(token))
        await ctx.send("Put this on your lodestone character profile and use the command !verify [lodestone URL].")

@bot.command()
@commands.check(is_dm_channel)
async def info(ctx):
    await send_info_message(ctx)

@bot.command()
@commands.check(is_dm_channel)
async def help(ctx):
    reply = "You can use the following commands (all commands must be used over DM):\n"
    reply += "!verify: generates a token for you to put on your lodestone profile.\n"
    reply += "!verify [lodestone URL]: verifies your token in order to confirm your FFXIV identity.\n"
    reply += "!role drs [fflogs URL]: checks your provided DRS logs.\n"
    await ctx.send(reply)

# ----------------------------------------------------------------------
# Run Bot
# ----------------------------------------------------------------------
bot.run(config["token"])

