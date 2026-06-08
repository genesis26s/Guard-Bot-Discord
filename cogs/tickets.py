import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import io
import time
from datetime import datetime
from utils.embeds import EmbedFactory

CREATING_USERS = set()

class TicketCategorySelect(discord.ui.Select):
    def __init__(self, bot, categories: list):
        self.bot = bot
        options = []
        if not categories:
            options.append(discord.SelectOption(
                label="General Support", 
                value="general", 
                description="Get assistance from our staff team.", 
                emoji="✉️"
            ))
        else:
            for cat in categories:
                raw_emoji = cat.get("emoji") or "🎫"
                is_url = raw_emoji.startswith("http")
                emoji_val = "🎫" if is_url else raw_emoji
                
                options.append(discord.SelectOption(
                    label=cat["label"],
                    value=cat["category_key"],
                    description=cat.get("description", "Open a request under this category"),
                    emoji=emoji_val
                ))
                
        super().__init__(
            placeholder="Select a ticket type...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="guardbot_ticket_cat_selector"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        category_key = self.values[0]

        if user_id in CREATING_USERS:
            return await interaction.followup.send(
                embed=EmbedFactory.error("Please wait! Your ticket is already being created.", system="Guard Tickets™"),
                ephemeral=True
            )

        CREATING_USERS.add(user_id)

        try:
            settings_row = await self.bot.db.select_row(
                "SELECT ticket_limit, category_id, support_role_ids FROM ticket_settings WHERE guild_id = ?",
                (str(guild_id),)
            )
            settings = dict(settings_row) if settings_row else {}
            ticket_limit = settings.get("ticket_limit", 1)
            category_parent_id = settings.get("category_id")

            active_count = await self.bot.db.select_row(
                "SELECT COUNT(*) as count FROM tickets WHERE guild_id = ? AND user_id = ? AND status = 'open'",
                (str(guild_id), str(user_id))
            )
            if active_count and active_count["count"] >= ticket_limit:
                CREATING_USERS.remove(user_id)
                return await interaction.followup.send(
                    embed=EmbedFactory.error(f"You already have {active_count['count']} open ticket(s). Close them before opening a new one!", system="Guard Tickets™"),
                    ephemeral=True
                )

            cat_info_row = await self.bot.db.select_row(
                "SELECT * FROM ticket_categories WHERE guild_id = ? AND category_key = ?",
                (str(guild_id), category_key)
            )
            cat_info = dict(cat_info_row) if cat_info_row else {}
            prefix = cat_info.get("prefix", "ticket")
            role_id = cat_info.get("role_id")

            parent_category = None
            if category_parent_id:
                parent_category = interaction.guild.get_channel(int(category_parent_id))

            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True
                ),
                interaction.guild.me: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, manage_channels=True, manage_permissions=True, attach_files=True, embed_links=True
                )
            }

            if settings.get("support_role_ids"):
                for r_id in settings["support_role_ids"].split(","):
                    if r_id.strip():
                        s_role = interaction.guild.get_role(int(r_id))
                        if s_role:
                            overwrites[s_role] = discord.PermissionOverwrite(
                                view_channel=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True
                            )

            if role_id:
                cat_role = interaction.guild.get_role(int(role_id))
                if cat_role:
                    overwrites[cat_role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True
                    )

            chan_name = f"{prefix}-{interaction.user.name.lower()}"
            ticket_channel = await interaction.guild.create_text_channel(
                name=chan_name,
                category=parent_category,
                overwrites=overwrites,
                reason=f"GuardBot Ticket System initiated by {interaction.user}"
            )

            await self.bot.db.execute(
                "INSERT INTO tickets (channel_id, guild_id, user_id, category_key, status) VALUES (?, ?, ?, ?, 'open')",
                (str(ticket_channel.id), str(guild_id), str(user_id), category_key)
            )

            embed = discord.Embed(
                title=f"🎫 {cat_info.get('label', 'Support Request')}",
                description=(
                    f"Welcome to your ticket, {interaction.user.mention}!\n"
                    "Our support staff has been alerted and will assist you shortly.\n\n"
                    "**How to get help:**\n"
                    "• Describe your issue in detail.\n"
                    "• Upload screenshots or relevant files right here.\n"
                    "• Avoid pinging staff repeatedly."
                ),
                color=EmbedFactory.COLOR_GSP_CYAN
            )
            if cat_info.get("emoji") and cat_info["emoji"].startswith("http"):
                embed.set_thumbnail(url=cat_info["emoji"])

            embed.add_field(name="Ticket Creator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Category", value=category_key.upper(), inline=True)
            embed.add_field(name="Priority Status", value="Medium", inline=True)

            control_panel = TicketActionControlPanel(self.bot)
            await ticket_channel.send(content=interaction.user.mention, embed=embed, view=control_panel)

            await interaction.followup.send(
                embed=EmbedFactory.success(f"Ticket opened successfully in {ticket_channel.mention}!", system="Guard Tickets™"),
                ephemeral=True
            )

            logging_cog = self.bot.get_cog("LoggingSystem")
            if logging_cog:
                log_embed = EmbedFactory.info(
                    f"🎫 Ticket created by {interaction.user.mention} ({interaction.user.id}) in {ticket_channel.mention}.",
                    title="Support Ticket Activity"
                )
                await logging_cog._send_log(interaction.guild, "log_tickets", log_embed)

        except Exception as e:
            await interaction.followup.send(
                embed=EmbedFactory.error(f"Failed to create ticket: {e}", system="Guard Tickets™"),
                ephemeral=True
            )
        finally:
            CREATING_USERS.discard(user_id)


