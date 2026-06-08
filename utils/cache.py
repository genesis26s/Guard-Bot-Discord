import time
from collections import defaultdict, deque
from typing import Dict, Any, Optional, List, Tuple

class GuardCache:
    """
    Sub-millisecond in-memory cache manager keeping high-velocity configuration paths,
    threat records, and dynamic identity statistics accessible without SQL bottlenecks.
    """
    def __init__(self):
        # Guild Security Matrix Configs: {guild_id_str: config_dict}
        self.configs: Dict[str, Dict[str, Any]] = {}
        
        # Guard Identity Profiling Cache: {user_id_str: identity_dict}
        self.identities: Dict[str, Dict[str, Any]] = {}
        
        # Real-time Quarantine registries: {guild_id_str: {user_id_str: quarantine_record_dict}}
        self.quarantine_registry: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        
        # Rate limit / verification tracking registers
        self.join_rates: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        self.verification_rate_limits: Dict[str, float] = {}

        # Message History Buffers for Sniper logs
        self.deleted_messages: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        self.edited_messages: Dict[int, List[Dict[str, Any]]] = defaultdict(list)

        # AFK Storage Registries
        self.afk_users: Dict[str, Dict[str, Any]] = {}

    def get_guild_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        return self.configs.get(str(guild_id))

    def set_guild_config(self, guild_id: int, config: Dict[str, Any]) -> None:
        self.configs[str(guild_id)] = config

    def clear_guild_config(self, guild_id: int) -> None:
        self.configs.pop(str(guild_id), None)

    def get_identity(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.identities.get(str(user_id))

    def set_identity(self, user_id: int, identity_data: Dict[str, Any]) -> None:
        self.identities[str(user_id)] = identity_data

    def is_quarantined(self, guild_id: int, user_id: int) -> bool:
        guild_key = str(guild_id)
        user_key = str(user_id)
        if guild_key in self.quarantine_registry:
            record = self.quarantine_registry[guild_key].get(user_key)
            if record and record.get("active", 1) == 1:
                return True
        return False

    def register_quarantine(self, guild_id: int, user_id: int, record: Dict[str, Any]) -> None:
        self.quarantine_registry[str(guild_id)][str(user_id)] = record

    def revoke_quarantine(self, guild_id: int, user_id: int) -> None:
        guild_key = str(guild_id)
        user_key = str(user_id)
        if guild_key in self.quarantine_registry and user_key in self.quarantine_registry[guild_key]:
            self.quarantine_registry[guild_key][user_key]["active"] = 0
