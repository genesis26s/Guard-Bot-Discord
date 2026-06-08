import discord
from discord.ext import commands
from utils.embeds import EmbedFactory

class LoggingSystem(commands.Cog):
    """
    🛡️ GUARD LOGGING SYSTEM™
    Bridges and routes logs seamlessly into server administrative log corridors.
    """
    def __init__(self, bot):
        self.bot = bot

    async def _send_log(self, guild: discord.Guild, column_name: str, embed: discord.Embed):
        guild_id_str = str(guild.id)
        
        # Check local DB log configurations
        row = await self.bot.db.select_row("SELECT * FROM guild_logs WHERE guild_id = ?", (guild_id_str,))
        if not row:
            return

        channel_id = row.get(column_name) or row.get("master_log_channel")
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        embed = EmbedFactory.panel(
            f"Message Deleted in #{message.channel.name}",
            f"• **User:** {message.author.mention} (`{message.author.id}`)\n"
            f"• **Text:**\n```\n{message.clean_content or '[No text contents]'}\n```",
            system="Guard Sentinel™"
        )
        await self._send_log(message.guild, "log_messages", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content:
            return

        embed = EmbedFactory.panel(
            f"Message Edited in #{before.channel.name}",
            f"• **User:** {before.author.mention} (`{before.author.id}`)\n"
            f"• **Before:**\n```\n{before.clean_content}\n```\n"
            f"• **After:**\n```\n{after.clean_content}\n```",
            system="Guard Sentinel™"
        )
        await self._send_log(before.guild, "log_messages", embed)

async def setup(bot):
    await bot.add_cog(LoggingSystem(bot))
