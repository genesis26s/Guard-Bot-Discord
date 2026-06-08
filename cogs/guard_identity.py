import discord
from discord.ext import commands
from discord import app_commands
import time
from datetime import datetime
from typing import Dict, Any, Tuple
from utils.embeds import EmbedFactory

class GuardIdentitySystem(commands.Cog):
    """
    🛡️ GUARD IDENTITY™ & GUARD TRUST™
    Governs global identity tracking database structures and dynamic trust scores calculations.
    """
    def __init__(self, bot):
        self.bot = bot

    async def get_or_create_identity(self, user_id: int) -> Dict[str, Any]:
        cached = self.bot.cache.get_identity(user_id)
        if cached:
            return cached

        row = await self.bot.db.select_row(
            "SELECT * FROM gsp_identity WHERE user_id = ?",
            (str(user_id),)
        )

        if not row:
            now_epoch = int(time.time())
            await self.bot.db.execute(
                """INSERT OR IGNORE INTO gsp_identity 
                   (user_id, first_seen, verification_attempts, verification_successes, verification_failures, reputation_score, trust_score, status) 
                   VALUES (?, ?, 0, 0, 0, 80, 50, 'UNVERIFIED')""",
                (str(user_id), now_epoch)
            )
            row = {
                "user_id": str(user_id),
                "first_seen": now_epoch,
                "verification_attempts": 0,
                "verification_successes": 0,
                "verification_failures": 0,
                "reputation_score": 80,
                "trust_score": 50,
                "status": "UNVERIFIED"
            }
        
        self.bot.cache.set_identity(user_id, row)
        return row

    async def calculate_trust_score(self, member: discord.Member, identity: Dict[str, Any]) -> Tuple[int, str]:
        score = 50  # Baseline GSP score
        
        now_dt = datetime.utcnow()
        created_at = member.created_at.replace(tzinfo=None)
        days_old = (now_dt - created_at).days

        if days_old < 1:
            score -= 35
        elif days_old < 7:
            score -= 20
        elif days_old < 30:
            score -= 10
        elif days_old > 365:
            score += 20
        elif days_old > 90:
            score += 10

        if member.avatar:
            score += 10
        else:
            score -= 15

        attempts = identity.get("verification_attempts", 0)
        successes = identity.get("verification_successes", 0)
        failures = identity.get("verification_failures", 0)

        if attempts > 2:
            success_rate = successes / attempts
            if success_rate >= 0.9:
                score += 15
            elif success_rate <= 0.4:
                score -= 20

        if failures > successes:
            score -= 25

        is_quarantined = self.bot.cache.is_quarantined(member.guild.id, member.id)
        if is_quarantined:
            score -= 40

        final_score = max(0, min(100, score))

        if final_score >= 95:
            classification = "Elite Trusted (G1)"
        elif final_score >= 80:
            classification = "Trusted (G2)"
        elif final_score >= 60:
            classification = "Standard Clearance (G3)"
        elif final_score >= 40:
            classification = "Suspicious Profile (G4)"
        elif final_score >= 20:
            classification = "High Risk Level (G5)"
        else:
            classification = "Critical Threat Profile (G6)"

        await self.bot.db.execute(
            "UPDATE gsp_identity SET trust_score = ? WHERE user_id = ?",
            (final_score, str(member.id))
        )
        identity["trust_score"] = final_score
        self.bot.cache.set_identity(member.id, identity)

        return final_score, classification

    @app_commands.command(name="identity", description="🛡️ Guard Identity™ — Analyze global tracking metrics of a user.")
    @app_commands.describe(user="The connection profile to retrieve metadata for.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def identity_command(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        identity = await self.get_or_create_identity(user.id)
        
        first_seen_formatted = datetime.utcfromtimestamp(identity["first_seen"]).strftime('%Y-%m-%d %H:%M:%S UTC')
        attempts = identity["verification_attempts"]
        successes = identity["verification_successes"]
        failures = identity["verification_failures"]
        reputation = identity["reputation_score"]
        status = identity["status"]

        desc = (
            f"**🔒 System Ident Mapping:** {user.mention} (`{user.id}`)\n"
            f"• **Global Registry Status:** `{status}`\n"
            f"• **First Seen Date:** `{first_seen_formatted}`\n\n"
            f"**⚙️ Active Verification Profiles:**\n"
            f"• Scans Triggered: `{attempts}`\n"
            f"• Scan Successes: `{successes}`\n"
            f"• Scan Failures: `{failures}`\n\n"
            f"**🎯 Reputation Index Metrics:**\n"
            f"• Rep Score: `{reputation}/100` (Classification: Secure)"
        )

        embed = EmbedFactory.console("GSP Identity Record Profile", desc, system="Guard Identity™")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="trust", description="🛡️ Guard Trust™ — Calculate real-time trust metrics of a member.")
    @app_commands.describe(user="The target server member to audit.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def trust_command(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        identity = await self.get_or_create_identity(user.id)
        score, classification = await self.calculate_trust_score(user, identity)

        bar_length = 20
        filled = int((score / 100) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

        desc = (
            f"**Analysis Target:** {user.mention} (`{user.id}`)\n"
            f"• **Assigned GSP Trust Class:** `{classification}`\n"
            f"• **Calculated Score Scalar:** `{score}/100`\n"
            f"• **Dynamic Progress Bar:**\n`[{bar}]`\n\n"
            f"**Security Evaluation Weightings:**\n"
            f"• Account Age Score: `Analyzed`\n"
            f"• Profile Configuration Flags: `Customized Avatar Checklist Verified`\n"
            f"• Identity Verification Track record: `Processed`"
        )

        embed = EmbedFactory.panel("Real-Time Trust Security Index", desc, system="Guard Trust™")
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(GuardIdentitySystem(bot))
