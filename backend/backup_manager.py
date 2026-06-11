"""自动备份恢复模块 - 数据持久化到 GitHub"""
import json
import os
import base64
import urllib.request
import urllib.error
import database

def get_token():
    """从环境变量读取 GitHub Token"""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        # 启动时不报错，只是不备份
        return None
    return token

OWNER = "zhangyi-pd"
REPO = "jingang-website"
BRANCH = "master"
BACKUP_PATH = "data/backup.json"

def _github_api(method, api_path, data=None):
    token = get_token()
    if not token:
        return None
    url = f"https://api.github.com{api_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "jingang-backup",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json"
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except:
        return None

def export_db():
    conn = database.get_db()
    data = {
        "articles": [dict(r) for r in conn.execute("SELECT * FROM articles").fetchall()],
        "comments": [dict(r) for r in conn.execute("SELECT * FROM comments").fetchall()],
        "knowledge": [dict(r) for r in conn.execute("SELECT * FROM knowledge").fetchall()],
        "publish_tasks": [dict(r) for r in conn.execute("SELECT * FROM publish_tasks").fetchall()]
    }
    conn.close()
    return data

def import_db(data):
    conn = database.get_db()
    try:
        for table in ["articles", "comments", "knowledge", "publish_tasks"]:
            conn.execute(f"DELETE FROM {table}")
        for a in data.get("articles", []):
            conn.execute("INSERT INTO articles VALUES (?,?,?,?,?,?,?)", (a.get("id"), a.get("title",""), a.get("summary",""), a.get("content",""), a.get("date",""), a.get("published",1), a.get("status","published")))
        for c in data.get("comments", []):
            conn.execute("INSERT INTO comments VALUES (?,?,?,?,?,?,?)", (c.get("id"), c.get("article_id"), c.get("author","同修"), c.get("content",""), c.get("reply",""), c.get("ai_reply",""), c.get("created_at","")))
        for k in data.get("knowledge", []):
            conn.execute("INSERT INTO knowledge VALUES (?,?,?,?,?)", (k.get("id"), k.get("title",""), k.get("content",""), k.get("source","text"), k.get("created_at","")))
        for t in data.get("publish_tasks", []):
            conn.execute("INSERT INTO publish_tasks VALUES (?,?,?,?,?,?,?,?,?)", (t.get("id"), t.get("topic",""), t.get("title",""), t.get("content",""), t.get("summary",""), t.get("status","pending"), t.get("publish_at",""), t.get("created_at",""), t.get("published_at","")))
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        conn.close()

def save_to_github():
    if not get_token(): return False
    data = export_db()
    content = json.dumps(data, ensure_ascii=False, indent=2)
    existing = _github_api("GET", f"/repos/{OWNER}/{REPO}/contents/{BACKUP_PATH}?ref={BRANCH}")
    sha = existing.get("sha") if existing and isinstance(existing, dict) else None
    body = {"message": "auto backup database", "content": base64.b64encode(content.encode("utf-8")).decode("ascii"), "branch": BRANCH}
    if sha: body["sha"] = sha
    result = _github_api("PUT", f"/repos/{OWNER}/{REPO}/contents/{BACKUP_PATH}", body)
    return result is not None

def load_from_github():
    if not get_token(): return False
    result = _github_api("GET", f"/repos/{OWNER}/{REPO}/contents/{BACKUP_PATH}?ref={BRANCH}")
    if not result or not isinstance(result, dict) or "content" not in result: return False
    try:
        data = json.loads(base64.b64decode(result["content"]).decode("utf-8"))
        return import_db(data)
    except:
        return False

def auto_restore():
    return load_from_github()

def auto_backup():
    save_to_github()
