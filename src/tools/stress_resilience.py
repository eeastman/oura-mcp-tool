"""
Oura Stress and Resilience MCP Tool
"""

from datetime import datetime, date
from typing import Optional, Dict, Any
from .oura_client import OuraAPIClient

async def get_stress_and_resilience_data(oura_token: str, date_param: Optional[str] = None) -> Dict[str, Any]:
    """
    Get stress and resilience data for a specific date
    
    Args:
        oura_token: Oura API token
        date_param: Date in YYYY-MM-DD format (defaults to today)
        
    Returns:
        MCP-formatted response with stress and resilience data
    """
    # Initialize client
    client = OuraAPIClient(oura_token)
    
    # Use provided date or today
    target_date = date_param or date.today().strftime("%Y-%m-%d")
    
    try:
        # Validate date format
        datetime.strptime(target_date, "%Y-%m-%d")
        
        # Fetch data in parallel
        stress_data = await client.get_daily_stress(target_date)
        resilience_data = await client.get_daily_resilience(target_date)
        
        # Check for errors
        if stress_data.get("isError"):
            return {
                "content": [{"type": "text", "text": f"Error: {stress_data['error']}"}],
                "isError": True
            }
        
        if resilience_data.get("isError"):
            return {
                "content": [{"type": "text", "text": f"Error: {resilience_data['error']}"}],
                "isError": True
            }
        
        # Process data
        stress_records = stress_data.get("data", [])
        resilience_records = resilience_data.get("data", [])
        
        stress_record = next((r for r in stress_records if r.get("day") == target_date), None)
        resilience_record = next((r for r in resilience_records if r.get("day") == target_date), None)
        
        if not stress_record:
            return {
                "content": [{"type": "text", "text": f"No data found for {target_date}"}],
                "isError": True
            }
        
        # Calculate stress metrics
        high_stress = stress_record.get("stress_high", 0)
        recovery = stress_record.get("recovery_high", 0)
        ratio = high_stress / recovery if recovery > 0 else float('inf')
        
        # Process resilience
        resilience_result = None
        if resilience_record:
            contributors = resilience_record.get("contributors", {})
            resilience_result = {
                "level": resilience_record.get("level", "unknown"),
                "contributors": {
                    "sleepRecovery": contributors.get("sleep_recovery", 0),
                    "daytimeRecovery": contributors.get("daytime_recovery", 0),
                    "stress": contributors.get("stress", 0)
                }
            }
        
        # Format response
        stress_formatted = _format_duration(high_stress)
        recovery_formatted = _format_duration(recovery)
        summary = f"Stress: {stress_formatted}, Recovery: {recovery_formatted}"
        if ratio != float('inf'):
            summary += f" (ratio: {ratio:.1f}:1)"
        
        return {
            "content": [{"type": "text", "text": summary}],
            "structuredContent": {
                "date": target_date,
                "stress": {
                    "highStressSeconds": high_stress,
                    "recoverySeconds": recovery,
                    "ratio": ratio if ratio != float('inf') else None
                },
                "resilience": resilience_result
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

def _format_duration(seconds: int) -> str:
    """Format duration from seconds to human-readable string"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    if hours > 0 and minutes > 0:
        return f"{hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return "0m"