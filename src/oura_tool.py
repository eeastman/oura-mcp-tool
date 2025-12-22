"""
Oura MCP Tool - Access Oura Ring health data through Dreamer platform
"""

from fastmcp import FastMCP
from pydantic import Field
import httpx
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Oura API token from environment
OURA_API_TOKEN = os.getenv('OURA_API_TOKEN')
OURA_API_BASE_URL = "https://api.ouraring.com/v2/usercollection"

# Initialize FastMCP server
mcp = FastMCP("oura-health", version="1.0.0")


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


@mcp.tool()
async def get_sleep_data(
    start_date: str = Field(description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format (defaults to start_date)")
) -> dict:
    """Get sleep data from Oura for a specified date range."""
    
    if not oura_client:
        return {
            "content": [{
                "type": "text",
                "text": "Oura API token not configured. Please set OURA_API_TOKEN environment variable."
            }],
            "isError": True
        }
    
    try:
        # Validate dates
        datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_date = start_date
        
        # Fetch sleep data
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        data = await oura_client.fetch_with_retry("sleep", params)
        
        if data.get("isError"):
            return {
                "content": [{
                    "type": "text",
                    "text": data.get("error", "Failed to fetch sleep data")
                }],
                "isError": True
            }
        
        sleep_sessions = data.get("data", [])
        
        if not sleep_sessions:
            return {
                "content": [{
                    "type": "text",
                    "text": f"No sleep data found for {start_date} to {end_date}"
                }],
                "structuredContent": {
                    "sleep_sessions": [],
                    "date_range": {
                        "start": start_date,
                        "end": end_date
                    }
                }
            }
        
        # Format sleep data
        formatted_sessions = []
        for session in sleep_sessions:
            formatted_sessions.append({
                "date": session.get("day"),
                "total_sleep": session.get("total_sleep_duration"),
                "rem_sleep": session.get("rem_sleep_duration"),
                "deep_sleep": session.get("deep_sleep_duration"),
                "light_sleep": session.get("light_sleep_duration"),
                "awake_time": session.get("awake_time"),
                "sleep_score": session.get("score", {}).get("total"),
                "efficiency": session.get("sleep_efficiency"),
                "latency": session.get("sleep_latency"),
                "bedtime_start": session.get("bedtime_start"),
                "bedtime_end": session.get("bedtime_end")
            })
        
        summary_text = f"Found {len(formatted_sessions)} sleep session(s) from {start_date} to {end_date}."
        if formatted_sessions:
            latest = formatted_sessions[0]
            summary_text += f" Latest session: {latest['total_sleep']//3600}h {(latest['total_sleep']%3600)//60}m total sleep, score: {latest['sleep_score']}"
        
        return {
            "content": [{
                "type": "text",
                "text": summary_text
            }],
            "structuredContent": {
                "sleep_sessions": formatted_sessions,
                "date_range": {
                    "start": start_date,
                    "end": end_date
                }
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
                "text": f"Error fetching sleep data: {str(e)}"
            }],
            "isError": True
        }


