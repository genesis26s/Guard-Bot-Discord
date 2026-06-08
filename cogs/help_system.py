import discord
from discord.ext import commands
from discord import app_commands
from utils.embeds import EmbedFactory

# Custom humanized name and clean summaries for each GSP Cog class
COG_METADATA_CLEAN_MAP = {
    "GuardIdentitySystem": {
        "emoji": "🔨",
        "clean_name": "Server Identity Matrix",
        "description": "User tracking matrices, join date, verification rates and reputation scores."
    },
    "GuardVerificationSystem": {
        "emoji": "🛡",
        "clean_name": "Verification Gate",
        "description": "Multi-tier distorted captcha checks and automatic quarantine containment."
    },
    "GuardIntelligence": {
        "emoji": "🔬",
        "clean_name": "Dynamic Forensics",
        "description": "VPN trackers, character matching alt trackers, and bot solve timing analytics."
    },
    "GuardProtection": {
        "emoji": "📡",
        "clean_name": "Active Protections",
        "description": "Raid trackers, lockdowns, shield escalations and permission audits."
    },
    "TicketSystem": {
        "emoji": "🎫",
        "clean_name": "Support Ticket Panels",
        "description": "Custom tickets dropdown panels setups and admin dashboards."
    },
    "LevelSystem": {
        "emoji": "⭐",
        "clean_name": "Text Leveling",
        "description": "Customizable join/leave greeting logs and milestones role rewards."
    },
    "AutoModSystem": {
        "emoji": "🔒",
        "clean_name": "Chat Filtering",
        "description": "Invitations, caps-lock triggers, and flood frequency spam checks."
    },
    "LoggingSystem": {
        "emoji": "📝",
        "clean_name": "Security Log Routing",
        "description": "Channel logging paths and log category routers."
    },
    "ModerationSystem": {
        "emoji": "🔨",
        "clean_name": "Moderation Tools",
        "description": "Quick bans, kicks, warnings, clears and temporary timeouts."
    },
    "UtilitySystem": {
        "emoji": "⚙️",
        "clean_name": "Utilities Modules",
        "description": "Ping diagnostic metrics, message snipers, and AFK status panels."
    }
}

class GSPDynamicDropdownMenu(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = []

        for cog_name, cog in self.bot.cogs.items():
            app_cmds = cog.get_app_commands()
            if not app_cmds:
                continue
            
            meta = COG_METADATA_CLEAN_MAP.get(cog_name, {
                "emoji": "⚙️",
                "clean_name": cog_name.replace("System", "").replace("Cog", ""),
                "description": "View associated platform commands."
            })
            
            options.append(discord.SelectOption(
                label=meta["clean_name"],
                value=cog_name,
                description=meta["description"],
                emoji=meta["emoji"]
            ))

        super().__init__(
            placeholder="Choose platform subsystem manual...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="gsp_dynamic_help_selector"
        )

    async def callback(self, interaction: discord.Interaction):
        cog_name = self.values[0]
        cog = self.bot.get_cog(cog_name)
        
        if not cog:
            return await interaction.response.send_message(embed=EmbedFactory.error("Target GSP system component offline."), ephemeral=True)

        meta = COG_METADATA_CLEAN_MAP.get(cog_name, {
            "emoji": "⚙️",
            "clean_name": cog_name,
            "description": ""
        })

        embed = discord.Embed(
            title=f"{meta['emoji']} {meta['clean_name']} Command Reference",
            color=EmbedFactory.COLOR_GSP_CYAN
        )

        app_cmds = cog.get_app_commands()
        desc = ""
        for cmd in app_cmds:
            if isinstance(cmd, app_commands.Group):
                for sub_cmd in cmd.commands:
                    desc += f"• `/{cmd.name} {sub_cmd.name}` - {sub_cmd.description or 'Active subcommand.'}\n"
            else:
                desc += f"• `/{cmd.name}` - {cmd.description or 'Active command.'}\n"

        embed.description = desc or "*No commands mapped to this component.*"
        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpSystemView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=180)
        self.add_item(GSPDynamicDropdownMenu(bot))


class HelpSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="🛡️ Guard Help™ — Opens dynamic, zero-maintenance operational manual.")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👋 Guard Security Platform™ Manual Portal",
            description=(
                "Guard Security Platform operates on dynamic operational trees.\n"
                "Select any subsystem from the menu below to view real-time descriptions and commands."
            ),
            color=EmbedFactory.COLOR_GSP_CYAN
        )
        embed.add_field(
            name="📡 Node Connections Speed", 
            value=f"• Connection Response: `{round(self.bot.latency * 1000)}ms`"
        )
        
        view = HelpSystemView(self.bot)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(HelpSystem(bot))
