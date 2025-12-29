"""
Storage wrapper to maintain dictionary-like interface
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from .storage import TokenStorage, get_storage


class StorageDict:
    """Dictionary-like wrapper around TokenStorage"""
    
    def __init__(self, storage: TokenStorage, prefix: str, default_ttl: Optional[int] = None):
        self.storage = storage
        self.prefix = prefix
        self.default_ttl = default_ttl  # Default TTL in seconds
    
    def _make_key(self, key: str) -> str:
        """Create prefixed key"""
        return f"{self.prefix}:{key}"
    
    async def set(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Set a value with optional TTL"""
        if ttl is None:
            ttl = self.default_ttl
        await self.storage.set(self._make_key(key), value, ttl)
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a value"""
        return await self.storage.get(self._make_key(key))
    
    async def delete(self, key: str) -> None:
        """Delete a key"""
        await self.storage.delete(self._make_key(key))
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        return await self.storage.exists(self._make_key(key))
    
    # Dictionary-like methods for compatibility
    async def __contains__(self, key: str) -> bool:
        """Support 'in' operator"""
        return await self.exists(key)
    
    async def pop(self, key: str, default=None) -> Any:
        """Pop a value"""
        value = await self.get(key)
        if value is not None:
            await self.delete(key)
            return value
        return default


class OAuthStorageManager:
    """Manages all OAuth storage with proper TTLs"""
    
    def __init__(self, storage: Optional[TokenStorage] = None):
        if storage is None:
            storage = get_storage()
        self.storage = storage
        
        # Initialize storage collections with appropriate TTLs
        self.clients = StorageDict(storage, "client", None)  # No expiration
        self.auth_codes = StorageDict(storage, "auth_code", 600)  # 10 minutes
        self.access_tokens = StorageDict(storage, "access_token", 3600)  # 1 hour default
        self.user_tokens = StorageDict(storage, "user_token", None)  # No expiration
    
    async def create_access_token(self, token: str, data: Dict[str, Any], expires_in: int = 3600) -> None:
        """Create an access token with expiration"""
        await self.access_tokens.set(token, data, expires_in)
    
    async def create_refresh_token(self, token: str, data: Dict[str, Any]) -> None:
        """Create a refresh token with 30-day expiration"""
        data['is_refresh_token'] = True
        await self.access_tokens.set(token, data, 30 * 24 * 3600)  # 30 days
    
    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate and return token data"""
        return await self.access_tokens.get(token)
    
    async def cleanup_expired(self) -> int:
        """Clean up expired tokens"""
        return await self.storage.clear_expired()


# Global storage manager instance
_storage_manager = None


def get_storage_manager() -> OAuthStorageManager:
    """Get or create the global storage manager"""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = OAuthStorageManager()
    return _storage_manager