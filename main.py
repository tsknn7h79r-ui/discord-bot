import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class DiscordBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self):
        extensions = [
            "cogs.fun",
            "cogs.extra_fun",
            "cogs.utility",
            "cogs.titles",
            "cogs.levels",
            "cogs.ai_cog",
            "cogs.help_cog",
        ]
        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"Loaded {ext}")
            except Exception as e:
                print(f"Failed to load {ext}: {e}")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

        # Directly wipe ALL global commands via Discord's REST API
        # This is the only reliable way to remove stale global commands
        try:
            await self.http.bulk_upsert_global_commands(self.application_id, [])
            print("Wiped all global commands from Discord API.")
        except Exception as e:
            print(f"Warning: could not wipe global commands: {e}")

        # Sync guild-specific commands (appear instantly, no global duplicates)
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f"Synced to: {guild.name}")
            except Exception as e:
                print(f"Failed to sync to {guild.name}: {e}")

        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name="/help | Powered by AI"
        )
        await self.change_presence(activity=activity)

    async def on_guild_join(self, guild: discord.Guild):
        try:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"New guild synced: {guild.name}")
        except Exception as e:
            print(f"Failed to sync new guild {guild.name}: {e}")


bot = DiscordBot()

token = os.environ.get("DISCORD_TOKEN")
if not token:
    print("ERROR: DISCORD_TOKEN is not set. Please add it to Secrets.")
    exit(1)

bot.run(token)