@mcp.tool()
async def get_activity_data(
    start_date: str = Field(description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format (defaults to start_date)")
) -> dict:
    """Get daily activity data from Oura for a specified date range."""
    
    if not oura_client:
        return {
            "content": [{
                "type": "text",
                "text": "Oura API token not configured. Please set OURA_API_TOKEN environment variable."
            }],
            "isError": True
        }
    
    try:
        # Validate dates
        datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_date = start_date
        
        # Fetch activity data
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        data = await oura_client.fetch_with_retry("daily_activity", params)
        
        if data.get("isError"):
            return {
                "content": [{
                    "type": "text",
                    "text": data.get("error", "Failed to fetch activity data")
                }],
                "isError": True
            }
        
        activities = data.get("data", [])
        
        if not activities:
            return {
                "content": [{
                    "type": "text",
                    "text": f"No activity data found for {start_date} to {end_date}"
                }],
                "structuredContent": {
                    "activities": [],
                    "date_range": {
                        "start": start_date,
                        "end": end_date
                    }
                }
            }
        
        # Format activity data
        formatted_activities = []
        for activity in activities:
            formatted_activities.append({
                "date": activity.get("day"),
                "activity_score": activity.get("score"),
                "steps": activity.get("steps"),
                "active_calories": activity.get("active_calories"),
                "total_calories": activity.get("total_calories"),
                "equivalent_walking_distance": activity.get("equivalent_walking_distance"),
                "high_activity_time": activity.get("high_activity_time"),
                "medium_activity_time": activity.get("medium_activity_time"),
                "low_activity_time": activity.get("low_activity_time"),
                "sedentary_time": activity.get("sedentary_time"),
                "movement_alert_count": activity.get("non_wear_time"),
                "target_calories": activity.get("target_calories"),
                "target_meters": activity.get("target_meters")
            })
        
        summary_text = f"Found {len(formatted_activities)} day(s) of activity data from {start_date} to {end_date}."
        if formatted_activities:
            latest = formatted_activities[0]
            summary_text += f" Latest: {latest['steps']} steps, {latest['total_calories']} calories, activity score: {latest['activity_score']}"
        
        return {
            "content": [{
                "type": "text",
                "text": summary_text
            }],
            "structuredContent": {
                "activities": formatted_activities,
                "date_range": {
                    "start": start_date,
                    "end": end_date
                }
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
                "text": f"Error fetching activity data: {str(e)}"
            }],
            "isError": True
        }


@mcp.tool()
async def get_readiness_data(
    start_date: str = Field(description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format (defaults to start_date)")
) -> dict:
    """Get readiness scores from Oura for a specified date range."""
    
    if not oura_client:
        return {
            "content": [{
                "type": "text",
                "text": "Oura API token not configured. Please set OURA_API_TOKEN environment variable."
            }],
            "isError": True
        }
    
    try:
        # Validate dates
        datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_date = start_date
        
        # Fetch readiness data
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        data = await oura_client.fetch_with_retry("daily_readiness", params)
        
        if data.get("isError"):
            return {
                "content": [{
                    "type": "text",
                    "text": data.get("error", "Failed to fetch readiness data")
                }],
                "isError": True
            }
        
        readiness_data = data.get("data", [])
        
        if not readiness_data:
            return {
                "content": [{
                    "type": "text",
                    "text": f"No readiness data found for {start_date} to {end_date}"
                }],
                "structuredContent": {
                    "readiness": [],
                    "date_range": {
                        "start": start_date,
                        "end": end_date
                    }
                }
            }
        
        # Format readiness data
        formatted_readiness = []
        for readiness in readiness_data:
            contributors = readiness.get("contributors", {})
            formatted_readiness.append({
                "date": readiness.get("day"),
                "readiness_score": readiness.get("score"),
                "temperature_deviation": readiness.get("temperature_deviation"),
                "temperature_trend_deviation": readiness.get("temperature_trend_deviation"),
                "contributors": {
                    "activity_balance": contributors.get("activity_balance"),
                    "body_temperature": contributors.get("body_temperature"),
                    "hrv_balance": contributors.get("hrv_balance"),
                    "previous_day_activity": contributors.get("previous_day_activity"),
                    "previous_night": contributors.get("previous_night"),
                    "recovery_index": contributors.get("recovery_index"),
                    "resting_heart_rate": contributors.get("resting_heart_rate"),
                    "sleep_balance": contributors.get("sleep_balance")
                }
            })
        
        summary_text = f"Found {len(formatted_readiness)} day(s) of readiness data from {start_date} to {end_date}."
        if formatted_readiness:
            latest = formatted_readiness[0]
            summary_text += f" Latest readiness score: {latest['readiness_score']}"
        
        return {
            "content": [{
                "type": "text",
                "text": summary_text
            }],
            "structuredContent": {
                "readiness": formatted_readiness,
                "date_range": {
                    "start": start_date,
                    "end": end_date
                }
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
                "text": f"Error fetching readiness data: {str(e)}"
            }],
            "isError": True
        }


