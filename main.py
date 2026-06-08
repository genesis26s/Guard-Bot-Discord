```python
import os
import sys
import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.database import DatabaseManager
from utils.cache import GuardCache

# Configure premium industrial logging formats
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("GSP.Main")

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    logger.critical("CRITICAL: DISCORD_TOKEN is missing from your environment configuration.")
    sys.exit(1)

class GuardBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.moderation = True
        intents.guilds = True
        intents.reactions = True
        
        super().__init__(
            command_prefix=[],
            intents=intents,
            help_command=None
        )
        self.db = DatabaseManager()
        self.cache = GuardCache()
        self.loaded_cogs_status = {}

    async def setup_hook(self):
        # 1. Initialize SQLite Database Tables & Migrations
        await self.db.initialize()
        
        # 2. Hydrate Server configuration settings into active cache memory
        records = await self.db.select_all("SELECT * FROM gsp_guild_config")
        for row in records:
            self.cache.set_guild_config(int(row["guild_id"]), row)

        # 3. Modular System Cog Loader Matrix
        cogs_list = [
            'cogs.guard_identity',
            'cogs.guard_verification',
            'cogs.guard_intelligence',
            'cogs.guard_protection',
            'cogs.tickets',
            'cogs.levels',
            'cogs.automod',
            'cogs.logging_system',
            'cogs.moderation',
            'cogs.utility',
            'cogs.help_system'
        ]
        
        print("\n┌────────────────────────────────────────────────────────┐")
        print("│       GUARD SECURITY PLATFORM™ COG SHIELD LOADING      │")
        print("├────────────────────────────────────────────────────────┤")
        for cog in cogs_list:
            cog_clean_name = cog.split('.')[-1].upper()
            try:
                await self.load_extension(cog)
                self.loaded_cogs_status[cog_clean_name] = "🟢 SECURE"
                print(f"│  → LOADING {cog_clean_name:<20} ─── [ SUCCESS ] │")
            except Exception as e:
                self.loaded_cogs_status[cog_clean_name] = "🔴 FAILED"
                print(f"│  → LOADING {cog_clean_name:<20} ─── [ FAILURE ] │")
                logger.error(f"Failed loading cog extension {cog}: {e}")
        print("└────────────────────────────────────────────────────────┘")

        # 4. Global Command Synchronizer Tree
        print("📡 Synchronizing dynamic application commands with Discord Gateway...")
        try:
            synced = await self.tree.sync()
            print(f"✅ Secure handshake complete: Synced {len(synced)} application commands.")
        except Exception as e:
            logger.warning(f"Gateway Handshake command synchronization warning: {e}")

    async def on_ready(self):
        latency_ms = round(self.latency * 1000)
        guilds_count = len(self.guilds)
        total_users = sum(guild.member_count for guild in self.guilds)

        print("\n" + "═"*66)
        print(f" GUARD SECURITY PLATFORM™ CORE SENTINEL ENGINE ONLINE ".center(66, "═"))
        print("═"*66)
        print(f"  • Secure Account Identity :  {self.user.name} ({self.user.id})")
        print(f"  • Connection Latency      :  {latency_ms} ms")
        print(f"  • Active Server Nodes     :  {guilds_count} Servers")
        print(f"  • Total Tracked Profiles  :  {total_users} users")
        print("─"*66)
        print("  SYSTEM INTEGRITY GRID STATUS:")
        
        # Output visual operational matrix
        cog_items = list(self.loaded_cogs_status.items())
        for i in range(0, len(cog_items), 2):
            col1 = f"    {cog_items[i][0][:18]}: {cog_items[i][1]}"
            if i + 1 < len(cog_items):
                col2 = f"{cog_items[i+1][0][:18]}: {cog_items[i+1][1]}"
                print(f"{col1:<35} | {col2}")
            else:
                print(f"{col1}")
                
        print("═"*66 + "\n")
        
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="over GSP secure protocols | /help")
        )

bot = GuardBot()

if __name__ == "__main__":
    asyncio.run(bot.start(TOKEN))
