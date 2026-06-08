import discord
from datetime import datetime

class EmbedFactory:
    """
    Standardized, high-fidelity cybersecurity design engine for GSP alerts,
    consoles, and monitoring reports. Inspired by enterprise security operation centers (SOC).
    """
    COLOR_GSP_CYAN = discord.Color.from_rgb(0, 240, 255)      # GSP Core Interface
    COLOR_GSP_GREEN = discord.Color.from_rgb(0, 255, 127)     # Secure Status
    COLOR_GSP_AMBER = discord.Color.from_rgb(255, 170, 0)     # Suspicious Threat Warning
    COLOR_GSP_RED = discord.Color.from_rgb(255, 45, 85)       # Critical Attack Vector
    COLOR_GSP_CARBON = discord.Color.from_rgb(20, 20, 22)     # Carbon Operations Panel

    @staticmethod
    def _create_soc_frame(title: str, description: str, color: discord.Color, system_origin: str) -> discord.Embed:
        embed = discord.Embed(
            title=f"🛡️ SECURE INTERFACE: {system_origin.upper()}",
            description=f"### **[{title.upper()}]**\n\n{description}",
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(
            text="GUARD SECURITY PLATFORM™ | ENTERPRISE SENTINEL ENGINE v1.0",
            icon_url=None
        )
        return embed

    @staticmethod
    def console(title: str, description: str, system: str = "Guard Identity™") -> discord.Embed:
        return EmbedFactory._create_soc_frame(title, description, EmbedFactory.COLOR_GSP_CARBON, system)

    @staticmethod
    def panel(title: str, description: str, system: str = "Guard Trust™") -> discord.Embed:
        return EmbedFactory._create_soc_frame(title, description, EmbedFactory.COLOR_GSP_CYAN, system)

    @staticmethod
    def success(description: str, title: str = "Clearance Authorized", system: str = "Guard Shield™") -> discord.Embed:
        return EmbedFactory._create_soc_frame(title, description, EmbedFactory.COLOR_GSP_GREEN, system)

    @staticmethod
    def warning(description: str, title: str = "Anomalous Metric Flagged", system: str = "Guard Sentinel™") -> discord.Embed:
        return EmbedFactory._create_soc_frame(title, description, EmbedFactory.COLOR_GSP_AMBER, system)

    @staticmethod
    def error(description: str, title: str = "Intrusion Containment Active", system: str = "Guard Quarantine™") -> discord.Embed:
        return EmbedFactory._create_soc_frame(title, description, EmbedFactory.COLOR_GSP_RED, system)
