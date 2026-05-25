import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import asyncio

DATA_FILE = "data/title_config.json"

DEFAULT_KEYWORDS = {
    "red": "🔥",
    "blue": "💧",
    "green": "🌿",
    "gold": "⭐",
    "silver": "⚔️",
    "purple": "💜",
    "black": "🌑",
    "white": "⬜",
    "pink": "🌸",
    "yellow": "☀️",
    "orange": "🍊",
    "admin": "👑",
    "owner": "💎",
    "mod": "🛡️",
    "moderator": "🛡️",
    "staff": "🔧",
    "helper": "💚",
    "vip": "✨",
    "booster": "🚀",
    "member": "🌀",
    "new": "🌱",
    "veteran": "🏅",
    "legend": "🦁",
    "elite": "⚡",
    "pro": "🎯",
    "developer": "💻",
    "dev": "💻",
    "artist": "🎨",
    "music": "🎵",
    "gamer": "🎮",
    "bot": "🤖",
}


def load_config() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(config: dict):
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(config, f, indent=2)


def _guild_cfg(guild_id: int) -> dict:
    return load_config().get(str(guild_id), {})


def _update_guild_cfg(guild_id: int, updates: dict):
    config = load_config()
    key = str(guild_id)
    if key not in config:
        config[key] = {}
    config[key].update(updates)
    save_config(config)


def get_keyword_map(guild_id: int) -> dict:
    cfg = _guild_cfg(guild_id)
    overrides = cfg.get("keywords", {})
    merged = dict(DEFAULT_KEYWORDS)
    for k, v in overrides.items():
        if v is None:
            merged.pop(k, None)
        else:
            merged[k] = v
    return merged


def is_autoemoji_enabled(guild_id: int) -> bool:
    return _guild_cfg(guild_id).get("auto_emoji_enabled", False)


def set_autoemoji_enabled(guild_id: int, enabled: bool):
    _update_guild_cfg(guild_id, {"auto_emoji_enabled": enabled})


def get_cached_emoji(guild_id: int, role_name: str):
    return _guild_cfg(guild_id).get("emoji_cache", {}).get(role_name)


def save_cached_emoji(guild_id: int, role_name: str, emoji: str):
    config = load_config()
    key = str(guild_id)
    if key not in config:
        config[key] = {}
    if "emoji_cache" not in config[key]:
        config[key]["emoji_cache"] = {}
    config[key]["emoji_cache"][role_name] = emoji
    save_config(config)


def get_base_name(member: discord.Member) -> str:
    name = member.display_name
    if name.startswith("[") and "]" in name:
        name = name[name.index("]") + 1:].strip()
    return name


async def get_role_emoji(role: discord.Role, keyword_map: dict, guild_id: int, bot) -> str | None:
    role_name_lower = role.name.lower()

    for keyword, emoji in keyword_map.items():
        if keyword.lower() in role_name_lower:
            return emoji

    if not is_autoemoji_enabled(guild_id):
        return None

    cached = get_cached_emoji(guild_id, role.name)
    if cached is not None:
        return cached

    ai_cog = bot.get_cog("AI") if bot else None
    if not ai_cog:
        return None

    try:
        result = await ai_cog.quick_ai(
            f"Give me one single unicode emoji that best represents a Discord server role called '{role.name}'. "
            f"Reply with ONLY the emoji character, nothing else whatsoever.",
            system="You are an emoji picker. Reply with a single emoji only. No text, no punctuation, just one emoji."
        )
        emoji = result.strip().split()[0] if result.strip() else ""
        if emoji:
            save_cached_emoji(guild_id, role.name, emoji)
            return emoji
    except Exception:
        pass

    return None


def _build_nickname(role_name: str, emoji: str, base_name: str) -> str:
    prefix = f"[{role_name}{emoji}]"
    full = f"{prefix} {base_name}"
    if len(full) <= 32:
        return full
    max_role_len = 32 - len(f"[{emoji}]") - len(f" {base_name}") - 1
    if max_role_len > 1:
        prefix = f"[{role_name[:max_role_len]}{emoji}]"
        return f"{prefix} {base_name}"[:32]
    return f"[{emoji}] {base_name}"[:32]


async def update_member_title(member: discord.Member, keyword_map: dict = None, bot=None):
    if member.bot:
        return False
    if keyword_map is None:
        keyword_map = get_keyword_map(member.guild.id)

    base_name = get_base_name(member)
    roles = sorted(
        [r for r in member.roles if r.name != "@everyone"],
        key=lambda r: r.position,
        reverse=True
    )

    new_nick = base_name if member.nick else None
    matched_role = None
    matched_emoji = None

    for role in roles:
        emoji = await get_role_emoji(role, keyword_map, member.guild.id, bot)
        if emoji:
            matched_role = role.name
            matched_emoji = emoji
            new_nick = _build_nickname(role.name, emoji, base_name)
            break

    try:
        current = member.nick or ""
        desired = new_nick or ""
        if current != desired:
            await member.edit(nick=new_nick)
        return True, matched_role, matched_emoji
    except discord.Forbidden:
        return False, None, None
    except Exception:
        return False, None, None


