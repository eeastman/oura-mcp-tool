"""
Oura Trends MCP Tool
Returns multi-day trends for readiness, HRV, body temperature, and sleep quality.
"""

from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from statistics import mean
from .oura_client import OuraAPIClient


def calculate_direction(values: List[float], is_body_temp: bool = False) -> str:
    """
    Calculate trend direction from a list of values.

    Args:
        values: List of numeric values (oldest first)
        is_body_temp: Whether this is body temperature data (special pattern detection)

    Returns:
        Direction string: "rising", "declining", "stable", "elevatedThenRecovering",
        "volatile", or "insufficient_data"
    """
    # Filter out None values for calculation
    valid_values = [v for v in values if v is not None]

    if len(valid_values) < 3:
        return "insufficient_data"

    # For body temperature, check for spike-then-recovery pattern
    if is_body_temp and len(valid_values) >= 4:
        max_val = max(valid_values)
        max_idx = valid_values.index(max_val)
        # Peak in middle third, and latest value significantly lower than peak
        if 1 <= max_idx <= len(valid_values) - 2:
            if valid_values[-1] < max_val * 0.6 or (max_val > 0.3 and valid_values[-1] < 0.2):
                return "elevatedThenRecovering"

    # Calculate first half vs second half averages
    mid = len(valid_values) // 2
    first_half = valid_values[:mid] if mid > 0 else valid_values[:1]
    second_half = valid_values[mid:] if mid > 0 else valid_values[1:]

    first_avg = mean(first_half)
    second_avg = mean(second_half)

    # Avoid division by zero
    if first_avg == 0:
        if second_avg > 0:
            return "rising"
        return "stable"

    change_pct = ((second_avg - first_avg) / abs(first_avg)) * 100

    if change_pct > 5:
        return "rising"
    elif change_pct < -5:
        return "declining"
    else:
        return "stable"


def calculate_change_vs_baseline(current_values: List[float], baseline_values: List[float]) -> Optional[float]:
    """
    Calculate percentage change of current period vs baseline period.

    Args:
        current_values: Recent values (e.g., 7 days)
        baseline_values: Baseline values (e.g., 30 days)

    Returns:
        Percentage change, or None if insufficient data
    """
    valid_current = [v for v in current_values if v is not None]
    valid_baseline = [v for v in baseline_values if v is not None]

    if len(valid_current) < 1 or len(valid_baseline) < 7:
        return None

    current_avg = mean(valid_current)
    baseline_avg = mean(valid_baseline)

    if baseline_avg == 0:
        return None

    return round(((current_avg - baseline_avg) / abs(baseline_avg)) * 100, 1)


