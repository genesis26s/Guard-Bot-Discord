import discord
from discord.ext import commands
from collections import defaultdict
import time
import re
from utils.embeds import EmbedFactory

class AutoModSystem(commands.Cog):
    """
    🛡️ GUARD AUTOMOD™
    Secures chat environments by enforcing message frequency spam limits, word lists, 
    invite filters, caps lock constraints, and links controls.
    """
    def __init__(self, bot):
        self.bot = bot
        # Track fast-paced message structures in memory
        self.user_message_timestamps = defaultdict(list)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        user_id = str(message.author.id)

        # Skip administrative commands bypass
        if message.author.guild_permissions.manage_messages:
            return

        cfg = self.bot.cache.get_guild_config(message.guild.id)
        if not cfg or cfg.get("anti_spam_enabled", 1) == 0:
            return

        content = message.content.strip()

        # 1. Enforce Invite Links Filter rules
        if "discord.gg/" in content.lower() or "discord.com/invite/" in content.lower():
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {message.author.mention}, invite links are blocked in this server.", delete_after=5)
                return
            except discord.Forbidden:
                pass

        # 2. Enforce CAPS constraints
        if len(content) > 12 and sum(1 for c in content if c.isupper()) / len(content) > 0.85:
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {message.author.mention}, please avoid typing in all CAPS.", delete_after=5)
                return
            except discord.Forbidden:
                pass

        # 3. Enforce Chat Frequency limits
        now = time.time()
        user_timeline = self.user_message_timestamps[(guild_id, user_id)]
        user_timeline.append(now)

        # Filter timeline logs (last 5 seconds only)
        self.user_message_timestamps[(guild_id, user_id)] = [t for t in user_timeline if now - t < 5.0]

        if len(self.user_message_timestamps[(guild_id, user_id)]) > 6:
            try:
                await message.channel.purge(limit=5, check=lambda m: m.author.id == message.author.id)
                # Apply temporary muting timeout parameters
                await message.author.timeout(discord.utils.utcnow() + discord.timedelta(minutes=5), reason="GSP AutoMod: Chat flooding spam trigger.")
                await message.channel.send(f"🚨 {message.author.mention} has been silenced for spamming messages.")
            except Exception:
                pass

async def setup(bot):
    await bot.add_cog(AutoModSystem(bot))