class TitlesCog(commands.Cog, name="Titles"):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles != after.roles:
            keyword_map = get_keyword_map(after.guild.id)
            await update_member_title(after, keyword_map, self.bot)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        if before.name != after.name:
            keyword_map = get_keyword_map(after.guild.id)
            for member in after.members:
                if not member.bot:
                    await update_member_title(member, keyword_map, self.bot)
                    await asyncio.sleep(0.5)

    @app_commands.command(name="autoemoji", description="[Admin] Toggle automatic AI emoji assignment for unmatched roles.")
    @app_commands.describe(toggle="Turn auto-emoji on or off")
    @app_commands.choices(toggle=[
        app_commands.Choice(name="On", value="on"),
        app_commands.Choice(name="Off", value="off"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def autoemoji(self, interaction: discord.Interaction, toggle: app_commands.Choice[str]):
        enabled = toggle.value == "on"
        set_autoemoji_enabled(interaction.guild.id, enabled)

        if enabled:
            embed = discord.Embed(
                title="✅ Auto-Emoji Enabled",
                description=(
                    "Roles without a keyword match will now automatically be assigned a fitting emoji by AI.\n"
                    "Emojis are cached after first use — run `/settitleall` to apply to existing members."
                ),
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="🔴 Auto-Emoji Disabled",
                description="Only roles that match a defined keyword will receive an emoji in their title.",
                color=discord.Color.red()
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="settitleall", description="[Admin] Set titles for all members based on their roles.")
    @app_commands.checks.has_permissions(administrator=True)
    async def settitleall(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        keyword_map = get_keyword_map(interaction.guild.id)

        members = [m for m in interaction.guild.members if not m.bot]
        await interaction.followup.send(
            f"⏳ Updating titles for **{len(members)}** members... This may take a moment.",
            ephemeral=True
        )

        updated = 0
        failed = 0
        for member in members:
            result = await update_member_title(member, keyword_map, self.bot)
            if result[0]:
                updated += 1
            else:
                failed += 1
            await asyncio.sleep(0.4)

        embed = discord.Embed(title="✅ Title Update Complete", color=discord.Color.green())
        embed.add_field(name="Updated", value=str(updated), inline=True)
        embed.add_field(name="Failed (no permission)", value=str(failed), inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="settitle", description="[Admin] Set the title for a specific member.")
    @app_commands.describe(member="The member to update")
    @app_commands.checks.has_permissions(administrator=True)
    async def settitle(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)
        keyword_map = get_keyword_map(interaction.guild.id)
        success, role_name, emoji = await update_member_title(member, keyword_map, self.bot)

        if success:
            if role_name:
                await interaction.followup.send(
                    f"✅ Updated title for **{member.display_name}**: `[{role_name}{emoji}]`",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"✅ No matching role/emoji found for **{member.display_name}** — title cleared.",
                    ephemeral=True
                )
        else:
            await interaction.followup.send(
                f"❌ Could not update **{member.display_name}**'s nickname. I may lack permission (e.g. server owner).",
                ephemeral=True
            )

    @app_commands.command(name="removetitle", description="[Admin] Remove the title from a specific member.")
    @app_commands.describe(member="The member whose title to remove")
    @app_commands.checks.has_permissions(administrator=True)
    async def removetitle(self, interaction: discord.Interaction, member: discord.Member):
        base_name = get_base_name(member)
        try:
            await member.edit(nick=base_name if member.nick else None)
            await interaction.response.send_message(
                f"✅ Removed title from **{member.display_name}**.", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ I don't have permission to change **{member.display_name}**'s nickname.", ephemeral=True
            )

    @app_commands.command(name="titlekeywords", description="[Admin] View current keyword → emoji mappings.")
    @app_commands.checks.has_permissions(administrator=True)
    async def titlekeywords(self, interaction: discord.Interaction):
        keyword_map = get_keyword_map(interaction.guild.id)
        auto = is_autoemoji_enabled(interaction.guild.id)

        lines = [f"`{kw}` → {em}" for kw, em in sorted(keyword_map.items())]
        chunks = []
        chunk = []
        for line in lines:
            chunk.append(line)
            if len(chunk) >= 20:
                chunks.append("\n".join(chunk))
                chunk = []
        if chunk:
            chunks.append("\n".join(chunk))

        embed = discord.Embed(
            title="🏷️ Title Keyword Mappings",
            description=chunks[0] if chunks else "No keywords configured.",
            color=discord.Color.blurple()
        )
        embed.set_footer(
            text=f"Auto-emoji is {'ON' if auto else 'OFF'} | Use /addkeyword and /removekeyword to customize."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="addkeyword", description="[Admin] Add a custom keyword → emoji mapping.")
    @app_commands.describe(keyword="The keyword to match in role names", emoji="The emoji to assign")
    @app_commands.checks.has_permissions(administrator=True)
    async def addkeyword(self, interaction: discord.Interaction, keyword: str, emoji: str):
        config = load_config()
        key = str(interaction.guild.id)
        if key not in config:
            config[key] = {}
        if "keywords" not in config[key]:
            config[key]["keywords"] = {}
        config[key]["keywords"][keyword.lower()] = emoji
        save_config(config)
        await interaction.response.send_message(
            f"✅ Added mapping: `{keyword.lower()}` → {emoji}", ephemeral=True
        )

    @app_commands.command(name="removekeyword", description="[Admin] Remove a keyword mapping.")
    @app_commands.describe(keyword="The keyword to remove")
    @app_commands.checks.has_permissions(administrator=True)
    async def removekeyword(self, interaction: discord.Interaction, keyword: str):
        config = load_config()
        key = str(interaction.guild.id)
        kw_lower = keyword.lower()

        if key not in config:
            config[key] = {}
        if "keywords" not in config[key]:
            config[key]["keywords"] = {}

        if kw_lower in DEFAULT_KEYWORDS or kw_lower in config[key]["keywords"]:
            config[key]["keywords"][kw_lower] = None
            save_config(config)
            await interaction.response.send_message(
                f"✅ Removed keyword mapping for `{kw_lower}`.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Keyword `{kw_lower}` not found.", ephemeral=True
            )

    @autoemoji.error
    @settitleall.error
    @settitle.error
    @removetitle.error
    @titlekeywords.error
    @addkeyword.error
    @removekeyword.error
    async def admin_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Administrator** permission to use this command.", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(TitlesCog(bot))
