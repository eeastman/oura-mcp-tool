"""
Oura Stress and Resilience MCP Tool
"""

import os
import sys
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import json

# Import our modules
try:
    # Try absolute import first (for when running as python main.py)
    from src.auth.oauth_server import setup_oauth_routes, validate_token, storage
    from src.tools.stress_resilience import get_stress_and_resilience_data as get_stress_resilience
    from src.tools.readiness import get_readiness_data
    from src.tools.sleep_quality import get_sleep_quality_data
    from src.tools.trends import get_trends_data
except ImportError:
    # Fall back to relative import (for when running as python src/oura_tool.py)
    from auth.oauth_server import setup_oauth_routes, validate_token, storage
    from tools.stress_resilience import get_stress_and_resilience_data as get_stress_resilience
    from tools.readiness import get_readiness_data
    from tools.sleep_quality import get_sleep_quality_data
    from tools.trends import get_trends_data

# Load environment variables
load_dotenv()

# Configuration

# Server configuration
PORT = int(os.environ.get("PORT", 8080))

# Initialize FastAPI app
app = FastAPI(title="Oura Stress & Resilience Tool")

# CORS setup per Dreamer requirements
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)

# Setup OAuth routes from our auth module
setup_oauth_routes(app)

# MCP Tool Implementation

async def get_stress_and_resilience_data(user_id: str, date_param: Optional[str] = None) -> dict:
    """Get stress and resilience data for user"""
    
    # Get user's Oura token from storage
    user_data = await storage.user_tokens.get(user_id)
    if not user_data:
        return {
            "content": [{"type": "text", "text": "User not found"}],
            "isError": True
        }
    
    oura_token = user_data["oura_token"]
    
    # Call the imported function
    return await get_stress_resilience(oura_token, date_param)

async def get_readiness(user_id: str, date_param: Optional[str] = None) -> dict:
    """Get readiness data for user"""

    # Get user's Oura token from storage
    user_data = await storage.user_tokens.get(user_id)
    if not user_data:
        return {
            "content": [{"type": "text", "text": "User not found"}],
            "isError": True
        }

    oura_token = user_data["oura_token"]

    # Call the imported function
    return await get_readiness_data(oura_token, date_param)

async def get_sleep_quality(user_id: str, date_param: Optional[str] = None) -> dict:
    """Get sleep quality data for user"""

    # Get user's Oura token from storage
    user_data = await storage.user_tokens.get(user_id)
    if not user_data:
        return {
            "content": [{"type": "text", "text": "User not found"}],
            "isError": True
        }

    oura_token = user_data["oura_token"]

    # Call the imported function
    return await get_sleep_quality_data(oura_token, date_param)

async def get_trends(user_id: str, days: int = 7) -> dict:
    """Get health trends for user over multiple days"""

    # Get user's Oura token from storage
    user_data = await storage.user_tokens.get(user_id)
    if not user_data:
        return {
            "content": [{"type": "text", "text": "User not found"}],
            "isError": True
        }

    oura_token = user_data["oura_token"]

    # Call the imported function
    return await get_trends_data(oura_token, days)

