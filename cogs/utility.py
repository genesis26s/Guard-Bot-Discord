import discord
from discord.ext import commands
from discord import app_commands
import time
from utils.embeds import EmbedFactory

# Global track values
BOOT_TIMESTAMP = time.time()

class UtilitySystem(commands.Cog):
    """
    🛡️ GUARD UTILITY™
    Dynamic utility tools: latency, snipes, editsnipes, and AFK systems.
    """
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        # Capture deleted items
        buffer = self.bot.cache.deleted_messages[message.channel.id]
        buffer.append({
            "author": message.author,
            "content": message.content,
            "timestamp": time.time()
        })
        # Keep buffer limited to 5 records
        if len(buffer) > 5:
            buffer.pop(0)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        
        buffer = self.bot.cache.edited_messages[before.channel.id]
        buffer.append({
            "author": before.author,
            "before": before.content,
            "after": after.content,
            "timestamp": time.time()
        })
        if len(buffer) > 5:
            buffer.pop(0)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Check AFK Mentions
        for mention in message.mentions:
            afk_key = f"{message.guild.id}:{mention.id}"
            if afk_key in self.bot.cache.afk_users:
                data = self.bot.cache.afk_users[afk_key]
                time_diff = int(time.time() - data["timestamp"])
                await message.reply(f"💤 **{mention.name}** is currently AFK: `{data['status']}` ({time_diff}s ago)")

        # Clear active AFK status if user types
        my_key = f"{message.guild.id}:{message.author.id}"
        if my_key in self.bot.cache.afk_users:
            self.bot.cache.afk_users.pop(my_key)
            await message.channel.send(f"👋 Welcome back, {message.author.mention}! Your AFK status has been cleared.", delete_after=5)

    @app_commands.command(name="ping", description="Check current connection latency parameters.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(embed=EmbedFactory.panel("Gateway Latency Diagnostics", f"• Response speed: `{latency}ms`", system="Guard Utility™"))

    @app_commands.command(name="uptime", description="View active node execution runtime.")
    async def uptime(self, interaction: discord.Interaction):
        uptime_seconds = int(time.time() - BOOT_TIMESTAMP)
        formatted_uptime = str(timedelta_formatted := timedelta_hours_min_sec(uptime_seconds))
        await interaction.response.send_message(embed=EmbedFactory.panel("Sentinel Platform Uptime", f"• Running Node operations: `{formatted_uptime}`", system="Guard Utility™"))

    @app_commands.command(name="snipe", description="Instantly recover the last message deleted in this channel.")
    async def snipe(self, interaction: discord.Interaction):
        buffer = self.bot.cache.deleted_messages.get(interaction.channel_id)
        if not buffer:
            return await interaction.response.send_message(embed=EmbedFactory.warning("No recently deleted items tracked inside this channel buffer.", system="Guard Utility™"), ephemeral=True)

        record = buffer[-1]
        embed = EmbedFactory.panel(
            f"Trace Message Sniper Output",
            f"• **Target User:** {record['author'].mention} (`{record['author'].id}`)\n"
            f"• **Clean Content:**\n```\n{record['content'] or '[No text content]'}\n```",
            system="Guard Utility™"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="editsnipe", description="Review old and new states of the last edited message.")
    async def editsnipe(self, interaction: discord.Interaction):
        buffer = self.bot.cache.edited_messages.get(interaction.channel_id)
        if not buffer:
            return await interaction.response.send_message(embed=EmbedFactory.warning("No recently edited items tracked inside this channel buffer.", system="Guard Utility™"), ephemeral=True)

        record = buffer[-1]
        embed = EmbedFactory.panel(
            f"Edit Trace Output",
            f"• **Target User:** {record['author'].mention}\n"
            f"• **Old Message state:**\n```\n{record['before']}\n```\n"
            f"• **New Message state:**\n```\n{record['after']}\n```",
            system="Guard Utility™"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="afk", description="Set an away-from-keyboard status note.")
    @app_commands.describe(status="Your current AFK note.")
    async def afk(self, interaction: discord.Interaction, status: str = "AFK"):
        my_key = f"{interaction.guild.id}:{interaction.user.id}"
        self.bot.cache.afk_users[my_key] = {
            "status": status,
            "timestamp": time.time()
        }
        await interaction.response.send_message(f"💤 {interaction.user.mention} is now AFK: `{status}`")

def timedelta_hours_min_sec(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}h {m}m {s}s"

async def setup(bot):
    await bot.add_cog(UtilitySystem(bot))
