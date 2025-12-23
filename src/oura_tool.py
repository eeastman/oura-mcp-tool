"""
Oura Stress and Resilience MCP Tool - Access stress load and resilience data through Dreamer platform
"""

from fastmcp import FastMCP
from pydantic import Field
import httpx
import os
from datetime import datetime, date
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Get Oura API token from environment
OURA_API_TOKEN = os.getenv('OURA_API_TOKEN')
OURA_API_BASE_URL = "https://api.ouraring.com/v2/usercollection"

# Initialize FastMCP server
mcp = FastMCP("oura-stress-resilience", version="1.0.0")


class OuraAPIClient:
    """Client for interacting with Oura API"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}"
        }
    
    async def fetch_with_retry(self, endpoint: str, params: Optional[Dict[str, Any]] = None, max_retries: int = 3) -> Dict[str, Any]:
        """Fetch data from Oura API with retry logic"""
        url = f"{OURA_API_BASE_URL}/{endpoint}"
        
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, headers=self.headers, params=params)
                    
                    if response.status_code == 401:
                        return {
                            "error": "Invalid API token. Please check your Oura API token.",
                            "isError": True
                        }
                    
                    if response.status_code == 429:
                        if attempt < max_retries:
                            # Rate limited, wait and retry
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return {
                            "error": "Rate limit exceeded. Please try again later.",
                            "isError": True
                        }
                    
                    response.raise_for_status()
                    return response.json()
                    
            except httpx.TimeoutException:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {
                    "error": "Request timeout. Please try again.",
                    "isError": True
                }
            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {
                    "error": f"Error fetching data: {str(e)}",
                    "isError": True
                }


# Initialize the Oura client
oura_client = OuraAPIClient(OURA_API_TOKEN) if OURA_API_TOKEN else None


def calculate_stress_ratio(high_stress_seconds: int, recovery_seconds: int) -> float:
    """Calculate stress:recovery ratio, handling division by zero"""
    if recovery_seconds == 0:
        return float('inf') if high_stress_seconds > 0 else 0.0
    return high_stress_seconds / recovery_seconds


def get_day_summary_description(ratio: float) -> str:
    """Convert stress ratio to descriptive summary"""
    if ratio == 0:
        return "very_restorative"
    elif ratio <= 1:
        return "restorative" 
    elif ratio <= 2:
        return "balanced"
    elif ratio <= 4:
        return "stressful"
    else:
        return "very_stressful"


def get_resilience_level(contributors: Dict[str, int]) -> str:
    """Determine resilience level based on contributor scores"""
    avg_score = sum(contributors.values()) / len(contributors) if contributors else 0
    
    if avg_score >= 75:
        return "excellent"
    elif avg_score >= 60:
        return "good"
    elif avg_score >= 45:
        return "limited"
    else:
        return "low"


@mcp.tool()
async def get_stress_and_resilience(
    user_id: Optional[str] = Field(None, description="User ID (not required for personal tokens)"),
    date_param: Optional[str] = Field(None, description="Date in YYYY-MM-DD format (defaults to today)")
) -> dict:
    """
    Returns today's stress load (time in high stress vs. recovery) and resilience level.
    
    Provides actionable stress:recovery ratio and resilience context to understand
    capacity decline patterns beyond just readiness scores.
    """
    
    if not oura_client:
        return {
            "content": [{
                "type": "text",
                "text": "Oura API token not configured. Please set OURA_API_TOKEN environment variable."
            }],
            "isError": True
        }
    
    try:
        # Use provided date or default to today
        target_date = date_param if date_param else date.today().strftime("%Y-%m-%d")
        
        # Validate date format
        datetime.strptime(target_date, "%Y-%m-%d")
        
        # Fetch both stress and resilience data in parallel
        stress_params = {"start_date": target_date, "end_date": target_date}
        
        # Make both API calls
        stress_task = oura_client.fetch_with_retry("daily_stress", stress_params)
        resilience_task = oura_client.fetch_with_retry("daily_resilience", stress_params)
        
        stress_data, resilience_data = await asyncio.gather(stress_task, resilience_task)
        
        # Check for API errors
        if stress_data.get("isError"):
            return {
                "content": [{
                    "type": "text", 
                    "text": f"Error fetching stress data: {stress_data.get('error')}"
                }],
                "isError": True
            }
            
        if resilience_data.get("isError"):
            return {
                "content": [{
                    "type": "text",
                    "text": f"Error fetching resilience data: {resilience_data.get('error')}"
                }],
                "isError": True
            }
        
        # Extract data for the target date
        stress_records = stress_data.get("data", [])
        resilience_records = resilience_data.get("data", [])
        
        # Find records for the target date
        stress_record = next((r for r in stress_records if r.get("day") == target_date), None)
        resilience_record = next((r for r in resilience_records if r.get("day") == target_date), None)
        
        if not stress_record:
            return {
                "content": [{
                    "type": "text",
                    "text": f"No stress data found for {target_date}"
                }],
                "structuredContent": {
                    "date": target_date,
                    "stress": None,
                    "resilience": None
                }
            }
        
        # Process stress data
        high_stress_seconds = stress_record.get("stress_high", 0)
        recovery_seconds = stress_record.get("recovery_high", 0)
        ratio = calculate_stress_ratio(high_stress_seconds, recovery_seconds)
        day_summary = get_day_summary_description(ratio)
        
        stress_result = {
            "highStressSeconds": high_stress_seconds,
            "recoverySeconds": recovery_seconds, 
            "ratio": ratio if ratio != float('inf') else None,
            "daySummary": day_summary
        }
        
        # Process resilience data
        resilience_result = None
        if resilience_record:
            contributors = resilience_record.get("contributors", {})
            resilience_contributors = {
                "sleepRecovery": contributors.get("sleep_recovery", 0),
                "daytimeRecovery": contributors.get("daytime_recovery", 0), 
                "stress": contributors.get("stress", 0)
            }
            
            resilience_result = {
                "level": get_resilience_level(resilience_contributors),
                "contributors": resilience_contributors
            }
        
        # Create summary text
        stress_hours = high_stress_seconds // 3600
        stress_minutes = (high_stress_seconds % 3600) // 60
        recovery_hours = recovery_seconds // 3600
        recovery_minutes = (recovery_seconds % 3600) // 60
        
        summary_text = f"Stress & Resilience for {target_date}: "
        summary_text += f"{stress_hours}h{stress_minutes}m high stress, "
        summary_text += f"{recovery_hours}h{recovery_minutes}m recovery"
        
        if ratio != float('inf') and ratio is not None:
            summary_text += f" (ratio: {ratio:.1f}:1)"
        
        if resilience_result:
            summary_text += f", resilience: {resilience_result['level']}"
        
        return {
            "content": [{
                "type": "text",
                "text": summary_text
            }],
            "structuredContent": {
                "date": target_date,
                "stress": stress_result,
                "resilience": resilience_result
            }
        }
        
    except ValueError as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Invalid date format: {str(e)}. Please use YYYY-MM-DD format."
            }],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error fetching stress and resilience data: {str(e)}"
            }],
            "isError": True
        }


def main():
    """Run the MCP server"""
    # Railway sets PORT dynamically
    port = int(os.environ.get("PORT", 8080))
    
    # Debug: Print environment info
    print(f"Starting server with PORT={port}")
    print(f"OURA_API_TOKEN present: {'Yes' if os.environ.get('OURA_API_TOKEN') else 'No'}")
    
    if not OURA_API_TOKEN:
        print("Warning: OURA_API_TOKEN not set. The server will start but API calls will fail.")
        print("Please set your Oura API token in the environment or .env file.")
    
    print(f"Starting Oura Stress & Resilience MCP server on port {port}")
    print(f"Server will listen on 0.0.0.0:{port}")
    
    # Run the MCP server - bind to 0.0.0.0 for Railway
    mcp.run(transport="streamable-http", port=port, host="0.0.0.0")


if __name__ == "__main__":
    main()