# MCP endpoint info
@app.get("/mcp")
async def mcp_info():
    """MCP endpoint - return tools list for GET requests"""
    # Some MCP clients do GET first to check available tools
    return {
        "tools": [{
            "name": "get_stress_and_resilience",
            "description": "Get stress and resilience data for a specific date",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "date_param": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (defaults to today)"
                    }
                }
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format"
                    },
                    "stress": {
                        "type": "object",
                        "properties": {
                            "highStressSeconds": {
                                "type": "integer",
                                "description": "Time spent in high stress (seconds)"
                            },
                            "recoverySeconds": {
                                "type": "integer",
                                "description": "Time spent in recovery (seconds)"
                            },
                            "ratio": {
                                "type": ["number", "null"],
                                "description": "Stress to recovery ratio"
                            }
                        },
                        "required": ["highStressSeconds", "recoverySeconds"]
                    },
                    "resilience": {
                        "type": "object",
                        "properties": {
                            "level": {
                                "type": "string",
                                "description": "Resilience level (e.g., solid, limited)"
                            },
                            "contributors": {
                                "type": "object",
                                "properties": {
                                    "sleepRecovery": {"type": "number"},
                                    "daytimeRecovery": {"type": "number"},
                                    "stress": {"type": "number"}
                                },
                                "description": "Contributing factors to resilience"
                            }
                        },
                        "required": ["level"]
                    }
                },
                "required": ["date", "stress", "resilience"]
            }
        }, {
            "name": "get_readiness",
            "description": "Get readiness score and contributors for a specific date",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "date_param": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (defaults to today)"
                    }
                }
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "score": {
                        "type": "integer",
                        "description": "Overall readiness score (0-100)"
                    },
                    "contributors": {
                        "type": "object",
                        "properties": {
                            "hrvBalance": {"type": ["integer", "null"]},
                            "bodyTemperature": {"type": ["integer", "null"]},
                            "recoveryIndex": {"type": ["integer", "null"]},
                            "restingHeartRate": {"type": ["integer", "null"]},
                            "sleepBalance": {"type": ["integer", "null"]},
                            "previousNight": {"type": ["integer", "null"]},
                            "previousDayActivity": {"type": ["integer", "null"]},
                            "activityBalance": {"type": ["integer", "null"]}
                        },
                        "description": "Individual readiness contributors (0-100)"
                    },
                    "limitingFactors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Contributors with scores < 70"
                    },
                    "timestamp": {
                        "type": "string",
                        "format": "date-time",
                        "description": "When readiness was calculated"
                    }
                },
                "required": ["score", "contributors", "limitingFactors", "timestamp"]
            }
        }, {
            "name": "get_sleep_quality",
            "description": "Get sleep quality score and detailed sleep metrics for a specific date",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "date_param": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (defaults to today)"
                    }
                }
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "score": {
                        "type": "integer",
                        "description": "Overall sleep quality score (0-100)"
                    },
                    "contributors": {
                        "type": "object",
                        "properties": {
                            "deepSleep": {"type": ["integer", "null"]},
                            "remSleep": {"type": ["integer", "null"]},
                            "efficiency": {"type": ["integer", "null"]},
                            "latency": {"type": ["integer", "null"]},
                            "restfulness": {"type": ["integer", "null"]},
                            "timing": {"type": ["integer", "null"]},
                            "totalSleep": {"type": ["integer", "null"]}
                        },
                        "description": "Individual sleep quality contributors (0-100)"
                    },
                    "limitingFactors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Contributors with scores < 70"
                    },
                    "durations": {
                        "type": "object",
                        "properties": {
                            "total": {"type": "integer", "description": "Total sleep duration in seconds"},
                            "deep": {"type": "integer", "description": "Deep sleep duration in seconds"},
                            "rem": {"type": "integer", "description": "REM sleep duration in seconds"},
                            "light": {"type": "integer", "description": "Light sleep duration in seconds"},
                            "awake": {"type": "integer", "description": "Awake duration in seconds"}
                        }
                    },
                    "timestamps": {
                        "type": "object",
                        "properties": {
                            "bedtimeStart": {
                                "type": ["string", "null"],
                                "format": "date-time",
                                "description": "When bedtime started"
                            },
                            "bedtimeEnd": {
                                "type": ["string", "null"],
                                "format": "date-time",
                                "description": "When bedtime ended"
                            }
                        }
                    }
                },
                "required": ["score", "contributors", "limitingFactors", "durations", "timestamps"]
            }
        }]
    }

# MCP OPTIONS for CORS
@app.options("/mcp")
async def mcp_options():
    """Handle OPTIONS requests for CORS"""
    return Response(
        content="",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Mcp-Session-Id",
            "Access-Control-Expose-Headers": "Mcp-Session-Id",
            "Access-Control-Max-Age": "86400"
        }
    )

