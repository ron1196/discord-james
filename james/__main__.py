import discord
from discord.ext import commands
import asyncio
import json
import os
import difflib
import sys
import pickle
import math
import re
from urllib.request import Request, urlopen
from datetime import datetime

CITY = ['jer', 'ash', 'mad']

def load_data():
    # Load configuration
    global config
    with open('config.json', 'r') as fd:
        config = json.load(fd)

    # Load Guild Dict   
    global guild_dict
    try:
        with open(os.path.join('data', 'guild_dict'), 'rb') as fd:
            guild_dict = pickle.load(fd)
    except OSError:
        with open(os.path.join('data', 'guild_dict'), 'wb') as fd:
            guild_dict = {}
            pickle.dump(guild_dict, fd, (- 1))

    # Load Gyms
    global gyms
    gyms = {}
    for city in CITY:
        gyms[city] = {}
        file_path = os.path.join('data/gyms', f'{city}.json')
        if not os.path.isfile(file_path):
            continue
        with open(file_path, 'r') as fd:
            gyms_data = json.load(fd)["Document"]["Folder"]
        for gym_folder in gyms_data:
            if( gym_folder['name'] == "Gyms" or gym_folder['name'] == "Confirmed EX Gyms" ):
                for gym in gym_folder["Placemark"]:
                    gym_name = str(gym["name"]) if ("__cdata" not in gym["name"]) else str(gym["name"]["__cdata"])
                    gym_coord = gym["Point"]["coordinates"].strip().split(',')[:2]
                    gym_coord.reverse()
                    gym_ex_confirmed = True if gym_folder["name"] == "Confirmed EX Gyms" else False

                    gyms[city][gym_name.lower()] = {"Name": gym_name, "Coordinates": gym_coord, "Ex Confirmed": gym_ex_confirmed}

    # Load Pokestops
    global pokestops
    pokestops = {}
    for city in CITY:
        pokestops[city] = {}
        file_path = os.path.join('data/pokestops', f'{city}.json')
        if not os.path.isfile(file_path):
            continue
        with open(file_path, 'r') as fd:
            pokestops_data = json.load(fd)
        for pokestop in pokestops_data:
            pokestop_name = pokestop["In-game name | שם התחנה במשחק"]
            pokestop_coord = [str(pokestop["Latitude | קו רוחב"]), str(pokestop["Longtitue | קו אורך"])]
            pokestops[city][pokestop_name.lower()] = {"Name": pokestop_name, "Coordinates": pokestop_coord}

load_data()
James = commands.Bot(command_prefix=config['default_prefix'], owner_id=config['master'], case_insensitive=True)
James.remove_command('help')

async def save():
    with open(os.path.join('data', 'guild_dict_tmp'), 'wb') as fd:
        pickle.dump(guild_dict, fd, (- 1))
    os.remove(os.path.join('data', 'guild_dict'))
    os.rename(os.path.join('data', 'guild_dict_tmp'), os.path.join('data', 'guild_dict'))

"""
Events
"""

@James.event
async def on_ready():
    async def auto_save(loop=True):
        while (not James.is_closed()):
            try:
                await save()
            except Exception as err:
                pass
            await asyncio.sleep(600)
            continue

    try:
        event_loop.create_task(auto_save())
    except KeyboardInterrupt as e:
        pass
event_loop = asyncio.get_event_loop()

@James.event
async def on_guild_join(guild):
    guild_dict[guild.id] = {
        'region': None
    }

@James.event
async def on_guild_remove(guild):
    try:
        if guild.id in guild_dict:
            try:
                del guild_dict[guild.id]
            except KeyError:
                pass
    except KeyError:
        pass

@James.event
async def on_guild_channel_create(channel):
    if channel.guild != None:
        name = channel.name
        if name.startswith("ex") or (name[0].isdigit() and int(name[0]) >= 1 and int(name[0]) <= 5) or name.startswith("level"):
            await asyncio.sleep(7)

            first_message = (await channel.history(reverse=True).flatten())[0]
            details_start_index = first_message.content.index("Details: ") + len("Details: ")
            details_end_index = first_message.content.index(".", details_start_index)
            raid_location_details = first_message.content[details_start_index:details_end_index]

            gym = await find_gym(raid_location_details, first_message.mentions[0], channel)
            if gym:
                maps_link = 'https://www.google.com/maps/search/?api=1&query={}'.format('+'.join(gym['Coordinates']))
                await channel.send(f'{maps_link}')
                if gym["Ex Confirmed"]:
                    role = discord.utils.get(channel.guild.roles, name="ex")
                    if role:
                        role = role.mention
                    else:
                        role = "ex"
                    await channel.send('{} Raid Gym in {}'.format(role, raid_location_details))