class TicketPersistentPanel(discord.ui.View):
    def __init__(self, bot, categories: list):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect(bot, categories))


class TicketActionControlPanel(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Lock & Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="guardbot_btn_close_t")
    async def btn_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = EmbedFactory.warning("Are you sure you want to finalize and archive this support channel context?", system="Guard Tickets™")
        view = TicketCloseConfirmPanel(self.bot)
        await interaction.followup.send(embed=embed, view=view)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, emoji="🙋", custom_id="guardbot_btn_claim_t")
    async def btn_claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        chan_id = str(interaction.channel.id)
        settings_row = await self.bot.db.select_row("SELECT support_role_ids FROM ticket_settings WHERE guild_id = ?", (str(interaction.guild.id),))
        settings = dict(settings_row) if settings_row else {}
        has_access = False
        if interaction.user.guild_permissions.administrator:
            has_access = True
        elif settings.get("support_role_ids"):
            for r_id in settings["support_role_ids"].split(","):
                if r_id.strip() and interaction.guild.get_role(int(r_id)) in interaction.user.roles:
                    has_access = True
                    break

        if not has_access:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("You are not registered as part of our support staff.", system="Guard Tickets™"),
                ephemeral=True
            )

        await self.bot.db.execute("UPDATE tickets SET claimed_by = ? WHERE channel_id = ?", (str(interaction.user.id), chan_id))
        await interaction.channel.edit(topic=f"Claimed by Support Agent: {interaction.user}")
        await interaction.response.send_message(
            embed=EmbedFactory.success(f"This support request has been claimed by {interaction.user.mention} and is now locked to their active queue.", system="Guard Tickets™")
        )


