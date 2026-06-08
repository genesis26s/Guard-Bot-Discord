import discord
from discord.ext import commands
from discord import app_commands
import random
import time
from utils.embeds import EmbedFactory

class EditLevelUpMessageModal(discord.ui.Modal, title="Level-Up Message Config"):
    template = discord.ui.TextInput(
        label="Message template:",
        style=discord.TextStyle.paragraph,
        placeholder="🎉 {user} has reached Level {newlevel} from Level {oldlevel}!",
        default="🎉 {user} has advanced to **Level {newlevel}**!",
        min_length=5,
        max_length=500,
        required=True
    )
    color_hex = discord.ui.TextInput(
        label="Embed Color Hex Code (e.g. #00FF00):",
        placeholder="#00FF00",
        default="#00FF00",
        min_length=7,
        max_length=7,
        required=False
    )

    def __init__(self, bot, guild_id: str):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        color_clean = self.color_hex.value.replace("#", "")
        try:
            color_int = int(color_clean, 16)
        except ValueError:
            color_int = 65280

        await self.bot.db.execute(
            """INSERT INTO guild_level_settings (guild_id, msg_template, msg_color) 
               VALUES (?, ?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET msg_template=?, msg_color=?""",
            (self.guild_id, self.template.value, str(color_int), self.template.value, str(color_int))
        )

        await interaction.followup.send(
            embed=EmbedFactory.success("Successfully updated level-up message template parameters!", system="Guard Levels™"),
            ephemeral=True
        )


class AddRewardRoleSelect(discord.ui.RoleSelect):
    def __init__(self, bot, guild_id: str, level: int):
        self.bot = bot
        self.guild_id = guild_id
        self.level = level
        super().__init__(placeholder="Select the role to award...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        role = self.values[0]

        await self.bot.db.execute(
            "INSERT OR REPLACE INTO level_rewards (guild_id, level, role_id) VALUES (?, ?, ?)",
            (self.guild_id, self.level, str(role.id))
        )
        await interaction.followup.send(
            embed=EmbedFactory.success(f"Configured **{role.name}** as a milestone reward role for **Level {self.level}**!", system="Guard Levels™"),
            ephemeral=True
        )


class AddRewardModal(discord.ui.Modal, title="Add Level Milestone Role"):
    level_num = discord.ui.TextInput(
        label="Trigger Level:",
        placeholder="10",
        min_length=1,
        max_length=3,
        required=True
    )

    def __init__(self, bot, guild_id: str):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            lvl = int(self.level_num.value)
        except ValueError:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Invalid input. Trigger Level must be a raw number.", system="Guard Levels™"),
                ephemeral=True
            )

        role_select = AddRewardRoleSelect(self.bot, self.guild_id, lvl)
        view = discord.ui.View().add_item(role_select)
        await interaction.response.send_message(
            "Select the role you want members to receive at this level:",
            view=view,
            ephemeral=True
        )


