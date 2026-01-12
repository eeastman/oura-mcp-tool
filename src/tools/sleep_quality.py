"""
Oura Sleep Quality MCP Tool
"""

from datetime import datetime, date
from typing import Optional, Dict, Any, List
from .oura_client import OuraAPIClient

async def get_sleep_quality_data(oura_token: str, date_param: Optional[str] = None) -> Dict[str, Any]:
    """
    Get sleep quality score and contributors for a specific date
    
    Args:
        oura_token: Oura API token
        date_param: Date in YYYY-MM-DD format (defaults to today)
        
    Returns:
        MCP-formatted response with sleep quality data
    """
    # Initialize client
    client = OuraAPIClient(oura_token)
    
    # Use provided date or today
    target_date = date_param or date.today().strftime("%Y-%m-%d")
    
    try:
        # Validate date format
        datetime.strptime(target_date, "%Y-%m-%d")
        
        # Fetch sleep data
        sleep_data = await client.get_daily_sleep(target_date)
        
        # Check for errors
        if sleep_data.get("isError"):
            return {
                "content": [{"type": "text", "text": f"Error: {sleep_data['error']}"}],
                "isError": True
            }
        
        # Process data
        sleep_records = sleep_data.get("data", [])
        sleep_record = next((r for r in sleep_records if r.get("day") == target_date), None)
        
        if not sleep_record:
            return {
                "content": [{"type": "text", "text": f"No sleep data found for {target_date}"}],
                "isError": True
            }
        
        # Extract sleep score
        score = sleep_record.get("score", 0)
        
        # Extract contributors (Oura API field names)
        contributors_data = sleep_record.get("contributors", {})
        contributors = {
            "deepSleep": contributors_data.get("deep", None),
            "remSleep": contributors_data.get("rem", None),
            "efficiency": contributors_data.get("efficiency", None),
            "latency": contributors_data.get("latency", None),
            "restfulness": contributors_data.get("restfulness", None),
            "timing": contributors_data.get("timing", None),
            "totalSleep": contributors_data.get("total", None)
        }
        
        # Identify limiting factors (scores < 70)
        limiting_factors = []
        for key, value in contributors.items():
            if value is not None and value < 70:
                limiting_factors.append((key, value))
        
        # Sort by score (lowest first) and extract just the names
        limiting_factors.sort(key=lambda x: x[1])
        limiting_factor_names = [factor[0] for factor in limiting_factors]
        
        # Extract sleep stage durations (in seconds)
        durations = {
            "total": sleep_record.get("total_sleep_duration", 0),
            "deep": sleep_record.get("deep_sleep_duration", 0),
            "rem": sleep_record.get("rem_sleep_duration", 0),
            "light": sleep_record.get("light_sleep_duration", 0),
            "awake": sleep_record.get("awake_time", 0)
        }
        
        # Extract timestamps
        timestamps = {
            "bedtimeStart": sleep_record.get("bedtime_start", None),
            "bedtimeEnd": sleep_record.get("bedtime_end", None)
        }
        
        # Format human-readable summary
        summary = f"Sleep quality: {score}/100"
        if limiting_factors:
            # Show up to 2 limiting factors with their scores
            factors_str = ", ".join([
                f"{_format_contributor_name(f[0])} ({f[1]})" 
                for f in limiting_factors[:2]
            ])
            summary += f". Limited by: {factors_str}"
        
        # Add duration info
        if durations["total"] > 0:
            hours = durations["total"] // 3600
            minutes = (durations["total"] % 3600) // 60
            summary += f" ({hours}h {minutes}m total)"
        
        return {
            "content": [{"type": "text", "text": summary}],
            "structuredContent": {
                "score": score,
                "contributors": contributors,
                "limitingFactors": limiting_factor_names,
                "durations": durations,
                "timestamps": timestamps
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
        "deepSleep": "deep sleep",
        "remSleep": "REM sleep",
        "efficiency": "efficiency",
        "latency": "latency",
        "restfulness": "restfulness",
        "timing": "timing",
        "totalSleep": "total sleep"
    }
    return formatting.get(name, name)