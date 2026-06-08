import discord
from discord.ext import commands
from discord import app_commands
import time
import random
from typing import Dict, Any, Tuple
from utils.embeds import EmbedFactory

ACTIVE_VERIFICATION_CHALLENGES: Dict[str, Tuple[str, str, str, float]] = {}
CHALLENGES_VOCABULARY = [
    "blue rabbit 482", "solar comet 913", "silver maple 147",
    "neon vortex 330", "emerald hawk 882", "cyber beacon 501",
    "carbon shadow 644", "matrix phantom 909", "quantum pulse 115"
]

class GSPVerifyChallengeModal(discord.ui.Modal, title="GSP Platform: Secure Gate Challenge"):
    def __init__(self, bot, correct_code: str, correct_phrase: str, threat_level: str):
        super().__init__()
        self.bot = bot
        self.correct_code = correct_code
        self.correct_phrase = correct_phrase
        self.threat_level = threat_level

        self.captcha_field = discord.ui.TextInput(
            label="Security Captcha (Case-Sensitive):",
            placeholder="Input visual security string here...",
            min_length=5,
            max_length=5,
            required=True
        )
        self.add_item(self.captcha_field)

        if self.threat_level in ["HIGH", "CRITICAL"]:
            self.phrase_field = discord.ui.TextInput(
                label="Required Visual Security Phrase:",
                placeholder="Type the provided text string exactly...",
                min_length=5,
                max_length=40,
                required=True
            )
            self.add_item(self.phrase_field)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        captcha_sol = self.captcha_field.value.strip().upper()
        phrase_sol = self.phrase_field.value.strip().lower() if len(self.children) > 1 else None

        if captcha_sol != self.correct_code:
            await self.bot.db.execute(
                "UPDATE gsp_identity SET verification_failures = verification_failures + 1 WHERE user_id = ?",
                (user_id,)
            )
            return await interaction.followup.send(
                embed=EmbedFactory.error("Verification captcha verification failed. Access denied.", system="Guard Verification™"),
                ephemeral=True
            )

        if self.threat_level in ["HIGH", "CRITICAL"] and phrase_sol != self.correct_phrase:
            await self.bot.db.execute(
                "UPDATE gsp_identity SET verification_failures = verification_failures + 1 WHERE user_id = ?",
                (user_id,)
            )
            return await interaction.followup.send(
                embed=EmbedFactory.error("Dynamic security phrase validation failed. Access denied.", system="Guard Verification™"),
                ephemeral=True
            )

        identity_cog = self.bot.get_cog("GuardIdentitySystem")
        if identity_cog:
            await self.bot.db.execute(
                """INSERT INTO gsp_identity (user_id, verification_attempts, verification_successes, status) 
                   VALUES (?, 1, 1, 'VERIFIED')
                   ON CONFLICT(user_id) DO UPDATE SET 
                   verification_attempts=verification_attempts+1, verification_successes=verification_successes+1, status='VERIFIED'""",
                (user_id,)
            )
            self.bot.cache.identities.pop(user_id, None)

        ACTIVE_VERIFICATION_CHALLENGES.pop(user_id, None)

        cog = self.bot.get_cog("GuardVerificationSystem")
        if cog:
            await cog.release_user_containment(interaction.guild, interaction.user)

        await interaction.followup.send(
            embed=EmbedFactory.success("Passed all adaptive threat evaluation challenges. Node clearance granted.", title="Threat Verification Resolved", system="Guard Identity™"),
            ephemeral=True
        )


class GSPVerifyPlatformGateway(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Initiate Platform Scan",
        style=discord.ButtonStyle.primary,
        emoji="🛡️",
        custom_id="gsp_gate_portal_trigger"
    )
    async def run_verify_sequence(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        identity_cog = self.bot.get_cog("GuardIdentitySystem")
        cog = self.bot.get_cog("GuardVerificationSystem")
        if not identity_cog or not cog:
            return await interaction.followup.send("Platform Engine Failure: Security components offline.", ephemeral=True)

        now = time.time()
        last_action = self.bot.cache.verification_rate_limits.get(user_id, 0.0)
        if now - last_action < 45:
            return await interaction.followup.send(
                embed=EmbedFactory.warning("Threat scanner rate limit active. Please wait 45 seconds.", system="Guard Shield™"),
                ephemeral=True
            )
        self.bot.cache.verification_rate_limits[user_id] = now

        identity = await identity_cog.get_or_create_identity(interaction.user.id)
        trust_score, trust_class = await identity_cog.calculate_trust_score(interaction.user, identity)

        threat_level = "LOW"
        if trust_score < 40:
            threat_level = "CRITICAL"
        elif trust_score < 65:
            threat_level = "HIGH"
        elif trust_score < 80:
            threat_level = "MEDIUM"

        if threat_level == "LOW":
            await cog.release_user_containment(interaction.guild, interaction.user)
            return await interaction.followup.send(
                embed=EmbedFactory.success("Passed low risk baseline characteristics check. Access granted.", system="Guard Identity™"),
                ephemeral=True
            )

        code = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=5))
        phrase = random.choice(CHALLENGES_VOCABULARY)
        ACTIVE_VERIFICATION_CHALLENGES[user_id] = (code, phrase, threat_level, time.time())

        noise = ["░", "▒", "▓", "█", "■", "•", "·", "°", "×"]
        lines = [
            "".join(random.choices(noise, k=18)),
            f" {random.choice(noise[:3])}  {code}  {random.choice(noise[:3])} ",
            "".join(random.choices(noise, k=18))
        ]
        ascii_captcha = "\n".join(lines)

        desc = (
            f"### Dynamic Threat Analysis Complete\n"
            f"• **Assessed Risk Level:** `{threat_level}`\n"
            f"• **Dynamic GSP Trust Score:** `{trust_score}/100`\n"
            f"• **Categorization Rating:** `{trust_class}`\n\n"
            f"**To verify your security session clearance, solve the captcha challenge:**\n"
        )

        if threat_level == "MEDIUM":
            desc += f"```\n{ascii_captcha}\n```\nClick **Solve Challenge** and input the captcha code."
        elif threat_level in ["HIGH", "CRITICAL"]:
            if threat_level == "CRITICAL":
                await cog.quarantine_user_containment(interaction.guild, interaction.user, "GSP Shield: Low Trust Score Threat Detection on scan.")
            desc += f"