async def get_trends_data(oura_token: str, days: int = 7) -> Dict[str, Any]:
    """
    Get health trends over specified number of days.

    Args:
        oura_token: Oura API token
        days: Number of days to analyze (default 7, max 30)

    Returns:
        MCP-formatted response with trend data
    """
    # Clamp days to valid range
    days = max(3, min(30, days))

    # Initialize client
    client = OuraAPIClient(oura_token)

    # Calculate date ranges
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    baseline_start = end_date - timedelta(days=30)

    end_str = end_date.strftime("%Y-%m-%d")
    start_str = start_date.strftime("%Y-%m-%d")
    baseline_start_str = baseline_start.strftime("%Y-%m-%d")

    try:
        # Fetch all data in parallel-ish (async)
        readiness_data = await client.get_daily_readiness_range(baseline_start_str, end_str)
        sleep_summary_data = await client.get_daily_sleep_range(baseline_start_str, end_str)
        sleep_detail_data = await client.get_sleep_range(baseline_start_str, end_str)

        # Check for errors
        for data, name in [(readiness_data, "readiness"), (sleep_summary_data, "sleep"), (sleep_detail_data, "sleep detail")]:
            if data.get("isError"):
                return {
                    "content": [{"type": "text", "text": f"Error fetching {name} data: {data.get('error')}"}],
                    "isError": True
                }

        # Build date list for the requested period
        date_list = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        baseline_date_list = [(baseline_start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]

        # Extract readiness scores and temperature deviations
        readiness_records = {r["day"]: r for r in readiness_data.get("data", [])}
        readiness_values = []
        temp_values = []
        readiness_baseline = []

        for d in date_list:
            record = readiness_records.get(d)
            readiness_values.append(record.get("score") if record else None)
            temp_values.append(record.get("temperature_deviation") if record else None)

        for d in baseline_date_list:
            record = readiness_records.get(d)
            if record and record.get("score") is not None:
                readiness_baseline.append(record["score"])

        # Extract sleep scores
        sleep_records = {r["day"]: r for r in sleep_summary_data.get("data", [])}
        sleep_values = []
        sleep_baseline = []

        for d in date_list:
            record = sleep_records.get(d)
            sleep_values.append(record.get("score") if record else None)

        for d in baseline_date_list:
            record = sleep_records.get(d)
            if record and record.get("score") is not None:
                sleep_baseline.append(record["score"])

        # Extract HRV from detailed sleep (use long_sleep type only)
        sleep_detail_records = {}
        for r in sleep_detail_data.get("data", []):
            day = r.get("day")
            # Prefer long_sleep type
            if day not in sleep_detail_records or r.get("type") == "long_sleep":
                if r.get("type") == "long_sleep" or sleep_detail_records.get(day, {}).get("type") != "long_sleep":
                    sleep_detail_records[day] = r

        hrv_values = []
        hrv_baseline = []

        for d in date_list:
            record = sleep_detail_records.get(d)
            hrv_values.append(record.get("average_hrv") if record else None)

        for d in baseline_date_list:
            record = sleep_detail_records.get(d)
            if record and record.get("average_hrv") is not None:
                hrv_baseline.append(record["average_hrv"])

        # Calculate directions and averages
        valid_readiness = [v for v in readiness_values if v is not None]
        valid_hrv = [v for v in hrv_values if v is not None]
        valid_temp = [v for v in temp_values if v is not None]
        valid_sleep = [v for v in sleep_values if v is not None]

        readiness_avg = round(mean(valid_readiness)) if valid_readiness else None
        hrv_avg = round(mean(valid_hrv)) if valid_hrv else None
        sleep_avg = round(mean(valid_sleep)) if valid_sleep else None

        # Build structured response
        result = {
            "readiness": {
                "values": readiness_values,
                "direction": calculate_direction(readiness_values),
                "average": readiness_avg,
                "changeVsBaseline": calculate_change_vs_baseline(readiness_values, readiness_baseline)
            },
            "hrv": {
                "values": hrv_values,
                "direction": calculate_direction(hrv_values),
                "average": hrv_avg,
                "changeVsBaseline": calculate_change_vs_baseline(hrv_values, hrv_baseline)
            },
            "bodyTemperature": {
                "values": temp_values,
                "direction": calculate_direction(temp_values, is_body_temp=True),
                "latest": temp_values[-1] if temp_values else None
            },
            "sleepScore": {
                "values": sleep_values,
                "direction": calculate_direction(sleep_values),
                "average": sleep_avg,
                "changeVsBaseline": calculate_change_vs_baseline(sleep_values, sleep_baseline)
            },
            "period": {
                "days": days,
                "startDate": start_str,
                "endDate": end_str
            }
        }

        # Build human-readable summary
        summary_parts = [f"{days}-day trends:"]

        if readiness_avg is not None:
            baseline_str = f" ({result['readiness']['changeVsBaseline']:+.0f}% vs baseline)" if result['readiness']['changeVsBaseline'] is not None else ""
            summary_parts.append(f"Readiness {result['readiness']['direction']} at {readiness_avg} avg{baseline_str}.")

        if hrv_avg is not None:
            baseline_str = f" ({result['hrv']['changeVsBaseline']:+.0f}% vs baseline)" if result['hrv']['changeVsBaseline'] is not None else ""
            summary_parts.append(f"HRV {result['hrv']['direction']} at {hrv_avg} avg{baseline_str}.")

        if result['bodyTemperature']['direction'] != "insufficient_data":
            if result['bodyTemperature']['direction'] == "elevatedThenRecovering":
                summary_parts.append("Body temp recovering after elevation.")
            elif result['bodyTemperature']['latest'] is not None:
                summary_parts.append(f"Body temp {result['bodyTemperature']['direction']} (latest: {result['bodyTemperature']['latest']:+.1f}°).")

        if sleep_avg is not None:
            baseline_str = f" ({result['sleepScore']['changeVsBaseline']:+.0f}% vs baseline)" if result['sleepScore']['changeVsBaseline'] is not None else ""
            summary_parts.append(f"Sleep {result['sleepScore']['direction']} at {sleep_avg} avg{baseline_str}.")

        summary = " ".join(summary_parts)

        return {
            "content": [{"type": "text", "text": summary}],
            "structuredContent": result,
            "isError": False
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "isError": True
        }
