"""
Oura API Client
Handles all interactions with the Oura Ring API
"""

import httpx
from typing import Dict, Any, Optional
from datetime import date

OURA_API_BASE_URL = "https://api.ouraring.com/v2/usercollection"

class OuraAPIClient:
    """Client for Oura API with error handling and retry logic"""
    
    def __init__(self, api_token: str):
        """Initialize client with API token"""
        self.api_token = api_token
        self.headers = {"Authorization": f"Bearer {api_token}"}
    
    async def fetch_data(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Fetch data from Oura API
        
        Args:
            endpoint: API endpoint (e.g., "daily_stress", "daily_resilience")
            params: Query parameters (e.g., start_date, end_date)
            
        Returns:
            API response as dictionary, or error dict with isError=True
        """
        url = f"{OURA_API_BASE_URL}/{endpoint}"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers, params=params or {})
                
                if response.status_code == 401:
                    return {"error": "Invalid Oura token", "isError": True}
                
                if response.status_code == 429:
                    return {"error": "Rate limited", "isError": True}
                
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}: {e.response.text}", "isError": True}
        except httpx.TimeoutException:
            return {"error": "Request timed out", "isError": True}
        except Exception as e:
            return {"error": f"API error: {str(e)}", "isError": True}
    
    async def get_daily_stress(self, target_date: str) -> Dict[str, Any]:
        """Get daily stress data for a specific date"""
        params = {"start_date": target_date, "end_date": target_date}
        return await self.fetch_data("daily_stress", params)
    
    async def get_daily_resilience(self, target_date: str) -> Dict[str, Any]:
        """Get daily resilience data for a specific date"""
        params = {"start_date": target_date, "end_date": target_date}
        return await self.fetch_data("daily_resilience", params)
    
    async def get_daily_readiness(self, target_date: str) -> Dict[str, Any]:
        """Get daily readiness data for a specific date"""
        params = {"start_date": target_date, "end_date": target_date}
        return await self.fetch_data("daily_readiness", params)
    
    async def get_daily_sleep(self, target_date: str) -> Dict[str, Any]:
        """Get daily sleep summary data for a specific date (score + contributors only)"""
        params = {"start_date": target_date, "end_date": target_date}
        return await self.fetch_data("daily_sleep", params)

    async def get_sleep(self, target_date: str) -> Dict[str, Any]:
        """Get detailed sleep data for a specific date (includes durations, timestamps, HRV, etc.)

        Note: Queries a wider range because API filters by bedtime_start,
        but we want records where the day field matches target_date.
        Also handles timezone differences between server and API.
        """
        from datetime import datetime, timedelta
        target = datetime.strptime(target_date, "%Y-%m-%d")
        # Query 2 days before through 1 day after to handle timezone issues
        start = (target - timedelta(days=2)).strftime("%Y-%m-%d")
        end = (target + timedelta(days=1)).strftime("%Y-%m-%d")
        params = {"start_date": start, "end_date": end}
        return await self.fetch_data("sleep", params)
    
    async def get_daily_activity(self, target_date: str) -> Dict[str, Any]:
        """Get daily activity data for a specific date"""
        params = {"start_date": target_date, "end_date": target_date}
        return await self.fetch_data("daily_activity", params)

    # Range query methods for trends
    async def get_daily_readiness_range(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get daily readiness data for a date range (for trends: score + temperature_deviation)"""
        params = {"start_date": start_date, "end_date": end_date}
        return await self.fetch_data("daily_readiness", params)

    async def get_daily_sleep_range(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get daily sleep summary data for a date range (for trends: sleep score)"""
        params = {"start_date": start_date, "end_date": end_date}
        return await self.fetch_data("daily_sleep", params)

    async def get_sleep_range(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get detailed sleep data for a date range (for trends: HRV)

        Note: Extends range by 2 days before to handle bedtime_start filtering.
        """
        from datetime import datetime, timedelta
        start = datetime.strptime(start_date, "%Y-%m-%d")
        adjusted_start = (start - timedelta(days=2)).strftime("%Y-%m-%d")
        params = {"start_date": adjusted_start, "end_date": end_date}
        return await self.fetch_data("sleep", params)