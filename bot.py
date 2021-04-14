import datetime
import traceback
import logging
import sys
import copy
import json
import sqlite3
import aiohttp

import discord

from discord.ext import commands


INITIAL_EXTENSIONS = [
    'cogs.admin',
    'cogs.poll',
    'cogs.ping',
    'cogs.tags',
    'cogs.automod',
    'cogs.bio',
    'cogs.stats',
    'cogs.stattrak',
    'cogs.meta',
    'cogs.blizzard',
    'cogs.ckc',
    'cogs.convert',
    'cogs.mod',
    'cogs.twitch',
    'cogs.highlight',
    'cogs.nsfw',
    'cogs.reminders',
    'cogs.roles',
    'cogs.stars',
    'cogs.wolfram'
]


def load_json(filename):
    """
    Loads a json file, wow
    """
    with open(filename, encoding='utf-8') as infile:
        return json.load(infile)


def write_json(filename, contents):
    """
    Updates a json file, wow
    """
    with open(filename, 'w') as outfile:
        json.dump(contents, outfile, ensure_ascii=True, indent=4)


conn = sqlite3.connect('database.db')
c = conn.cursor()

log = logging.getLogger(__name__)


def _prefix_callable(bot, msg):
    user_id = bot.user.id
    base = ['<@!{}> '.format(user_id), '<@{}> '.format(user_id)]
    if msg.guild is None:
        base.append('!')
        base.append('?')
    else:
        base.extend(bot.prefixes.get(msg.guild.id, ['?', '!']))
    return base


def load_credentials():
    """
    Yes, this literally just gets me my token
    this is probably a very good thing since
    I seem to have a thing for pushing tokens
    """
    with open('cred.json') as f:
        return json.load(f)


credentials = load_credentials()


class CarlBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=_prefix_callable,
                         description="Better than the last one",
                         help_attrs=dict(hidden=True))
        self.client_id = 235148962103951360
        self.owner_id = 106429844627169280
        c.execute('SELECT * FROM servers WHERE 1')
        server_rows = c.fetchall()
        pre = {k[0]: k[5] or '!,?' for k in server_rows}
        self.prefixes = {int(k): v.split(',') for (k, v) in pre.items()}
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.token = credentials["token"]
        # self.remove_command('help')

        for extension in INITIAL_EXTENSIONS:
            try:
                self.load_extension(extension)
            except Exception as e:
                print('Failed to load extension {}\n{}: {}'.format(
                    extension, type(e).__name__, e))

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.author.send('This command cannot be used in private messages.')
        elif isinstance(error, commands.DisabledCommand):
            await ctx.author.send('Sorry. This command is disabled and cannot be used.')
        elif isinstance(error, commands.CommandInvokeError):
            print(f'In {ctx.command.qualified_name}:', file=sys.stderr)
            traceback.print_tb(error.original.__traceback__)
            print(
                f'{error.original.__class__.__name__}: {error.original}', file=sys.stderr)

    async def on_ready(self):
        """
        A lot of commands are dependant on information found in the database
        This abuses the api into giving me the required information
        useful for when the bot joins a server while offline
        """
        print('Logged in as:')
        print('Username: ' + self.user.name)
        print('ID: ' + str(self.user.id))
        print('------')
        if not hasattr(self, 'uptime'):
            self.uptime = datetime.datetime.utcnow()
        for server in self.guilds:
            c.execute('''INSERT OR IGNORE INTO servers
                            VALUES (?, ?, ?, ?, ?, ?)''',
                        (str(server.id), None, None, None, None, '?,!'))
            conn.commit()
            c.execute('''INSERT OR IGNORE INTO logging
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (str(server.id), 1, 1, 1, 1, 1, 1, 1, None))
            conn.commit()
            c.execute('''INSERT OR IGNORE INTO config
                            VALUES (?, ?, ?, ?, ?, ?)''',
                        (server.id, None, None, True, None, None))
            conn.commit()
            c.execute('''INSERT OR IGNORE INTO role_config
                            VALUES (?, ?, ?, ?, ?)''',
                        (None, False, str(server.id), None, True))
            conn.commit()
        
    def get_guild_prefixes(self, guild, *, local_inject=_prefix_callable):
        """
        Since prefixes are per server now, we need a way to retrieve them
        """
        proxy_msg = discord.Object(id=None)
        proxy_msg.guild = guild
        return local_inject(self, proxy_msg)

    def get_raw_guild_prefixes(self, guild_id):
        """
        So that the bot isn't useless if something goes wrong
        """
        return self.prefixes.get(guild_id, ['?', '!'])

    async def set_guild_prefixes(self, guild, prefixes):
        """
        Prefixes need to be available the second you add one, not when you restart the bot
        """
        if not prefixes:
            c.execute('UPDATE servers SET prefix=? WHERE id=?',
                      (None, guild.id))
            conn.commit()
            self.prefixes[guild.id] = prefixes
        elif len(prefixes) > 15:
            raise RuntimeError('Cannot have more than 10 custom prefixes.')
        else:
            c.execute('''UPDATE servers
                         SET prefix=? 
                         WHERE id=?''',
                      (','.join(sorted(set(prefixes))), str(guild.id)))
            conn.commit()
            self.prefixes[guild.id] = sorted(set(prefixes))

    async def on_message(self, message):
        if message.author.bot:
            return
        await self.process_commands(message)
        ctx = await self.get_context(message)
        if ctx.invoked_with and ctx.invoked_with.lower() not in self.commands and ctx.command is None:
            msg = copy.copy(message)
            if ctx.prefix:
                new_content = msg.content[len(ctx.prefix):]
                msg.content = "{}tag get {}".format(ctx.prefix, new_content)
                await self.process_commands(msg)

    async def close(self):
        await super().close()
        await self.session.close()

    def run(self):
        super().run(self.token, reconnect=True)


if __name__ == '__main__':
    carlbot = CarlBot()
    carlbot.run()
