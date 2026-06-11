"""知识库搜索模块"""
import database

def search_knowledge(keyword, limit=5):
    conn = database.get_db()
    rows = conn.execute(
        "SELECT id, title, content, source FROM knowledge WHERE title LIKE ? OR content LIKE ? ORDER BY id DESC LIMIT ?",
        (f"%{keyword}%", f"%{keyword}%", limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def list_knowledge():
    conn = database.get_db()
    rows = conn.execute("SELECT id, title, content, source, created_at FROM knowledge ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_knowledge(title, content, source="text"):
    conn = database.get_db()
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute(
        "INSERT INTO knowledge (title, content, source, created_at) VALUES (?, ?, ?, ?)",
        (title, content, source, now)
    )
    conn.commit()
    conn.close()

def delete_knowledge(id):
    conn = database.get_db()
    conn.execute("DELETE FROM knowledge WHERE id=?", (id,))
    conn.commit()
    conn.close()

def build_search_context(topic):
    results = search_knowledge(topic, limit=8)
    if not results:
        return ""
    context = "以下是知识库中与该主题相关的内容：\n\n"
    for r in results:
        context += f"--- {r['title']} ---\n{r['content'][:300]}\n\n"
    return context
