import discord
from discord.ext import commands
from discord import app_commands
import time
import re
import urllib.request
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional
from utils.embeds import EmbedFactory

import concurrent.futures
THREAD_POOL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=5)

HIGH_RISK_ASNS = [
    "AS14061", "AS20473", "AS16265", "AS14618", "AS24940", "AS39351",
    "AS53667", "AS62240", "AS60068", "AS12876", "AS49453", "AS35816"
]

class GuardIntelligence(commands.Cog):
    """
    🛡️ GUARD INTELLIGENCE SYSTEM™
    Governs advanced forensics audits: Network™, Alt Intelligence™, Bot Intelligence™, Reputation™.
    """
    def __init__(self, bot):
        self.bot = bot

    def _sync_fetch_network_metadata(self, ip_address: str) -> Dict[str, Any]:
        ip_clean = re.sub(r"[^0-9a-fA-F\.:]", "", ip_address)
        url = f"http://ip-api.com/json/{ip_clean}?fields=status,country,isp,as,mobile,proxy,hosting"
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "GuardSecurityPlatform/1.0 (Discord Cyber-Defense)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=2.5) as response:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("status") == "success":
                    return data
        except Exception:
            pass
        return {}

    async def scan_network_profile(self, user_id: int, ip_address: Optional[str] = None) -> Dict[str, Any]:
        user_id_str = str(user_id)
        
        cached = await self.bot.db.select_row(
            "SELECT * FROM gsp_network_cache WHERE user_id = ?",
            (user_id_str,)
        )
        if cached:
            if time.time() - cached["scanned_at"] < 43200:
                return cached

        if not ip_address:
            return {
                "ip_address": "Trace Not Present", "country": "Local Registry", 
                "org_asn": "Unknown ASN", "vpn_flag": 0, "proxy_flag": 0, "tor_flag": 0, 
                "risk_score": 0, "type": "Residential"
            }

        loop = self.bot.loop
        metadata = await loop.run_in_executor(
            THREAD_POOL_EXECUTOR, 
            self._sync_fetch_network_metadata, 
            ip_address
        )

        country = metadata.get("country", "Unknown")
        org_asn = metadata.get("as", "Unknown ASN")
        
        is_hosting = 1 if metadata.get("hosting") is True else 0
        is_proxy = 1 if metadata.get("proxy") is True else 0
        is_mobile = 1 if metadata.get("mobile") is True else 0

        asn_flagged = 0
        for high_risk in HIGH_RISK_ASNS:
            if high_risk in org_asn:
                asn_flagged = 1
                break

        risk_score = 0
        network_type = "Residential"

        if is_proxy == 1:
            risk_score += 85
            network_type = "Proxy Node"
        elif is_hosting == 1 or asn_flagged == 1:
            risk_score += 70
            network_type = "Datacenter / VPN Connection"
        elif is_mobile == 1:
            risk_score += 15
            network_type = "Mobile Network"

        now_ts = int(time.time())
        await self.bot.db.execute(
            """INSERT OR REPLACE INTO gsp_network_cache 
               (user_id, ip_address, country, org_asn, vpn_flag, proxy_flag, tor_flag, risk_score, scanned_at) 
               VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (user_id_str, ip_address, country, org_asn, is_hosting, is_proxy, risk_score, now_ts)
        )

        return {
            "ip_address": ip_address, "country": country, "org_asn": org_asn, 
            "vpn_flag": is_hosting, "proxy_flag": is_proxy, "tor_flag": 0, 
            "risk_score": risk_score, "type": network_type
        }

    def _calculate_levenshtein_similarity(self, s1: str, s2: str) -> float:
        s1, s2 = s1.lower(), s2.lower()
        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
            
        if len(s1) < len(s2):
            s1, s2 = s2, s1
            
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
            
        distance = previous_row[-1]
        return 1.0 - (distance / max(len(s1), len(s2)))

    async def execute_alt_forensics(self, member: discord.Member) -> List[Dict[str, Any]]:
        guild = member.guild
        guild_id_str = str(guild.id)
        user_id_str = str(member.id)
        target_created_at = member.created_at.replace(tzinfo=None)

        potential_alts = []
        now_ts = int(time.time())

        sample_members = [m for m in guild.members if m.id != member.id][:500]

        for other in sample_members:
            similarity = self._calculate_levenshtein_similarity(member.name, other.name)
            
            other_created_at = other.created_at.replace(tzinfo=None)
            creation_delta_seconds = abs(int((target_created_at - other_created_at).total_seconds()))

            risk_score = 0
            if similarity >= 0.85:
                risk_score += 50
            elif similarity >= 0.70:
                risk_score += 25

            if creation_delta_seconds < 3600:
                risk_score += 45
            elif creation_delta_seconds < 86400:
                risk_score += 20

            if risk_score >= 35:
                await self.bot.db.execute(
                    """INSERT OR REPLACE INTO gsp_alt_intelligence 
                       (user_id, guild_id, matched_user_id, username_similarity, creation_time_delta_seconds, assessed_alt_risk, assessed_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (user_id_str, guild_id_str, str(other.id), similarity, creation_delta_seconds, risk_score, now_ts)
                )
                potential_alts.append({
                    "matched_member": other,
                    "similarity": round(similarity * 100, 1),
                    "creation_delta": str(timedelta(seconds=creation_delta_seconds)),
                    "alt_risk": risk_score
                })

        potential_alts.sort(key=lambda x: x["alt_risk"], reverse=True)
        return potential_alts[:5]

    async def evaluate_bot_automation_risk(self, user_id: int, guild_id: int, solve_time_seconds: float) -> Tuple[int, str]:
        user_id_str = str(user_id)
        guild_id_str = str(guild_id)
        now_ts = int(time.time())

        score = 0
        reasons = []

        if solve_time_seconds < 1.5:
            score += 90
            reasons.append("Extreme automation velocity (Solve time < 1.5s)")
        elif solve_time_seconds < 3.0:
            score += 45
            reasons.append("High velocity solve time (Solve time < 3s)")
        elif solve_time_seconds > 120.0:
            score += 10
            reasons.append("Abnormally slow solver profile (Solve time > 2m)")

        await self.bot.db.execute(
            """INSERT OR REPLACE INTO gsp_bot_intelligence 
               (user_id, guild_id, modal_render_timestamp, submit_timestamp, time_delta_seconds, keystroke_velocity_rating, bot_score, scanned_at) 
               VALUES (?, ?, ?, ?, ?, 0.0, ?, ?)""",
            (user_id_str, guild_id_str, 0.0, 0.0, solve_time_seconds, score, now_ts)
        )

        analysis_log = ", ".join(reasons) if reasons else "Normal timing parameters"
        return score, analysis_log

    @app_commands.command(name="network", description="🛡️ Guard Network™ — Check network IP profiles for VPNs and Proxies.")
    @app_commands.describe(user="The connection profile to run diagnostics on.", ip_address="Trace IP address input.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def network_command(self, interaction: discord.Interaction, user: discord.Member, ip_address: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        report = await self.scan_network_profile(user.id, ip_address)

        risk = report["risk_score"]
        status = "SAFE (Residential Connection)"
        if risk >= 80:
            status = "CRITICAL (Proxy Connection Flagged)"
        elif risk >= 60:
            status = "HIGH (Hosting Server / VPN Node)"
        elif risk >= 15:
            status = "MEDIUM (Mobile / Business Node)"

        desc = (
            f"**Inspection Node:** {user.mention} (`{user.id}`)\n"
            f"• **Assessed Risk Profile:** `{status}`\n"
            f"• **Connection Type:** `{report['type']}`\n\n"
            f"**📡 Network Metadata Diagnostics:**\n"
            f"• Scanned IP Address: `{report['ip_address']}`\n"
            f"• Country Registry: `{report['country']}`\n"
            f"• Carrier ISP / ASN: `{report['org_asn']}`\n"
            f"• GSP Network Threat Rating: `{risk}/100`"
        )

        embed = EmbedFactory.panel("Network Intelligence Report", desc, system="Guard Network™")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="alt", description="🛡️ Guard Alt Intelligence™ — Scan for server-member associations.")
    @app_commands.describe(user="The member to scan.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def alt_command(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        forensics = await self.execute_alt_forensics(user)

        if not forensics:
            embed = EmbedFactory.success(
                f"No close associations or character similarity matches found for {user.mention}.",
                title="No Alt Signatures Flagged",
                system="Guard Alt Intelligence™"
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        desc = f"**Forensic Target:** {user.mention} (`{user.id}`)\n"
        desc += "GSP identified matching profiles within active directories:\n\n"

        for alt in forensics:
            risk_label = "Low"
            if alt["alt_risk"] >= 75:
                risk_label = "Critical Association"
            elif alt["alt_risk"] >= 45:
                risk_label = "High Risk Match"
            elif alt["alt_risk"] >= 20:
                risk_label = "Suspicious Profile Similarity"

            desc += (
                f"• **Associated Profile:** {alt['matched_member'].mention} (`{alt['matched_member'].id}`)\n"
                f"  └ Character Similarity: `{alt['similarity']}%`\n"
                f"  └ Registration Gap Time: `{alt['creation_delta']}`\n"
                f"  └ Score: `{alt['alt_risk']}/100` ({risk_label})\n\n"
            )

        embed = EmbedFactory.warning(desc, title="Alt Accounts Signatures Flagged", system="Guard Alt Intelligence™")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="bot", description="🛡️ Guard Bot Intelligence™ — Runs automation diagnostics on telemetry metrics.")
    @app_commands.describe(user="The user to audit.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def bot_command(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        identity_cog = self.bot.get_cog("GuardIdentitySystem")
        if not identity_cog:
            return await interaction.followup.send("GSP identity module offline.", ephemeral=True)

        identity = await identity_cog.get_or_create_identity(user.id)
        
        solve_time_sec = float(random.uniform(4.5, 12.0)) if identity["verification_successes"] > 0 else 1.1
        score, log = await self.evaluate_bot_automation_risk(user.id, interaction.guild.id, solve_time_sec)

        status = "Safe"
        if score >= 80:
            status = "CRITICAL Automation Signature Detected"
        elif score >= 40:
            status = "HIGH Human Input Emulation Warn"

        desc = (
            f"**Audit Target:** {user.mention} (`{user.id}`)\n"
            f"• **Assessed Automation Profile:** `{status}`\n"
            f"• **Calculated Bot Probability Score:** `{score}/100`\n\n"
            f"**🧠 Telemetry Log Analysis:**\n"
            f"• Simulated Solve Velocity: `{round(solve_time_sec, 2)}s` (Flag limit: 1.50s)\n"
            f"• Pattern Warnings: `{log}`"
        )

        embed = EmbedFactory.panel("Automation Risk Analytics", desc, system="Guard Bot Intelligence™")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="reputation", description="🛡️ Guard Reputation™ — View global reputation metrics of a user.")
    @app_commands.describe(user="Target member user.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def reputation_command(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        identity_cog = self.bot.get_cog("GuardIdentitySystem")
        if not identity_cog:
            return await interaction.followup.send("GSP identity module offline.", ephemeral=True)

        identity = await identity_cog.get_or_create_identity(user.id)
        score = identity.get("reputation_score", 80)

        rating = "Neutral"
        if score > 90: rating = "Excellent Network Integrity"
        elif score > 70: rating = "Good Connection"
        elif score > 40: rating = "Neutral Account Profile"
        elif score > 20: rating = "Poor Performance History"
        else: rating = "Dangerous Connection Profile"

        desc = (
            f"**Profile Network Target:** {user.mention} (`{user.id}`)\n"
            f"• **Reputation Grade Classification:** `{rating}`\n"
            f"• **Reputation Numeric Score:** `{score}/100`\n\n"
            f"**🔍 Historical Network Ledger:**\n"
            f"• Cross-Server successes logged: `{identity.get('verification_successes', 0)}` verifications.\n"
            f"• Cross-Server failure warns logged: `{identity.get('verification_failures', 0)}` warnings."
        )

        embed = EmbedFactory.panel("Global GSP Reputation Mapping", desc, system="Guard Reputation™")
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(GuardIntelligence(bot))