"""
Helper functions
"""

async def find_gym(entered_gym, author, channel):
    guild = channel.guild
    if( guild_dict[guild.id].get("region", None) is None ):
        await channel.send("Use **!region [region]**")
        return

    entered_gym = entered_gym.lower()
    gym = gyms[guild_dict[guild.id]["region"]].get(entered_gym, None)
    if not gym:
        gym_autocorrect = autocorrect(entered_gym, gyms[guild_dict[guild.id]["region"]].keys(), author, channel)
        if gym_autocorrect:
            if await ask('The Gym name is {} ?'.format(gym_autocorrect.title()), author, channel):
                gym = gyms[guild_dict[guild.id]["region"]][gym_autocorrect]
    if not gym:
        pass#await channel.send("Use **!gym [gym_name]** to send the gym location.")
    return gym

async def find_pokestop(entered_pokestop, author, channel):
    guild = channel.guild
    if( guild_dict[guild.id].get("region", None) is None ):
        await channel.send("Use **!region [region]**")
        return

    entered_pokestop = entered_pokestop.lower()
    pokestop = pokestops[guild_dict[guild.id]["region"]].get(entered_pokestop, None)
    if not gym:
        pokestop_autocorrect = autocorrect(entered_pokestop, pokestops[guild_dict[guild.id]["region"]].keys(), author, channel)
        if pokestop_autocorrect:
            if await ask('The Pokestop name is {} ?'.format(pokestop_autocorrect.title()), author, channel):
                pokestop = pokestops[guild_dict[guild.id]["region"]][pokestop_autocorrect]
    if not pokestop:
        return
    return pokestop

def autocorrect(word, word_list, user, channel):
    close_matches = difflib.get_close_matches(word, word_list, n=1, cutoff=0.6)
    if ( len(close_matches) <= 0 ):
        return None
    return close_matches[0]

async def ask(message, user, channel):
    react_list = ['👍', '👎']
    rusure = await channel.send(message)
    def check(reaction, user_react):
        return reaction.message.id == rusure.id and user.id == user_react.id and (reaction.emoji in react_list)
    for r in react_list:
        await asyncio.sleep(0.25)
        await rusure.add_reaction(r)
    try:
        reaction, user = await James.wait_for('reaction_add', check=check, timeout=60)
        await rusure.delete()
        return reaction.emoji == '👍'
    except asyncio.TimeoutError:
        await rusure.delete()
        return False

"""
Commands
"""

@James.command()
async def gym(ctx):
    message = ctx.message
    channel = message.channel
    author = message.author
    guild = channel.guild

    args = message.clean_content.split()[1:]
    if len(args) == 0:
        await channel.send('Give me the gym name!')
        return
    entered_gym = ' '.join(args)
    gym = await find_gym(entered_gym, author, channel)
    if gym:
        maps_link = 'https://www.google.com/maps/search/?api=1&query={}'.format('+'.join(gym['Coordinates']))
        await channel.send(f'{maps_link}')
        if ("-" in channel.name) and gym["Ex Confirmed"]:
            role = discord.utils.get(channel.guild.roles, name="ex")
            if role:
                role = role.mention
            else:
                role = "ex"
            await channel.send('{} Raid Gym in {}'.format(role, entered_gym))

@James.command(hidden=True, aliases=['gym_d'])
async def d_gym(ctx):
    message = ctx.message
    channel = message.channel
    author = message.author
    guild = channel.guild

    args = message.clean_content.split()[1:]
    if len(args) == 0:
        await channel.send('Give me the gym name!')
        return
    entered_gym = ' '.join(args)
    gym = await find_gym(entered_gym, author, channel)
    if gym:
        await channel.send(f'{gym}')
        
@James.command(hidden=True, aliases=['all_gym_d'])
async def d_all_gym(ctx):
    message = ctx.message
    channel = message.channel

    await channel.send(f'{gyms}')

