"""MCP Server - HTTP 模式（用于部署到 Railway）"""
import json
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jingang.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def list_articles(params=None):
    conn = get_db()
    rows = conn.execute("SELECT id, title, summary, date FROM articles WHERE published=1 ORDER BY date DESC LIMIT 20").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_article(params):
    aid = params.get("id", 1)
    conn = get_db()
    row = conn.execute("SELECT id, title, summary, content, date FROM articles WHERE id=?", (aid,)).fetchone()
    conn.close()
    if not row: return {"error": "文章不存在"}
    return dict(row)

def search_knowledge(params):
    kw = params.get("keyword", "")
    conn = get_db()
    rows = conn.execute("SELECT id, title, content, source FROM knowledge WHERE title LIKE ? OR content LIKE ? ORDER BY id DESC", (f"%{kw}%", f"%{kw}%")).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats(params=None):
    conn = get_db()
    a = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    c = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    k = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
    conn.close()
    return {"articles": a, "comments": c, "knowledge": k}

TOOLS = {
    "list_articles": {
        "description": "获取网站文章列表，返回标题、摘要和发布日期",
        "handler": list_articles,
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    "get_article": {
        "description": "获取单篇文章的完整内容",
        "handler": get_article,
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "文章 ID"}},
            "required": ["id"]
        }
    },
    "search_knowledge": {
        "description": "搜索知识库，找到与关键词相关的佛学素材",
        "handler": search_knowledge,
        "inputSchema": {
            "type": "object",
            "properties": {"keyword": {"type": "string", "description": "搜索关键词"}},
            "required": ["keyword"]
        }
    },
    "get_stats": {
        "description": "获取网站统计数据（文章数、评论数、知识库条数）",
        "handler": get_stats,
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    }
}

def handle_mcp_request(body):
    """处理 MCP JSON-RPC 请求，返回响应"""
    req_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "jingang-mcp", "version": "1.0.0"},
                "capabilities": {"tools": {}}
            }
        }
    elif method == "tools/list":
        tools = []
        for name, info in TOOLS.items():
            tools.append({
                "name": name,
                "description": info["description"],
                "inputSchema": info["inputSchema"]
            })
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}
    elif method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})
        tool = TOOLS.get(tool_name)
        if not tool:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"未知工具: {tool_name}"}}
        try:
            result = tool["handler"](args)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}
            }
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}
    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"未知方法: {method}"}}