# Protected MCP endpoint
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP endpoint with OAuth protection"""
    print("=== MCP ENDPOINT CALLED ===")
    print(f"Headers: {dict(request.headers)}")
    
    # Validate OAuth token
    try:
        token_data = await validate_token(request)
        print(f"Token validated for user: {token_data.get('user_id')}")
    except HTTPException as e:
        print(f"Token validation failed: {e.detail}")
        raise
    
    try:
        # Parse MCP request
        body = await request.body()
        body_str = body.decode()
        print(f"MCP request body: {body_str}")
        
        # Handle empty body case
        if not body_str:
            print("Empty body received, returning error")
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error: Empty request body"}
                },
                headers={"Content-Type": "application/json"},
                status_code=400
            )
        
        try:
            mcp_request = json.loads(body_str)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                },
                headers={"Content-Type": "application/json"},
                status_code=400
            )
        
        method = mcp_request.get("method")
        print(f"MCP method: {method}")

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": mcp_request.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "oura-stress-resilience", "version": "1.0.0"}
                }
            }
            return JSONResponse(content=response, headers={"Content-Type": "application/json"})
        
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": mcp_request.get("id"),
                "result": {
                    "tools": [{
                        "name": "get_stress_and_resilience",
                        "description": "Get stress and resilience data for a specific date",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "date_param": {
                                    "type": "string",
                                    "description": "Date in YYYY-MM-DD format (defaults to today)"
                                }
                            }
                        },
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "date": {
                                    "type": "string",
                                    "description": "Date in YYYY-MM-DD format"
                                },
                                "stress": {
                                    "type": "object",
                                    "properties": {
                                        "highStressSeconds": {
                                            "type": "integer",
                                            "description": "Time spent in high stress (seconds)"
                                        },
                                        "recoverySeconds": {
                                            "type": "integer",
                                            "description": "Time spent in recovery (seconds)"
                                        },
                                        "ratio": {
                                            "type": ["number", "null"],
                                            "description": "Stress to recovery ratio"
                                        }
                                    },
                                    "required": ["highStressSeconds", "recoverySeconds"]
                                },
                                "resilience": {
                                    "type": "object",
                                    "properties": {
                                        "level": {
                                            "type": "string",
                                            "description": "Resilience level (e.g., solid, limited)"
                                        },
                                        "contributors": {
                                            "type": "object",
                                            "properties": {
                                                "sleepRecovery": {"type": "number"},
                                                "daytimeRecovery": {"type": "number"},
                                                "stress": {"type": "number"}
                                            },
                                            "description": "Contributing factors to resilience"
                                        }
                                    },
                                    "required": ["level"]
                                }
                            },
                            "required": ["date", "stress", "resilience"]
                        }
                    }, {
                        "name": "get_readiness",
                        "description": "Get readiness score and contributors for a specific date",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "date_param": {
                                    "type": "string",
                                    "description": "Date in YYYY-MM-DD format (defaults to today)"
                                }
                            }
                        },
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "score": {
                                    "type": "integer",
                                    "description": "Overall readiness score (0-100)"
                                },
                                "contributors": {
                                    "type": "object",
                                    "properties": {
                                        "hrvBalance": {"type": ["integer", "null"]},
                                        "bodyTemperature": {"type": ["integer", "null"]},
                                        "recoveryIndex": {"type": ["integer", "null"]},
                                        "restingHeartRate": {"type": ["integer", "null"]},
                                        "sleepBalance": {"type": ["integer", "null"]},
                                        "previousNight": {"type": ["integer", "null"]},
                                        "previousDayActivity": {"type": ["integer", "null"]},
                                        "activityBalance": {"type": ["integer", "null"]}
                                    },
                                    "description": "Individual readiness contributors (0-100)"
                                },
                                "limitingFactors": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Contributors with scores < 70"
                                },
                                "timestamp": {
                                    "type": "string",
                                    "format": "date-time",
                                    "description": "When readiness was calculated"
                                }
                            },
                            "required": ["score", "contributors", "limitingFactors", "timestamp"]
                        }
                    }, {
                        "name": "get_sleep_quality",
                        "description": "Get sleep quality score and detailed sleep metrics for a specific date",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "date_param": {
                                    "type": "string",
                                    "description": "Date in YYYY-MM-DD format (defaults to today)"
                                }
                            }
                        },
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "score": {
                                    "type": "integer",
                                    "description": "Overall sleep quality score (0-100)"
                                },
                                "contributors": {
                                    "type": "object",
                                    "properties": {
                                        "deepSleep": {"type": ["integer", "null"]},
                                        "remSleep": {"type": ["integer", "null"]},
                                        "efficiency": {"type": ["integer", "null"]},
                                        "latency": {"type": ["integer", "null"]},
                                        "restfulness": {"type": ["integer", "null"]},
                                        "timing": {"type": ["integer", "null"]},
                                        "totalSleep": {"type": ["integer", "null"]}
                                    },
                                    "description": "Individual sleep quality contributors (0-100)"
                                },
                                "limitingFactors": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Contributors with scores < 70"
                                },
                                "durations": {
                                    "type": "object",
                                    "properties": {
                                        "total": {"type": "integer", "description": "Total sleep duration in seconds"},
                                        "deep": {"type": "integer", "description": "Deep sleep duration in seconds"},
                                        "rem": {"type": "integer", "description": "REM sleep duration in seconds"},
                                        "light": {"type": "integer", "description": "Light sleep duration in seconds"},
                                        "awake": {"type": "integer", "description": "Awake duration in seconds"}
                                    }
                                },
                                "timestamps": {
                                    "type": "object",
                                    "properties": {
                                        "bedtimeStart": {
                                            "type": ["string", "null"],
                                            "format": "date-time",
                                            "description": "When bedtime started"
                                        },
                                        "bedtimeEnd": {
                                            "type": ["string", "null"],
                                            "format": "date-time",
                                            "description": "When bedtime ended"
                                        }
                                    }
                                }
                            },
                            "required": ["score", "contributors", "limitingFactors", "durations", "timestamps"]
                        }
                    }, {
                        "name": "get_trends",
                        "description": "Get 7-day health trends for readiness, HRV, body temperature, and sleep quality with direction analysis",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "days": {
                                    "type": "integer",
                                    "description": "Number of days to analyze (default 7, min 3, max 30)",
                                    "default": 7,
                                    "minimum": 3,
                                    "maximum": 30
                                }
                            }
                        },
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "readiness": {
                                    "type": "object",
                                    "properties": {
                                        "values": {"type": "array", "items": {"type": ["integer", "null"]}},
                                        "direction": {"type": "string", "enum": ["rising", "declining", "stable", "insufficient_data"]},
                                        "average": {"type": ["integer", "null"]},
                                        "changeVsBaseline": {"type": ["number", "null"], "description": "Percentage change vs 30-day baseline"}
                                    }
                                },
                                "hrv": {
                                    "type": "object",
                                    "properties": {
                                        "values": {"type": "array", "items": {"type": ["integer", "null"]}},
                                        "direction": {"type": "string", "enum": ["rising", "declining", "stable", "insufficient_data"]},
                                        "average": {"type": ["integer", "null"]},
                                        "changeVsBaseline": {"type": ["number", "null"]}
                                    }
                                },
                                "bodyTemperature": {
                                    "type": "object",
                                    "properties": {
                                        "values": {"type": "array", "items": {"type": ["number", "null"]}},
                                        "direction": {"type": "string", "enum": ["rising", "declining", "stable", "elevatedThenRecovering", "insufficient_data"]},
                                        "latest": {"type": ["number", "null"], "description": "Latest temperature deviation from baseline"}
                                    }
                                },
                                "sleepScore": {
                                    "type": "object",
                                    "properties": {
                                        "values": {"type": "array", "items": {"type": ["integer", "null"]}},
                                        "direction": {"type": "string", "enum": ["rising", "declining", "stable", "insufficient_data"]},
                                        "average": {"type": ["integer", "null"]},
                                        "changeVsBaseline": {"type": ["number", "null"]}
                                    }
                                },
                                "period": {
                                    "type": "object",
                                    "properties": {
                                        "days": {"type": "integer"},
                                        "startDate": {"type": "string", "format": "date"},
                                        "endDate": {"type": "string", "format": "date"}
                                    }
                                }
                            },
                            "required": ["readiness", "hrv", "bodyTemperature", "sleepScore", "period"]
                        }
                    }]
                }
            }
            return JSONResponse(content=response, headers={"Content-Type": "application/json"})

        elif method == "tools/call":
            params = mcp_request.get("params", {})
            if params.get("name") == "get_stress_and_resilience":
                args = params.get("arguments", {})
                result = await get_stress_and_resilience_data(
                    user_id=token_data["user_id"],
                    date_param=args.get("date_param")
                )
                
                
                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": mcp_request.get("id"),
                        "result": result
                    },
                    headers={"Content-Type": "application/json"}
                )
            elif params.get("name") == "get_readiness":
                args = params.get("arguments", {})
                result = await get_readiness(
                    user_id=token_data["user_id"],
                    date_param=args.get("date_param")
                )

                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": mcp_request.get("id"),
                        "result": result
                    },
                    headers={"Content-Type": "application/json"}
                )
            elif params.get("name") == "get_sleep_quality":
                args = params.get("arguments", {})
                result = await get_sleep_quality(
                    user_id=token_data["user_id"],
                    date_param=args.get("date_param")
                )

                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": mcp_request.get("id"),
                        "result": result
                    },
                    headers={"Content-Type": "application/json"}
                )
            elif params.get("name") == "get_trends":
                args = params.get("arguments", {})
                result = await get_trends(
                    user_id=token_data["user_id"],
                    days=args.get("days", 7)
                )

                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": mcp_request.get("id"),
                        "result": result
                    },
                    headers={"Content-Type": "application/json"}
                )

        # Unknown method
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": mcp_request.get("id"),
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            },
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        print(f"MCP error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": mcp_request.get("id") if 'mcp_request' in locals() else None,
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
            },
            headers={"Content-Type": "application/json"}
        )

# MCP at root path for Dreamer compatibility
@app.post("/")
async def root_mcp_endpoint(request: Request):
    """Handle MCP requests at root path (Dreamer uses this)"""
    return await mcp_endpoint(request)

# Health check
@app.get("/health")
async def health():
    """Health check"""
    # Since storage is async, we can't easily count items
    # Just return basic health status
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "storage": "persistent",
        "storage_type": os.getenv('STORAGE_TYPE', 'sqlite')
    }


# Test endpoints for development
@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "service": "Oura Stress & Resilience Tool",
        "version": "1.0.0",
        "endpoints": {
            "oauth_metadata": "/.well-known/oauth-authorization-server",
            "resource_metadata": "/.well-known/oauth-protected-resource",
            "mcp": "/mcp",
            "health": "/health"
        }
    }

# Catch-all route for debugging
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all(request: Request, path: str):
    """Log all unhandled requests for debugging"""
    print(f"=== UNHANDLED REQUEST ===")
    print(f"Path: /{path}")
    print(f"Method: {request.method}")
    print(f"Headers: {dict(request.headers)}")
    if request.method in ["POST", "PUT"]:
        try:
            body = await request.body()
            print(f"Body: {body.decode()}")
        except:
            pass
    raise HTTPException(status_code=404, detail=f"Path not found: /{path}")


def main():
    """Run the server"""
    import uvicorn
    
    print(f"Starting Oura Stress & Resilience Tool on port {PORT}")
    print(f"Base URL: http://localhost:{PORT}")
    print("\nOAuth Endpoints:")
    print(f"  Metadata: http://localhost:{PORT}/.well-known/oauth-authorization-server")
    print(f"  Authorization: http://localhost:{PORT}/oauth/authorize")
    print(f"  Token: http://localhost:{PORT}/oauth/token")
    print(f"  Registration: http://localhost:{PORT}/oauth/register")
    print(f"\nMCP Endpoint: http://localhost:{PORT}/mcp")
    print(f"Health Check: http://localhost:{PORT}/health")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()