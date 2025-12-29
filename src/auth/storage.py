"""
Token Storage Interface and Implementations
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import json
import asyncio
import aiosqlite
from datetime import datetime, timedelta
import os


class TokenStorage(ABC):
    """Abstract base class for token storage"""
    
    @abstractmethod
    async def set(self, key: str, value: Dict[str, Any], expire_seconds: Optional[int] = None) -> None:
        """Store a key-value pair with optional expiration"""
        pass
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a value by key"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a key"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists"""
        pass
    
    @abstractmethod
    async def clear_expired(self) -> int:
        """Clear expired entries, return count deleted"""
        pass


class SQLiteStorage(TokenStorage):
    """SQLite implementation of token storage"""
    
    def __init__(self, db_path: str = "data/tokens.db"):
        self.db_path = db_path
        self._ensure_directory()
        self._initialized = False
        self._lock = asyncio.Lock()
    
    def _ensure_directory(self):
        """Ensure the data directory exists"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
    
    async def _init_db(self):
        """Initialize database tables"""
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized:
                return
                
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS tokens (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        expires_at TEXT,
                        created_at TEXT NOT NULL
                    )
                ''')
                await db.execute('''
                    CREATE INDEX IF NOT EXISTS idx_expires_at 
                    ON tokens(expires_at) 
                    WHERE expires_at IS NOT NULL
                ''')
                await db.commit()
            
            self._initialized = True
    
    async def set(self, key: str, value: Dict[str, Any], expire_seconds: Optional[int] = None) -> None:
        """Store a key-value pair with optional expiration"""
        await self._init_db()
        
        expires_at = None
        if expire_seconds:
            expires_at = (datetime.utcnow() + timedelta(seconds=expire_seconds)).isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                '''INSERT OR REPLACE INTO tokens (key, value, expires_at, created_at) 
                   VALUES (?, ?, ?, ?)''',
                (key, json.dumps(value), expires_at, datetime.utcnow().isoformat())
            )
            await db.commit()
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a value by key"""
        await self._init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT value, expires_at FROM tokens WHERE key = ?',
                (key,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            value, expires_at = row
            
            # Check expiration
            if expires_at:
                if datetime.fromisoformat(expires_at) < datetime.utcnow():
                    await self.delete(key)
                    return None
            
            return json.loads(value)
    
    async def delete(self, key: str) -> None:
        """Delete a key"""
        await self._init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM tokens WHERE key = ?', (key,))
            await db.commit()
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists"""
        return await self.get(key) is not None
    
    async def clear_expired(self) -> int:
        """Clear expired entries, return count deleted"""
        await self._init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                '''DELETE FROM tokens 
                   WHERE expires_at IS NOT NULL 
                   AND expires_at < ?''',
                (datetime.utcnow().isoformat(),)
            )
            await db.commit()
            return cursor.rowcount


class InMemoryStorage(TokenStorage):
    """In-memory storage implementation (for testing/development)"""
    
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.expirations: Dict[str, datetime] = {}
    
    async def set(self, key: str, value: Dict[str, Any], expire_seconds: Optional[int] = None) -> None:
        """Store a key-value pair with optional expiration"""
        self.data[key] = value
        
        if expire_seconds:
            self.expirations[key] = datetime.utcnow() + timedelta(seconds=expire_seconds)
        elif key in self.expirations:
            del self.expirations[key]
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a value by key"""
        if key not in self.data:
            return None
        
        # Check expiration
        if key in self.expirations:
            if self.expirations[key] < datetime.utcnow():
                await self.delete(key)
                return None
        
        return self.data[key]
    
    async def delete(self, key: str) -> None:
        """Delete a key"""
        self.data.pop(key, None)
        self.expirations.pop(key, None)
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists"""
        return await self.get(key) is not None
    
    async def clear_expired(self) -> int:
        """Clear expired entries, return count deleted"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, exp_time in self.expirations.items()
            if exp_time < now
        ]
        
        for key in expired_keys:
            await self.delete(key)
        
        return len(expired_keys)


def get_storage(storage_type: Optional[str] = None) -> TokenStorage:
    """Factory function to get storage instance based on environment"""
    if storage_type is None:
        storage_type = os.getenv('STORAGE_TYPE', 'sqlite')
    
    if storage_type == 'sqlite':
        db_path = os.getenv('SQLITE_DB_PATH', 'data/tokens.db')
        return SQLiteStorage(db_path)
    elif storage_type == 'memory':
        return InMemoryStorage()
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")