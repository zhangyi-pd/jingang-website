"""知识库管理模块 - 支持文件存储（持久化）+ SQLite（运行时）"""
import database
import os
from datetime import datetime

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")

def load_from_files():
    """从 knowledge/ 目录加载知识到数据库"""
    if not os.path.exists(KNOWLEDGE_DIR):
        return
    conn = database.get_db()
    existing = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
    if existing > 0:
        conn.close()
        return  # 已有数据，不覆盖
    
    for fname in sorted(os.listdir(KNOWLEDGE_DIR)):
        if fname.endswith((".md", ".txt")):
            fpath = os.path.join(KNOWLEDGE_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read().strip()
            title = fname.replace(".md", "").replace(".txt", "")
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            conn.execute(
                "INSERT INTO knowledge (title, content, source, created_at) VALUES (?, ?, 'file', ?)",
                (title, content, now)
            )
    conn.commit()
    conn.close()

def save_to_file(title, content):
    """保存一条知识到文件（持久化）"""
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    # 文件名用标题，去除非文件名字符
    safe_name = "".join(c for c in title if c.isalnum() or c in " _-（()）").strip() or "知识"
    fpath = os.path.join(KNOWLEDGE_DIR, safe_name + ".md")
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{content}\n")
    return fpath

def delete_file(title):
    """删除对应的知识文件"""
    safe_name = "".join(c for c in title if c.isalnum() or c in " _-（()）").strip() or "知识"
    fpath = os.path.join(KNOWLEDGE_DIR, safe_name + ".md")
    if os.path.exists(fpath):
        os.remove(fpath)
        return True
    return False

def sync_files():
    """返回所有知识文件列表"""
    if not os.path.exists(KNOWLEDGE_DIR):
        return []
    files = []
    for fname in sorted(os.listdir(KNOWLEDGE_DIR)):
        if fname.endswith((".md", ".txt")):
            fpath = os.path.join(KNOWLEDGE_DIR, fname)
            files.append({
                "name": fname,
                "size": os.path.getsize(fpath),
                "path": fpath
            })
    return files

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

def add_knowledge(title, content, source="file"):
    conn = database.get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute(
        "INSERT INTO knowledge (title, content, source, created_at) VALUES (?, ?, ?, ?)",
        (title, content, source, now)
    )
    conn.commit()
    conn.close()
    # 同时保存到文件（持久化）
    if source != "file":
        save_to_file(title, content)

def delete_knowledge(id):
    conn = database.get_db()
    row = conn.execute("SELECT title FROM knowledge WHERE id=?", (id,)).fetchone()
    if row:
        delete_file(row["title"])
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
