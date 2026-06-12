"""MCP Server - 金刚般若网站数据接口

通过 MCP 协议暴露网站数据，让 AI 客户端可以直接访问。

启动方式：
  python mcp_server.py

支持的 MCP 工具：
  - list_articles: 获取文章列表
  - get_article: 获取文章详情
  - search_knowledge: 搜索知识库
  - get_stats: 获取网站统计
"""

import sys
import json
import sqlite3
import os
from datetime import datetime

# ========== 数据库连接 ==========

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "jingang.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ========== 工具函数 ==========

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
    if not row:
        return {"error": "文章不存在"}
    return dict(row)

def search_knowledge(params):
    keyword = params.get("keyword", "")
    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, content, source FROM knowledge WHERE title LIKE ? OR content LIKE ? ORDER BY id DESC",
        (f"%{keyword}%", f"%{keyword}%")
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats(params=None):
    conn = get_db()
    articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    comments = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    knowledge = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
    conn.close()
    return {"articles": articles, "comments": comments, "knowledge": knowledge}

# ========== MCP 协议实现 ==========

TOOLS = {
    "list_articles": {
        "description": "获取网站文章列表，返回标题、摘要和发布日期",
        "handler": list_articles,
        "parameters": {}
    },
    "get_article": {
        "description": "获取单篇文章的完整内容",
        "handler": get_article,
        "parameters": {
            "id": {"type": "integer", "description": "文章 ID", "required": True}
        }
    },
    "search_knowledge": {
        "description": "搜索知识库，找到与关键词相关的佛学素材",
        "handler": search_knowledge,
        "parameters": {
            "keyword": {"type": "string", "description": "搜索关键词", "required": True}
        }
    },
    "get_stats": {
        "description": "获取网站统计数据（文章数、评论数、知识库条数）",
        "handler": get_stats,
        "parameters": {}
    }
}

def handle_request(msg):
    """处理 MCP JSON-RPC 请求"""
    req_id = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params", {})

    if method == "initialize":
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "jingang-mcp", "version": "1.0.0"},
                "capabilities": {
                    "tools": {}
                }
            }
        })

    elif method == "notifications/initialized":
        return None

    elif method == "tools/list":
        tool_list = []
        for name, info in TOOLS.items():
            t = {
                "name": name,
                "description": info["description"],
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
            if info["parameters"]:
                t["inputSchema"]["properties"] = {k: v for k, v in info["parameters"].items() if k != "required"}
                t["inputSchema"]["required"] = [k for k, v in info["parameters"].items() if v.get("required")]
            tool_list.append(t)
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tool_list}
        })

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        tool = TOOLS.get(tool_name)
        if not tool:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"未知工具: {tool_name}"}
            })
        try:
            result = tool["handler"](tool_args)
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]
                }
            })
        except Exception as e:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(e)}
            })

    else:
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"未知方法: {method}"}
        })

def main():
    """主循环：通过 stdin/stdout 与 MCP 客户端通信"""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            response = handle_request(msg)
            if response:
                sys.stdout.write(response + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except EOFError:
            break
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()