class RemoveRewardDropdown(discord.ui.Select):
    def __init__(self, bot, guild_id: str, rewards: list):
        self.bot = bot
        self.guild_id = guild_id
        options = []
        for r in rewards:
            options.append(discord.SelectOption(
                label=f"Level {r['level']}", 
                value=str(r["level"]), 
                description=f"Removes reward role ID: {r['role_id']}"
            ))
        super().__init__(placeholder="Select a reward level to remove...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        level_to_rem = int(self.values[0])
        
        await self.bot.db.execute(
            "DELETE FROM level_rewards WHERE guild_id = ? AND level = ?", 
            (self.guild_id, level_to_rem)
        )
        await interaction.followup.send(
            embed=EmbedFactory.success(f"Deleted level-up role reward configuration for Level **{level_to_rem}**.", system="Guard Levels™"),
            ephemeral=True
        )


class LevelSystemAdminPanel(discord.ui.View):
    def __init__(self, bot, guild_id: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="Toggle Msg Type", style=discord.ButtonStyle.primary, emoji="🔄", row=0)
    async def toggle_msg_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        row = await self.bot.db.select_row("SELECT msg_type FROM guild_level_settings WHERE guild_id = ?", (self.guild_id,))
        settings = dict(row) if row else {}
        current_type = settings.get("msg_type", "text")
        new_type = "embed" if current_type == "text" else "text"

        await self.bot.db.execute(
            """INSERT INTO guild_level_settings (guild_id, msg_type) 
               VALUES (?, ?) 
               ON CONFLICT(guild_id) DO UPDATE SET msg_type = ?""",
            (self.guild_id, new_type, new_type)
        )
        await interaction.followup.send(
            embed=EmbedFactory.success(f"Level-up notification style changed to: **{new_type.upper()}**", system="Guard Levels™"),
            ephemeral=True
        )

    @discord.ui.button(label="Edit Template", style=discord.ButtonStyle.primary, emoji="📝", row=0)
    async def edit_msg(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditLevelUpMessageModal(self.bot, self.guild_id))

    @discord.ui.button(label="Add Reward Role", style=discord.ButtonStyle.success, emoji="🏆", row=1)
    async def add_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddRewardModal(self.bot, self.guild_id))

    @discord.ui.button(label="Remove Reward Role", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def remove_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        rewards_rows = await self.bot.db.execute("SELECT level, role_id FROM level_rewards WHERE guild_id = ?", (self.guild_id,))
        rewards = [{"level": r[0], "role_id": r[1]} for r in rewards_rows]

        if not rewards:
            return await interaction.response.send_message(
                embed=EmbedFactory.warning("You have no level milestone rewards configured yet.", system="Guard Levels™"),
                ephemeral=True
            )

        view = discord.ui.View().add_item(RemoveRewardDropdown(self.bot, self.guild_id, rewards))
        await interaction.response.send_message("Choose which level reward milestone to remove:", view=view, ephemeral=True)


class LevelSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    def _xp_needed(self, level: int) -> int:
        return int(100 * ((level + 1) ** 1.5))

    def _replace_placeholders(self, text: str, member: discord.Member, new_lvl: int, old_lvl: int) -> str:
        if not text:
            return ""
        return text.replace("{user}", member.mention)\
                   .replace("{username}", member.name)\
                   .replace("{newlevel}", str(new_lvl))\
                   .replace("{oldlevel}", str(old_lvl))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        user_id = str(message.author.id)

        settings_row = await self.bot.db.select_row("SELECT levels_enabled, msg_type, msg_template, msg_color FROM guild_level_settings WHERE guild_id = ?", (guild_id,))
        settings = dict(settings_row) if settings_row else {}
        if settings.get("levels_enabled", 1) == 0:
            return

        now = time.time()
        last_earned = self.cooldowns.get((guild_id, user_id), 0)
        if now - last_earned < 60:
            return

        self.cooldowns[(guild_id, user_id)] = now

        profile = await self.bot.db.select_row(
            "SELECT xp, level FROM users_levels WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )

        if not profile:
            xp = random.randint(15, 25)
            level = 0
            await self.bot.db.execute(
                "INSERT INTO users_levels (guild_id, user_id, xp, level) VALUES (?, ?, ?, ?)",
                (guild_id, user_id, xp, level)
            )
        else:
            xp = profile["xp"] + random.randint(15, 25)
            level = profile["level"]
            needed = self._xp_needed(level)

            if xp >= needed:
                xp -= needed
                old_level = level
                level += 1
                
                msg_template = settings.get("msg_template") or "🎉 {user} has advanced to **Level {newlevel}**!"
                parsed_msg = self._replace_placeholders(msg_template, message.author, level, old_level)

                if settings.get("msg_type", "text") == "embed":
                    try:
                        color_val = int(settings.get("msg_color", "65280"))
                    except ValueError:
                        color_val = 65280
                    
                    embed = discord.Embed(
                        description=parsed_msg,
                        color=discord.Color(color_val)
                    )
                    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
                    await message.channel.send(embed=embed)
                else:
                    await message.channel.send(parsed_msg)

                reward = await self.bot.db.select_row(
                    "SELECT role_id FROM level_rewards WHERE guild_id = ? AND level = ?",
                    (guild_id, level)
                )
                if reward:
                    role = message.guild.get_role(int(reward["role_id"]))
                    if role:
                        try:
                            await message.author.add_roles(role, reason=f"Level milestone {level} reached.")
                            await message.channel.send(f"🏆 {message.author.mention} was granted the **{role.name}** role!")
                        except discord.Forbidden:
                            pass

            await self.bot.db.execute(
                "UPDATE users_levels SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?",
                (xp, level, guild_id, user_id)
            )

    @app_commands.command(name="rank", description="Check your current level, XP, and rank progress.")
    async def view_rank(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        guild_id = str(interaction.guild.id)
        user_id = str(target.id)

        settings_row = await self.bot.db.select_row("SELECT levels_enabled FROM guild_level_settings WHERE guild_id = ?", (guild_id,))
        settings = dict(settings_row) if settings_row else {}
        if settings.get("levels_enabled", 1) == 0:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Leveling is currently disabled on this server.", system="Guard Levels™"),
                ephemeral=True
            )

        profile = await self.bot.db.select_row(
            "SELECT xp, level FROM users_levels WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )

        if not profile:
            return await interaction.response.send_message(
                embed=EmbedFactory.info(f"{target.mention} hasn't earned any XP yet.")
            )

        xp = profile["xp"]
        lvl = profile["level"]
        needed = self._xp_needed(lvl)

        embed = discord.Embed(title=f"⭐ Rank details for {target}", color=discord.Color.gold())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Current Level", value=f"🏆 `{lvl}`", inline=True)
        embed.add_field(name="XP Progress", value=f"✨ `{xp}` / `{needed} XP`", inline=True)
        
        progress = int((xp / max(needed, 1)) * 10)
        bar = "🟩" * progress + "⬜" * (10 - progress)
        embed.add_field(name="Progression Tracker", value=bar, inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="View the highest level users on this server.")
    async def leaderboard(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        settings_row = await self.bot.db.select_row("SELECT levels_enabled FROM guild_level_settings WHERE guild_id = ?", (guild_id,))
        settings = dict(settings_row) if settings_row else {}
        if settings.get("levels_enabled", 1) == 0:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Leveling is currently disabled on this server.", system="Guard Levels™"),
                ephemeral=True
            )

        rows = await self.bot.db.execute(
            "SELECT user_id, xp, level FROM users_levels WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10",
            (guild_id,)
        )

        if not rows:
            return await interaction.response.send_message("The leaderboard is completely empty.")

        embed = discord.Embed(title=f"🏆 Top 10 Server Levels: {interaction.guild.name}", color=discord.Color.blurple())
        
        desc = ""
        for index, row in enumerate(rows, start=1):
            user = interaction.guild.get_member(int(row[0]))
            user_name = user.name if user else f"User {row[0]}"
            desc += f"**#{index}** {user_name} • Level `{row[2]}` (XP: `{row[1]}`)\n"

        embed.description = desc
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="level-toggle", description="Quickly turn the server text leveling system ON or OFF.")
    @app_commands.choices(status=[
        app_commands.Choice(name="Turn On", value=1),
        app_commands.Choice(name="Turn Off", value=0)
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def level_toggle(self, interaction: discord.Interaction, status: app_commands.Choice[int]):
        guild_id = str(interaction.guild.id)
        
        await self.bot.db.execute(
            """INSERT INTO guild_level_settings (guild_id, levels_enabled) 
               VALUES (?, ?) 
               ON CONFLICT(guild_id) DO UPDATE SET levels_enabled = ?""",
            (guild_id, status.value, status.value)
        )
        word = "enabled" if status.value == 1 else "disabled"
        await interaction.response.send_message(
            embed=EmbedFactory.success(f"Leveling and XP gain algorithms have been successfully **{word}** globally.", system="Guard Levels™")
        )

    @app_commands.command(name="level-panel", description="Open the main administrative dashboard panel to configure leveling settings.")
    @app_commands.checks.has_permissions(administrator=True)
    async def level_panel(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)

        settings_row = await self.bot.db.select_row("SELECT * FROM guild_level_settings WHERE guild_id = ?", (guild_id,))
        settings = dict(settings_row) if settings_row else {}

        rewards_rows = await self.bot.db.execute("SELECT level, role_id FROM level_rewards WHERE guild_id = ?", (guild_id,))
        rewards_list = [f"• Level **{r[0]}** reward: <@&{r[1]}>" for r in rewards_rows]
        rewards_str = "\n".join(rewards_list) if rewards_list else "*No active level role rewards*"

        status_flag = "🟢 Active & Enabled" if settings.get("levels_enabled", 1) == 1 else "🔴 Disabled"
        msg_style = f"`{settings.get('msg_type', 'text').upper()}`"
        msg_template = f"```\n{settings.get('msg_template', '🎉 {user} has advanced to **Level {newlevel}**!')}\n```"

        embed = discord.Embed(
            title="⭐ Leveling System Management Dashboard",
            description=(
                "Use the interactive dashboard buttons below to configure your text leveling settings.\n\n"
                f"**📡 System Status:** {status_flag}\n"
                f"**⚙️ Level-Up Style:** {msg_style}\n\n"
                f"**📝 Notification Template:**\n{msg_template}\n"
                f"**🏆 Active Role Rewards:**\n{rewards_str}"
            ),
            color=EmbedFactory.COLOR_GSP_CYAN
        )
        view = LevelSystemAdminPanel(self.bot, guild_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(LevelSystem(bot))