@mcp.tool()
async def get_heart_rate_data(
    start_datetime: str = Field(description="Start datetime in YYYY-MM-DDTHH:MM:SS format"),
    end_datetime: Optional[str] = Field(None, description="End datetime in YYYY-MM-DDTHH:MM:SS format (defaults to 24 hours after start)")
) -> dict:
    """Get heart rate data from Oura for a specified time range."""
    
    if not oura_client:
        return {
            "content": [{
                "type": "text",
                "text": "Oura API token not configured. Please set OURA_API_TOKEN environment variable."
            }],
            "isError": True
        }
    
    try:
        # Parse and validate datetime
        start_dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
        if end_datetime:
            end_dt = datetime.fromisoformat(end_datetime.replace('Z', '+00:00'))
        else:
            end_dt = start_dt + timedelta(days=1)
        
        # Fetch heart rate data
        params = {
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat()
        }
        
        data = await oura_client.fetch_with_retry("heartrate", params)
        
        if data.get("isError"):
            return {
                "content": [{
                    "type": "text",
                    "text": data.get("error", "Failed to fetch heart rate data")
                }],
                "isError": True
            }
        
        heart_rate_data = data.get("data", [])
        
        if not heart_rate_data:
            return {
                "content": [{
                    "type": "text",
                    "text": f"No heart rate data found for the specified time range"
                }],
                "structuredContent": {
                    "heart_rate_samples": [],
                    "time_range": {
                        "start": start_datetime,
                        "end": end_datetime or end_dt.isoformat()
                    }
                }
            }
        
        # Calculate statistics
        bpms = [hr.get("bpm") for hr in heart_rate_data if hr.get("bpm")]
        
        stats = {
            "count": len(heart_rate_data),
            "average_bpm": sum(bpms) / len(bpms) if bpms else 0,
            "min_bpm": min(bpms) if bpms else 0,
            "max_bpm": max(bpms) if bpms else 0
        }
        
        # Sample the data if too many points
        if len(heart_rate_data) > 500:
            step = len(heart_rate_data) // 500
            sampled_data = heart_rate_data[::step]
        else:
            sampled_data = heart_rate_data
        
        summary_text = f"Found {stats['count']} heart rate measurements. "
        summary_text += f"Average: {stats['average_bpm']:.0f} bpm, "
        summary_text += f"Range: {stats['min_bpm']}-{stats['max_bpm']} bpm"
        
        return {
            "content": [{
                "type": "text",
                "text": summary_text
            }],
            "structuredContent": {
                "heart_rate_samples": sampled_data,
                "statistics": stats,
                "time_range": {
                    "start": start_datetime,
                    "end": end_datetime or end_dt.isoformat()
                }
            }
        }
        
    except ValueError as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Invalid datetime format: {str(e)}. Please use YYYY-MM-DDTHH:MM:SS format."
            }],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error fetching heart rate data: {str(e)}"
            }],
            "isError": True
        }


@mcp.tool()
async def get_personal_info() -> dict:
    """Get personal/profile information from Oura."""
    
    if not oura_client:
        return {
            "content": [{
                "type": "text",
                "text": "Oura API token not configured. Please set OURA_API_TOKEN environment variable."
            }],
            "isError": True
        }
    
    try:
        # Fetch personal info
        data = await oura_client.fetch_with_retry("personal_info")
        
        if data.get("isError"):
            return {
                "content": [{
                    "type": "text",
                    "text": data.get("error", "Failed to fetch personal information")
                }],
                "isError": True
            }
        
        # Format personal info
        info = {
            "age": data.get("age"),
            "weight": data.get("weight"),
            "height": data.get("height"),
            "biological_sex": data.get("biological_sex"),
            "email": data.get("email")
        }
        
        summary_text = "Retrieved Oura user profile information"
        if info.get("email"):
            summary_text += f" for {info['email']}"
        
        return {
            "content": [{
                "type": "text",
                "text": summary_text
            }],
            "structuredContent": {
                "personal_info": info
            }
        }
        
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error fetching personal information: {str(e)}"
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
    
    print(f"Starting Oura MCP server on port {port}")
    print(f"Server will listen on 0.0.0.0:{port}")
    
    # Run the MCP server - bind to 0.0.0.0 for Railway
    mcp.run(transport="streamable-http", port=port, host="0.0.0.0")


if __name__ == "__main__":
    import asyncio
    main()