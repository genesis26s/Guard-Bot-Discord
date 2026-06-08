import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
from utils.embeds import EmbedFactory

class ModerationSystem(commands.Cog):
    """
    🛡️ GUARD MODERATION™
    Core moderation commands with visual SOC designs.
    """
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ban", description="Permanently ban a user from the server.")
    @app_commands.describe(user="The member to ban.", reason="Reason for the ban.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided."):
        await interaction.response.defer()
        try:
            await user.send(embed=EmbedFactory.error(f"You have been banned from **{interaction.guild.name}**.\nReason: {reason}"))
        except discord.Forbidden:
            pass

        try:
            await user.ban(reason=reason)
            await interaction.followup.send(embed=EmbedFactory.success(f"Successfully banned **{user}** from server directories.", system="Guard Moderation™"))
        except discord.Forbidden:
            await interaction.followup.send(embed=EmbedFactory.error("GSP failed to execute ban. Check hierarchy permissions.", system="Guard Moderation™"))

    @app_commands.command(name="kick", description="Remove a member from the server.")
    @app_commands.describe(user="The member to kick.", reason="Reason for the kick.")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided."):
        await interaction.response.defer()
        try:
            await user.send(embed=EmbedFactory.warning(f"You have been kicked from **{interaction.guild.name}**.\nReason: {reason}"))
        except discord.Forbidden:
            pass

        try:
            await user.kick(reason=reason)
            await interaction.followup.send(embed=EmbedFactory.success(f"Successfully kicked **{user}**.", system="Guard Moderation™"))
        except discord.Forbidden:
            await interaction.followup.send(embed=EmbedFactory.error("GSP failed to execute kick. Check permissions.", system="Guard Moderation™"))

    @app_commands.command(name="timeout", description="Temporarily restrict a user from sending messages.")
    @app_commands.describe(user="The user to mute.", duration_minutes="Mute length in minutes.", reason="Reason.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, user: discord.Member, duration_minutes: int, reason: str = "No reason provided."):
        await interaction.response.defer()
        try:
            td = timedelta(minutes=duration_minutes)
            await user.timeout(discord.utils.utcnow() + td, reason=reason)
            await interaction.followup.send(embed=EmbedFactory.success(f"Successfully timed out **{user}** for **{duration_minutes}** minutes.", system="Guard Moderation™"))
        except discord.Forbidden:
            await interaction.followup.send(embed=EmbedFactory.error("GSP failed to timeout user. Verify permissions.", system="Guard Moderation™"))

    @app_commands.command(name="untimeout", description="Lift timeout constraints from a user.")
    @app_commands.describe(user="The user to unmute.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer()
        try:
            await user.timeout(None)
            await interaction.followup.send(embed=EmbedFactory.success(f"Successfully restored permissions for **{user}**.", system="Guard Moderation™"))
        except discord.Forbidden:
            await interaction.followup.send(embed=EmbedFactory.error("GSP failed to clear timeouts.", system="Guard Moderation™"))

    @app_commands.command(name="clear", description="Quickly delete messages from this channel.")
    @app_commands.describe(amount="The amount of messages to purge.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        purged = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(embed=EmbedFactory.success(f"Purged **{len(purged)}** messages from history.", system="Guard Moderation™"), ephemeral=True)

async def setup(bot):
    await bot.add_cog(ModerationSystem(bot))
