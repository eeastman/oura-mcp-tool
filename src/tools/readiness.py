"""
Oura Readiness MCP Tool
"""

from datetime import datetime, date
from typing import Optional, Dict, Any, List
from .oura_client import OuraAPIClient

async def get_readiness_data(oura_token: str, date_param: Optional[str] = None) -> Dict[str, Any]:
    """
    Get readiness score and contributors for a specific date
    
    Args:
        oura_token: Oura API token
        date_param: Date in YYYY-MM-DD format (defaults to today)
        
    Returns:
        MCP-formatted response with readiness data
    """
    # Initialize client
    client = OuraAPIClient(oura_token)
    
    # Use provided date or today
    target_date = date_param or date.today().strftime("%Y-%m-%d")
    
    try:
        # Validate date format
        datetime.strptime(target_date, "%Y-%m-%d")
        
        # Fetch readiness data
        readiness_data = await client.get_daily_readiness(target_date)
        
        # Check for errors
        if readiness_data.get("isError"):
            return {
                "content": [{"type": "text", "text": f"Error: {readiness_data['error']}"}],
                "isError": True
            }
        
        # Process data
        readiness_records = readiness_data.get("data", [])
        readiness_record = next((r for r in readiness_records if r.get("day") == target_date), None)
        
        if not readiness_record:
            return {
                "content": [{"type": "text", "text": f"No readiness data found for {target_date}"}],
                "isError": True
            }
        
        # Extract readiness score
        score = readiness_record.get("score", 0)
        
        # Extract contributors (Oura API field names)
        contributors_data = readiness_record.get("contributors", {})
        contributors = {
            "hrvBalance": contributors_data.get("hrv_balance", None),
            "bodyTemperature": contributors_data.get("body_temperature", None),
            "recoveryIndex": contributors_data.get("recovery_index", None),
            "restingHeartRate": contributors_data.get("resting_heart_rate", None),
            "sleepBalance": contributors_data.get("sleep_balance", None),
            "previousNight": contributors_data.get("previous_night", None),
            "previousDayActivity": contributors_data.get("previous_day_activity", None),
            "activityBalance": contributors_data.get("activity_balance", None)
        }
        
        # Identify limiting factors (scores < 70)
        limiting_factors = []
        for key, value in contributors.items():
            if value is not None and value < 70:
                limiting_factors.append((key, value))
        
        # Sort by score (lowest first) and extract just the names
        limiting_factors.sort(key=lambda x: x[1])
        limiting_factor_names = [factor[0] for factor in limiting_factors]
        
        # Extract timestamp
        timestamp = readiness_record.get("timestamp", f"{target_date}T00:00:00Z")
        
        # Format human-readable summary
        summary = f"Readiness: {score}/100"
        if limiting_factors:
            # Show up to 2 limiting factors with their scores
            factors_str = ", ".join([
                f"{_format_contributor_name(f[0])} ({f[1]})" 
                for f in limiting_factors[:2]
            ])
            summary += f". Limited by: {factors_str}"
        
        return {
            "content": [{"type": "text", "text": summary}],
            "structuredContent": {
                "score": score,
                "contributors": contributors,
                "limitingFactors": limiting_factor_names,
                "timestamp": timestamp
            },
            "isError": False
        }
        
    except ValueError:
        return {
            "content": [{"type": "text", "text": "Invalid date format. Use YYYY-MM-DD"}],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "isError": True
        }

def _format_contributor_name(name: str) -> str:
    """Format contributor name for human-readable display"""
    formatting = {
        "hrvBalance": "HRV balance",
        "bodyTemperature": "body temperature",
        "recoveryIndex": "recovery index",
        "restingHeartRate": "resting heart rate",
        "sleepBalance": "sleep balance",
        "previousNight": "previous night",
        "previousDayActivity": "previous day activity",
        "activityBalance": "activity balance"
    }
    return formatting.get(name, name)