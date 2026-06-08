import aiosqlite
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("GSP.Database")

class DatabaseManager:
    """
    Asynchronous SQL structural layer governing all identity tracking, 
    verification records, quarantine status metrics, and platform settings.
    """
    def __init__(self, db_path: str = "database.db"):
        self.db_path = db_path

    async def initialize(self) -> None:
        """Initializes all required structural schemas required for complete GSP platform execution."""
        async with aiosqlite.connect(self.db_path) as db:
            # ==========================================
            # BASE PLATFORM CONFIGURATIONS
            # ==========================================
            await db.execute("""
                CREATE TABLE IF NOT EXISTS gsp_guild_config (
                    guild_id TEXT PRIMARY KEY,
                    verified_role_id TEXT,
                    quarantine_role_id TEXT,
                    log_channel_id TEXT,
                    verification_channel_id TEXT,
                    captcha_difficulty TEXT DEFAULT 'MEDIUM',
                    anti_spam_enabled INTEGER DEFAULT 1,
                    anti_raid_enabled INTEGER DEFAULT 1,
                    anti_alt_enabled INTEGER DEFAULT 1,
                    min_age_days INTEGER DEFAULT 7,
                    spam_score_threshold INTEGER DEFAULT 100
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS gsp_identity (
                    user_id TEXT PRIMARY KEY,
                    first_seen INTEGER,
                    verification_attempts INTEGER DEFAULT 0,
                    verification_successes INTEGER DEFAULT 0,
                    verification_failures INTEGER DEFAULT 0,
                    reputation_score INTEGER DEFAULT 80,
                    trust_score INTEGER DEFAULT 50,
                    status TEXT DEFAULT 'UNVERIFIED'
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS gsp_quarantine (
                    guild_id TEXT,
                    user_id TEXT,
                    quarantined_at INTEGER,
                    reason TEXT,
                    active INTEGER DEFAULT 1,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS gsp_active_challenges (
                    guild_id TEXT,
                    user_id TEXT,
                    captcha_code TEXT,
                    phrase TEXT,
                    difficulty_level TEXT,
                    expires_at REAL,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)

            # ==========================================
            # ADVANCED FORENSICS SCHEMAS
            # ==========================================
            await db.execute("""
                CREATE TABLE IF NOT EXISTS gsp_network_cache (
                    user_id TEXT PRIMARY KEY,
                    ip_address TEXT,
                    country TEXT,
                    org_asn TEXT,
                    vpn_flag INTEGER DEFAULT 0,
                    proxy_flag INTEGER DEFAULT 0,
                    tor_flag INTEGER DEFAULT 0,
                    risk_score INTEGER DEFAULT 0,
                    scanned_at INTEGER
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS gsp_alt_intelligence (
                    user_id TEXT,
                    guild_id TEXT,
                    matched_user_id TEXT,
                    username_similarity REAL,
                    creation_time_delta_seconds INTEGER,
                    assessed_alt_risk INTEGER,
                    assessed_at INTEGER,
                    PRIMARY KEY (user_id, guild_id, matched_user_id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS gsp_bot_intelligence (
                    user_id TEXT,
                    guild_id TEXT,
                    modal_render_timestamp REAL,
                    submit_timestamp REAL,
                    time_delta_seconds REAL,
                    keystroke_velocity_rating REAL,
                    bot_score INTEGER,
                    scanned_at INTEGER,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS gsp_reputation_ledger (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    guild_id TEXT,
                    event_type TEXT,
                    reputation_delta INTEGER,
                    timestamp INTEGER,
                    description TEXT
                )
            """)

            # ==========================================
            # MONITORS & MITIGATION RESPONSE SCHEMAS
            # ==========================================
            await db.execute("""
                CREATE TABLE IF NOT EXISTS gsp_security_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT,
                    user_id TEXT,
                    system_origin TEXT,
                    severity TEXT,
                    event_type TEXT,
                    description TEXT,
                    timestamp INTEGER
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS gsp_shield_status (
                    guild_id TEXT PRIMARY KEY,
                    shield_active INTEGER DEFAULT 1,
                    threat_level TEXT DEFAULT 'NONE',
                    lockdown_active INTEGER DEFAULT 0,
                    extreme_mode INTEGER DEFAULT 0,
                    auto_lockdown_threshold INTEGER DEFAULT 15,
                    auto_quarantine_level TEXT DEFAULT 'HIGH'
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS gsp_analytics_daily (
                    guild_id TEXT,
                    log_date TEXT,
                    total_scans INTEGER DEFAULT 0,
                    successful_scans INTEGER DEFAULT 0,
                    blocked_alts INTEGER DEFAULT 0,
                    blocked_bots INTEGER DEFAULT 0,
                    blocked_vpns INTEGER DEFAULT 0,
                    raid_alerts INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, log_date)
                )
            """)

            # ==========================================
            # TICKETING & LEVELS SCHEMAS
            # ==========================================
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    channel_id TEXT PRIMARY KEY,
                    guild_id TEXT,
                    user_id TEXT,
                    status TEXT DEFAULT 'open',
                    priority TEXT DEFAULT 'medium',
                    claimed_by TEXT,
                    category_key TEXT DEFAULT 'general'
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_settings (
                    guild_id TEXT PRIMARY KEY,
                    support_role_ids TEXT,
                    category_id TEXT,
                    transcript_channel_id TEXT,
                    naming_format TEXT,
                    ticket_limit INTEGER DEFAULT 1,
                    auto_close_inactive INTEGER DEFAULT 0
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_categories (
                    category_key TEXT,
                    guild_id TEXT,
                    label TEXT,
                    emoji TEXT,
                    description TEXT,
                    role_id TEXT,
                    prefix TEXT,
                    PRIMARY KEY (guild_id, category_key)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_level_settings (
                    guild_id TEXT PRIMARY KEY,
                    levels_enabled INTEGER DEFAULT 1,
                    msg_type TEXT DEFAULT 'text',
                    msg_template TEXT DEFAULT '🎉 {user} has advanced to **Level {newlevel}**!',
                    msg_color TEXT DEFAULT '65280',
                    cooldown_seconds INTEGER DEFAULT 60
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS users_levels (
                    guild_id TEXT,
                    user_id TEXT,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS level_rewards (
                    guild_id TEXT,
                    level INTEGER,
                    role_id TEXT,
                    PRIMARY KEY (guild_id, level)
                )
            """)

            # ==========================================
            # LOGGING, MODERATION & GENERAL SCHEMAS
            # ==========================================
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_logs (
                    guild_id TEXT PRIMARY KEY,
                    master_log_channel TEXT,
                    log_moderation TEXT,
                    log_messages TEXT,
                    log_join_leave TEXT,
                    log_automod TEXT,
                    log_security TEXT,
                    log_verification TEXT,
                    log_tickets TEXT,
                    log_role_updates TEXT,
                    log_channel_updates TEXT,
                    log_voice TEXT,
                    log_reaction_roles TEXT
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS infractions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT,
                    user_id TEXT,
                    mod_id TEXT,
                    type TEXT,
                    reason TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    message_id TEXT,
                    emoji TEXT,
                    role_id TEXT,
                    guild_id TEXT,
                    PRIMARY KEY (message_id, emoji)
                )
            """)

            await db.commit()
        logger.info("Guard Security Platform Database tables finalized successfully.")

    async def execute(self, query: str, parameters: tuple = ()) -> List[Any]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, parameters) as cursor:
                await db.commit()
                return await cursor.fetchall()

    async def select_row(self, query: str, parameters: tuple = ()) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, parameters) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def select_all(self, query: str, parameters: tuple = ()) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, parameters) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
