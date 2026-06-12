"""MCP Handler - 处理 MCP JSON-RPC 请求"""
import json
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jingang.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ========== 读工具 ==========

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

# ========== 写工具 ==========

def create_article(params):
    """创建新文章"""
    title = params.get("title", "")
    summary = params.get("summary", "")
    content = params.get("content", "")
    if not title:
        return {"error": "标题不能为空"}
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO articles (title, summary, content, date, published) VALUES (?, ?, ?, ?, 1)",
        (title, summary, content, today)
    )
    article_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"ok": True, "id": article_id, "title": title, "date": today}

def list_comments(params=None):
    """获取所有评论"""
    conn = get_db()
    rows = conn.execute("SELECT c.*, a.title as article_title FROM comments c LEFT JOIN articles a ON c.article_id = a.id ORDER BY c.created_at DESC LIMIT 20").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def reply_comment(params):
    """回复评论"""
    cid = params.get("comment_id")
    reply_text = params.get("reply", "")
    if not cid or not reply_text:
        return {"error": "comment_id 和 reply 不能为空"}
    conn = get_db()
    conn.execute("UPDATE comments SET reply=? WHERE id=?", (reply_text, cid))
    conn.commit()
    conn.close()
    return {"ok": True, "comment_id": cid}

# ========== 工具注册 ==========

TOOLS = {
    # 读工具
    "list_articles": {
        "description": "读取文章列表（返回标题、摘要、日期）",
        "handler": list_articles,
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    "get_article": {
        "description": "读取单篇文章的完整内容",
        "handler": get_article,
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "文章 ID"}},
            "required": ["id"]
        }
    },
    "search_knowledge": {
        "description": "搜索知识库中的佛学素材",
        "handler": search_knowledge,
        "inputSchema": {
            "type": "object",
            "properties": {"keyword": {"type": "string", "description": "搜索关键词"}},
            "required": ["keyword"]
        }
    },
    "get_stats": {
        "description": "获取网站统计数据",
        "handler": get_stats,
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    # 写工具
    "create_article": {
        "description": "创建一篇新文章（需要 title, summary, content）",
        "handler": create_article,
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "文章标题"},
                "summary": {"type": "string", "description": "文章摘要"},
                "content": {"type": "string", "description": "文章正文（支持HTML）"}
            },
            "required": ["title"]
        }
    },
    "list_comments": {
        "description": "获取所有评论列表",
        "handler": list_comments,
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    "reply_comment": {
        "description": "回复某条评论",
        "handler": reply_comment,
        "inputSchema": {
            "type": "object",
            "properties": {
                "comment_id": {"type": "integer", "description": "评论 ID"},
                "reply": {"type": "string", "description": "回复内容"}
            },
            "required": ["comment_id", "reply"]
        }
    }
}

def handle_mcp_request(body):
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
            tools.append({"name": name, "description": info["description"], "inputSchema": info["inputSchema"]})
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