class TicketCloseConfirmPanel(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot

    @discord.ui.button(label="Confirm Closure", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        chan = interaction.channel
        guild_id = str(interaction.guild.id)

        await chan.send("Creating transcript secure export records...")
        transcript_data = await self.generate_transcript_stream(chan)
        
        settings_row = await self.bot.db.select_row("SELECT transcript_channel_id FROM ticket_settings WHERE guild_id = ?", (guild_id,))
        settings = dict(settings_row) if settings_row else {}
        t_chan = None
        if settings.get("transcript_channel_id"):
            t_chan = interaction.guild.get_channel(int(settings["transcript_channel_id"]))

        if t_chan and transcript_data:
            file = discord.File(transcript_data, filename=f"transcript-{chan.name}.html")
            embed = EmbedFactory.info(
                f"**Ticket Name:** `{chan.name}`\n"
                f"**Closed By:** {interaction.user.mention}\n"
                f"**Closing Date:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                title="Support Channel Transcript Archived"
            )
            await t_chan.send(embed=embed, file=file)

        await self.bot.db.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (str(chan.id),))
        await chan.send("Deconstructing environment. Channel will delete in 5 seconds...")
        await asyncio.sleep(5)
        try:
            await chan.delete()
        except discord.NotFound:
            pass

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closure aborted. Returning to operational state.", ephemeral=True)
        await interaction.message.delete()

    async def generate_transcript_stream(self, channel):
        messages = []
        async for m in channel.history(limit=None, oldest_first=True):
            messages.append(m)

        if not messages:
            return None

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ background: #2f3136; color: #dcddde; font-family: sans-serif; padding: 20px; }}
                .msg {{ display: flex; margin-bottom: 15px; border-bottom: 1px solid #40444b; padding-bottom: 10px; }}
                .avatar {{ width: 40px; height: 40px; border-radius: 50%; margin-right: 15px; }}
                .user {{ font-weight: bold; color: #fff; margin-bottom: 5px; }}
                .time {{ font-size: 0.8em; color: #72767d; margin-left: 10px; }}
                .content {{ font-size: 0.95em; line-height: 1.4; }}
                .attachment {{ margin-top: 10px; }}
                .attachment img {{ max-width: 300px; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <h2>Support Ticket Transcript Records: #{channel.name}</h2>
            <hr style="border-color: #40444b;">
        """

        for msg in messages:
            avatar_url = msg.author.display_avatar.url
            clean_content = msg.clean_content.replace("<", "&lt;").replace(">", "&gt;")
            time_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            
            html += f"""
            <div class="msg">
                <img class="avatar" src="{avatar_url}">
                <div>
                    <span class="user">{msg.author}</span>
                    <span class="time">{time_str}</span>
                    <div class="content">{clean_content}</div>
            """
            
            for attach in msg.attachments:
                if attach.content_type and attach.content_type.startswith("image/"):
                    html += f'<div class="attachment"><img src="{attach.url}"></div>'
                else:
                    html += f'<div class="attachment"><a style="color: #00b0f4;" href="{attach.url}">Attachment Link ({attach.filename})</a></div>'
                    
            html += """
                </div>
            </div>
            """

        html += "</body></html>"
        stream = io.BytesIO(html.encode("utf-8"))
        stream.seek(0)
        return stream


class AddCategoryModal(discord.ui.Modal, title="Add Ticket Category"):
    key = discord.ui.TextInput(label="Category Key (Unique, e.g. general)", placeholder="general", min_length=2, max_length=15, required=True)
    label = discord.ui.TextInput(label="Category Label", placeholder="League support", min_length=2, max_length=30, required=True)
    description = discord.ui.TextInput(label="Category Description", placeholder="Use this if you need general help...", min_length=2, max_length=100, required=True)
    prefix = discord.ui.TextInput(label="Prefix for ticket channels", placeholder="ticket-", min_length=1, max_length=10, required=True)
    emoji = discord.ui.TextInput(label="Emoji Unicode or direct Image Link", placeholder="⁉️", required=True)

    def __init__(self, bot, guild_id: str):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        role_select = discord.ui.RoleSelect(placeholder="Select specific support role notification target...", min_values=1, max_values=1)
        
        async def select_callback(inter: discord.Interaction):
            chosen_role = role_select.values[0]
            await inter.response.defer(ephemeral=True)
            
            await self.bot.db.execute(
                """INSERT INTO ticket_categories (category_key, guild_id, label, emoji, description, role_id, prefix) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(guild_id, category_key) DO UPDATE SET 
                   label=?, emoji=?, description=?, role_id=?, prefix=?""",
                (self.key.value.strip().lower(), self.guild_id, self.label.value.strip(), self.emoji.value.strip(), self.description.value.strip(), str(chosen_role.id), self.prefix.value.strip().lower(),
                 self.label.value.strip(), self.emoji.value.strip(), self.description.value.strip(), str(chosen_role.id), self.prefix.value.strip().lower())
            )
            await inter.followup.send(
                embed=EmbedFactory.success(f"Successfully configured Category: **{self.label.value}** under notification role {chosen_role.mention}!", system="Guard Tickets™"),
                ephemeral=True
            )

        role_select.callback = select_callback
        view = discord.ui.View().add_item(role_select)
        await interaction.followup.send("Excellent. Choose which support role gets access to this new category channel:", view=view, ephemeral=True)


class RemoveCategoryDropdown(discord.ui.Select):
    def __init__(self, bot, guild_id: str, categories: list):
        self.bot = bot
        self.guild_id = guild_id
        options = []
        for cat in categories:
            options.append(discord.SelectOption(label=cat["label"], value=cat["category_key"], description=f"Key: {cat['category_key']}"))
        super().__init__(placeholder="Select category to delete...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        key = self.values[0]
        await self.bot.db.execute("DELETE FROM ticket_categories WHERE guild_id = ? AND category_key = ?", (self.guild_id, key))
        await interaction.followup.send(embed=EmbedFactory.success(f"Removed ticket category `{key}` successfully!", system="Guard Tickets™"), ephemeral=True)


class SetLimitModal(discord.ui.Modal, title="Set Ticket Limit"):
    limit = discord.ui.TextInput(label="Max active tickets allowed per user:", placeholder="1", default="1", min_length=1, max_length=2, required=True)

    def __init__(self, bot, guild_id: str):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        limit_val = 1
        try:
            limit_val = int(self.limit.value)
        except ValueError:
            pass

        row = await self.bot.db.select_row("SELECT * FROM ticket_settings WHERE guild_id = ?", (self.guild_id,))
        curr = dict(row) if row else {}
        if not row:
            await self.bot.db.execute("INSERT OR IGNORE INTO ticket_settings (guild_id) VALUES (?)", (self.guild_id,))

        await self.bot.db.execute(
            """INSERT OR REPLACE INTO ticket_settings (guild_id, support_role_ids, category_id, transcript_channel_id, ticket_limit)
               VALUES (?, ?, ?, ?, ?)""",
            (self.guild_id, curr.get("support_role_ids"), curr.get("category_id"), curr.get("transcript_channel_id"), limit_val)
        )
        await interaction.followup.send(embed=EmbedFactory.success(f"User ticket limit set to **{limit_val}**.", system="Guard Tickets™"), ephemeral=True)


class TicketAdminPanelControlView(discord.ui.View):
    def __init__(self, bot, guild_id: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="Add Category", style=discord.ButtonStyle.primary, emoji="➕", row=0)
    async def add_cat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddCategoryModal(self.bot, self.guild_id))

    @discord.ui.button(label="Remove Category", style=discord.ButtonStyle.danger, emoji="➖", row=0)
    async def rem_cat(self, interaction: discord.Interaction, button: discord.ui.Button):
        categories_rows = await self.bot.db.execute("SELECT category_key, label FROM ticket_categories WHERE guild_id = ?", (self.guild_id,))
        categories = [{"category_key": r[0], "label": r[1]} for r in categories_rows]
        
        if not categories:
            return await interaction.response.send_message(embed=EmbedFactory.warning("You have no custom categories to remove.", system="Guard Tickets™"), ephemeral=True)
            
        view = discord.ui.View().add_item(RemoveCategoryDropdown(self.bot, self.guild_id, categories))
        await interaction.response.send_message("Choose which category to delete:", view=view, ephemeral=True)

    @discord.ui.button(label="Set Category Parent", style=discord.ButtonStyle.secondary, emoji="📁", row=1)
    async def set_parent(self, interaction: discord.Interaction, button: discord.ui.Button):
        select = discord.ui.ChannelSelect(placeholder="Select category folder target...", channel_types=[discord.ChannelType.category])
        
        async def select_callback(inter: discord.Interaction):
            chosen_cat = select.values[0]
            await inter.response.defer(ephemeral=True)
            
            row = await self.bot.db.select_row("SELECT * FROM ticket_settings WHERE guild_id = ?", (self.guild_id,))
            curr = dict(row) if row else {}
            if not row:
                await self.bot.db.execute("INSERT OR IGNORE INTO ticket_settings (guild_id) VALUES (?)", (self.guild_id,))

            await self.bot.db.execute(
                """INSERT OR REPLACE INTO ticket_settings (guild_id, support_role_ids, category_id, transcript_channel_id, ticket_limit)
                   VALUES (?, ?, ?, ?, ?)""",
                (self.guild_id, curr.get("support_role_ids"), str(chosen_cat.id), curr.get("transcript_channel_id"), curr.get("ticket_limit", 1))
            )
            await inter.followup.send(embed=EmbedFactory.success(f"Ticket channels will now open inside category: **{chosen_cat.name}**!", system="Guard Tickets™"), ephemeral=True)

        select.callback = select_callback
        view = discord.ui.View().add_item(select)
        await interaction.response.send_message("Choose the parent category below:", view=view, ephemeral=True)

    @discord.ui.button(label="Set Transcripts Channel", style=discord.ButtonStyle.secondary, emoji="📝", row=1)
    async def set_transcripts(self, interaction: discord.Interaction, button: discord.ui.Button):
        select = discord.ui.ChannelSelect(placeholder="Select transcripts log destination...", channel_types=[discord.ChannelType.text])
        
        async def select_callback(inter: discord.Interaction):
            chosen_chan = select.values[0]
            await inter.response.defer(ephemeral=True)
            
            row = await self.bot.db.select_row("SELECT * FROM ticket_settings WHERE guild_id = ?", (self.guild_id,))
            curr = dict(row) if row else {}
            if not row:
                await self.bot.db.execute("INSERT OR IGNORE INTO ticket_settings (guild_id) VALUES (?)", (self.guild_id,))

            await self.bot.db.execute(
                """INSERT OR REPLACE INTO ticket_settings (guild_id, support_role_ids, category_id, transcript_channel_id, ticket_limit)
                   VALUES (?, ?, ?, ?, ?)""",
                (self.guild_id, curr.get("support_role_ids"), curr.get("category_id"), str(chosen_chan.id), curr.get("ticket_limit", 1))
            )
            await inter.followup.send(embed=EmbedFactory.success(f"Transcripts will now log automatically in {chosen_chan.mention}!", system="Guard Tickets™"), ephemeral=True)

        select.callback = select_callback
        view = discord.ui.View().add_item(select)
        await interaction.response.send_message("Choose the transcripts destination below:", view=view, ephemeral=True)

    @discord.ui.button(label="User Ticket Limit", style=discord.ButtonStyle.secondary, emoji="🔢", row=1)
    async def set_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SetLimitModal(self.bot, self.guild_id))


class TicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(TicketActionControlPanel(self.bot))
        
        categories = await self.bot.db.execute("SELECT * FROM ticket_categories")
        guild_cats = {}
        for row in categories:
            g_id = row[1]
            if g_id not in guild_cats:
                guild_cats[g_id] = []
            guild_cats[g_id].append({
                "category_key": row[0],
                "label": row[2],
                "emoji": row[3],
                "description": row[4],
                "role_id": row[5],
                "prefix": row[6]
            })

        for g_id, cats in guild_cats.items():
            self.bot.add_view(TicketPersistentPanel(self.bot, cats))

    @app_commands.command(name="setup_tickets", description="Post the persistent support dropdown panel in this channel.")
    @app_commands.describe(banner_url="Include a banner image URL for your support hub panel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction, banner_url: str = None):
        guild_id = str(interaction.guild.id)
        
        categories_rows = await self.bot.db.execute(
            "SELECT * FROM ticket_categories WHERE guild_id = ?",
            (guild_id,)
        )
        
        categories = []
        for r in categories_rows:
            categories.append({
                "category_key": r[0],
                "label": r[2],
                "emoji": r[3],
                "description": r[4],
                "role_id": r[5],
                "prefix": r[6]
            })

        if not categories:
            return await interaction.response.send_message(
                embed=EmbedFactory.warning("You have no ticket categories configured yet! Run `/ticket_panel` to create your first category.", system="Guard Tickets™"),
                ephemeral=True
            )

        embed = discord.Embed(
            title="📨 Contact Support Centre",
            description=(
                "Need help? Select the category matching your request from the dropdown below.\n"
                "A secure private channel will be opened instantly."
            ),
            color=EmbedFactory.COLOR_GSP_CYAN
        )
        if banner_url:
            embed.set_image(url=banner_url)

        view = TicketPersistentPanel(self.bot, categories)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Support panel deployed successfully.", ephemeral=True)

    @app_commands.command(name="ticket_panel", description="Open the interactive dashboard to manage and configure your ticket system.")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        settings_row = await self.bot.db.select_row("SELECT * FROM ticket_settings WHERE guild_id = ?", (guild_id,))
        settings = dict(settings_row) if settings_row else {}
        
        categories_rows = await self.bot.db.execute("SELECT category_key, label FROM ticket_categories WHERE guild_id = ?", (guild_id,))
        categories_list = [f"• **{r[1]}** (`{r[0]}`)" for r in categories_rows]
        
        parent_cat = f"<#{settings.get('category_id')}>" if settings.get("category_id") else "`Not Configured`"
        transcript_chan = f"<#{settings.get('transcript_channel_id')}>" if settings.get("transcript_channel_id") else "`Not Configured`"
        max_limit = f"`{settings.get('ticket_limit', 1)}`"
        categories_str = "\n".join(categories_list) if categories_list else "*No active categories*"

        embed = discord.Embed(
            title="🎫 Ticket System Management Dashboard",
            description=(
                "Use the interactive dashboard buttons below to configure your ticketing environment.\n\n"
                f"**📂 Current Configured Categories:**\n{categories_str}\n\n"
                f"**🔧 Dashboard Settings:**\n"
                f"• Parent Category Folder: {parent_cat}\n"
                f"• Transcripts Channel: {transcript_chan}\n"
                f"• Active Ticket Limit: {max_limit}"
            ),
            color=EmbedFactory.COLOR_GSP_CYAN
        )
        view = TicketAdminPanelControlView(self.bot, guild_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TicketSystem(bot))