@James.command(aliases=['ps'])
async def pokestop(ctx):
    message = ctx.message
    channel = message.channel
    author = message.author
    guild = channel.guild

    args = message.clean_content.split()[1:]
    if len(args) == 0:
        await channel.send('Give me the pokestop name!')
        return
    entered_pokestop = ' '.join(args)
    pokestop = await find_pokestop(entered_pokestop, author, channel)
    if pokestop:
        maps_link = 'https://www.google.com/maps/search/?api=1&query={}'.format('+'.join(pokestop['Coordinates']))
        await channel.send(f'{maps_link}')

@James.command(hidden=True, aliases=['pokestop_d'])
async def d_pokestop(ctx):
    message = ctx.message
    channel = message.channel
    author = message.author
    guild = channel.guild

    args = message.clean_content.split()[1:]
    if len(args) == 0:
        await channel.send('Give me the pokestop name!')
        return
    entered_pokestop = ' '.join(args)
    pokestop = await find_pokestop(entered_pokestop, author, channel)
    if pokestop:
        await channel.send(f'{pokestop}')

@James.command(hidden=True, aliases=['all_pokestops_d'])
async def d_all_pokestops(ctx):
    message = ctx.message
    channel = message.channel

    await channel.send(f'{pokestops}')

@James.command(hidden=True)
async def region(ctx):
    message = ctx.message
    channel = message.channel
    guild = channel.guild

    args = message.clean_content.split()[1:]
    if len(args) == 0:
        await channel.send('Give me a region!')
        return
    region = ' '.join(args)
    if (region in CITY):
        guild_dict[guild.id]['region'] = region
        await message.add_reaction('✅')
    else:
        await message.add_reaction('❎')

@James.command()
async def events(ctx):
    message = ctx.message
    channel = message.channel
    guild = channel.guild

    events_url = "https://pokemon.gameinfo.io/en/js/list-events.js?v4.34.2"
    request = Request(events_url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urlopen(request)
    html = response.read().decode("utf-8")

    start = html.index("_event_data=") + len("_event_data=")
    end = html.index("if(!hasStorage)")
    html_array = html[start:end-1]
    events = json.loads(html_array)

    event_upcoming = []
    for event in events:
        if event.get('start', None):
            start_date = datetime.fromtimestamp(event['start'])
            if start_date >= datetime.now():
                event_upcoming.append( (event['name'], start_date) )
            continue

        if event.get('day', None) and event['day'] is not None:
            start_date = datetime.strptime(event['day'][0], "%Y-%m-%d")
            if start_date >= datetime.now():
                event_upcoming.append( (event['name'], start_date) )
            continue

    event_upcoming.sort(key=lambda x: x[1])
    text = ""
    for event in event_upcoming:
        text += "{} - {}\n".format(event[0], event[1].strftime('%d/%m/%Y'))

    embed = discord.Embed(title="Events", description=text, colour=guild.me.colour)
    await channel.send(embed=embed)


"""
Admin Commands
"""

@commands.is_owner()
@James.command(hidden=True)
async def reload(ctx):
    load_data()
    await ctx.message.add_reaction('☑')

@commands.is_owner()
@James.command(hidden=True)
async def restart(ctx):
    """Restart after saving.

    Usage: !restart.
    Calls the save function and restarts James."""
    await save()

    await ctx.channel.send('Restarting...')
    James._shutdown_mode = 26
    await James.logout()

@commands.is_owner()
@James.command(hidden=True)
async def exit(ctx):
    """Exit after saving.

    Usage: !exit.
    Calls the save function and quits the script."""
    await save()

    await ctx.channel.send('Shutting down...')
    James._shutdown_mode = 0
    await James.logout()


try:
    event_loop.run_until_complete(James.start(config['bot_token']))
except discord.LoginFailure:
    # Invalid token
    event_loop.run_until_complete(James.logout())
    James._shutdown_mode = 0
except KeyboardInterrupt:
    # Keyboard interrupt detected. Quitting...
    event_loop.run_until_complete(James.logout())
    James._shutdown_mode = 0
except Exception as e:
    # logger.critical('Fatal exception', exc_info=e)
    event_loop.run_until_complete(James.logout())
finally:
    pass
sys.exit(James._shutdown_mode)
