"""MCP Server - 作为 FastAPI sub-application"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import json
import sys, os

sys.path.insert(0, os.path.dirname(__file__))
import mcp_handler

mcp_app = FastAPI(title="MCP Server")

@mcp_app.post("")
async def mcp_endpoint(request: Request):
    body = await request.json()
    result = mcp_handler.handle_mcp_request(body)
    return JSONResponse(content=result)

@mcp_app.get("")
def mcp_info():
    return {
        "server": "jingang-mcp",
        "version": "1.0.0",
        "protocol": "MCP 2024-11-05",
        "tools": list(mcp_handler.TOOLS.keys()),
        "usage": "POST /mcp  with JSON-RPC body"
    }
