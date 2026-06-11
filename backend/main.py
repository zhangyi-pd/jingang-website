import os
import sys
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import threading

sys.path.insert(0, os.path.dirname(__file__))
import database
import deepseek
import knowledge_search
import ai_writer
import scheduler

app = FastAPI(title="金刚般若后台")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).parent.parent

@app.on_event("startup")
def startup():
    database.init_db()
    scheduler.start_scheduler()

app.mount("/admin", StaticFiles(directory=str(BASE_DIR / "admin"), html=True), name="admin")

# ========== 数据模型 ==========
class ArticleIn(BaseModel):
    title: str; summary: str; content: str
class CommentIn(BaseModel):
    article_id: int; author: str; content: str
class ReplyIn(BaseModel):
    reply: str
class LoginIn(BaseModel):
    username: str; password: str
class GenTaskIn(BaseModel):
    topic: str; publish_at: str

def check_auth(request: Request):
    if request.cookies.get("session") != "jingang_admin":
        raise HTTPException(status_code=401, detail="未登录")

# ========== 登录 ==========
@app.post("/api/login")
def login(data: LoginIn):
    conn = database.get_db()
    admin = conn.execute("SELECT * FROM admin WHERE username=? AND password=?", (data.username, data.password)).fetchone()
    conn.close()
    if admin:
        resp = JSONResponse({"ok": True})
        resp.set_cookie("session", "jingang_admin", httponly=True, max_age=86400*7)
        return resp
    raise HTTPException(status_code=401, detail="用户名或密码错误")

@app.post("/api/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("session")
    return resp

# ========== 文章 ==========
@app.get("/api/articles")
def list_articles(published_only: bool = True):
    conn = database.get_db()
    if published_only:
        rows = conn.execute("SELECT id, title, summary, date FROM articles WHERE published=1 ORDER BY date DESC").fetchall()
    else:
        rows = conn.execute("SELECT id, title, summary, date, published FROM articles ORDER BY date DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/articles/{article_id}")
def get_article(article_id: int):
    conn = database.get_db()
    row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
    conn.close()
    if not row: raise HTTPException(status_code=404, detail="文章不存在")
    return dict(row)

@app.post("/api/articles")
def create_article(data: ArticleIn, request: Request):
    check_auth(request)
    conn = database.get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute("INSERT INTO articles (title, summary, content, date) VALUES (?, ?, ?, ?)", (data.title, data.summary, data.content, today))
    conn.commit(); conn.close()
    return {"ok": True}

@app.put("/api/articles/{article_id}")
def update_article(article_id: int, data: ArticleIn, request: Request):
    check_auth(request)
    conn = database.get_db()
    conn.execute("UPDATE articles SET title=?, summary=?, content=? WHERE id=?", (data.title, data.summary, data.content, article_id))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/articles/{article_id}")
def delete_article(article_id: int, request: Request):
    check_auth(request)
    conn = database.get_db()
    conn.execute("DELETE FROM articles WHERE id=?", (article_id,))
    conn.execute("DELETE FROM comments WHERE article_id=?", (article_id,))
    conn.commit(); conn.close()
    return {"ok": True}

# ========== 知识库 ==========
@app.get("/api/knowledge")
def list_knowledge(request: Request):
    check_auth(request)
    return knowledge_search.list_knowledge()

@app.post("/api/knowledge")
def add_knowledge(title: str = Form(...), content: str = Form(...), request: Request = None):
    check_auth(request)
    knowledge_search.add_knowledge(title, content, "text")
    return {"ok": True}

@app.post("/api/knowledge/upload")
def upload_knowledge(file: UploadFile = File(...), request: Request = None):
    check_auth(request)
    content = file.file.read().decode("utf-8", errors="ignore")
    title = file.filename.replace(".txt", "").replace(".md", "")
    knowledge_search.add_knowledge(title, content, "file")
    return {"ok": True, "title": title, "length": len(content)}

@app.delete("/api/knowledge/{kid}")
def delete_knowledge(kid: int, request: Request):
    check_auth(request)
    knowledge_search.delete_knowledge(kid)
    return {"ok": True}

# ========== AI 生成文章 ==========
@app.post("/api/ai/generate")
def ai_generate(data: GenTaskIn, request: Request):
    """生成一篇 AI 文章（不发布，仅预览）"""
    check_auth(request)
    result = ai_writer.generate_article(data.topic)
    parsed = ai_writer.parse_article(result["raw"])
    return {"ok": True, **parsed}

@app.post("/api/ai/publish")
def ai_publish(data: GenTaskIn, request: Request):
    """创建定时发布任务"""
    check_auth(request)
    task_id = scheduler.create_publish_task(data.topic, data.publish_at)
    return {"ok": True, "task_id": task_id}

@app.get("/api/ai/tasks")
def list_tasks(request: Request):
    check_auth(request)
    return scheduler.list_tasks()

@app.delete("/api/ai/tasks/{task_id}")
def delete_task(task_id: int, request: Request):
    check_auth(request)
    scheduler.delete_task(task_id)
    return {"ok": True}

# ========== 评论 ==========
@app.get("/api/comments/{article_id}")
def list_comments(article_id: int):
    conn = database.get_db()
    rows = conn.execute("SELECT * FROM comments WHERE article_id=? ORDER BY created_at DESC", (article_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/comments")
def list_all_comments(request: Request):
    check_auth(request)
    conn = database.get_db()
    rows = conn.execute("SELECT c.*, a.title as article_title FROM comments c LEFT JOIN articles a ON c.article_id = a.id ORDER BY c.created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/comments")
def create_comment(data: CommentIn):
    conn = database.get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cur = conn.execute("INSERT INTO comments (article_id, author, content, created_at) VALUES (?, ?, ?, ?)", (data.article_id, data.author, data.content, now))
    cid = cur.lastrowid; conn.commit()
    # 异步生成 AI 回复
    t = threading.Thread(target=_gen_ai_reply, args=(cid, data.article_id))
    t.start()
    conn.close()
    return {"ok": True, "id": cid}

def _gen_ai_reply(cid, aid):
    try:
        conn = database.get_db()
        a = conn.execute("SELECT * FROM articles WHERE id=?", (aid,)).fetchone()
        c = conn.execute("SELECT * FROM comments WHERE id=?", (cid,)).fetchone()
        if a and c:
            r = deepseek.generate_reply(a["title"], a["content"], c["author"], c["content"])
            conn.execute("UPDATE comments SET ai_reply=? WHERE id=?", (r, cid))
            conn.commit()
        conn.close()
    except: pass

@app.post("/api/comments/{cid}/accept-ai")
def accept_ai_reply(cid: int, request: Request):
    check_auth(request)
    conn = database.get_db()
    c = conn.execute("SELECT * FROM comments WHERE id=?", (cid,)).fetchone()
    if not c: conn.close(); raise HTTPException(status_code=404)
    conn.execute("UPDATE comments SET reply=ai_reply WHERE id=?", (cid,))
    conn.commit(); conn.close()
    return {"ok": True}

@app.post("/api/comments/{cid}/regen-ai")
def regen_ai_reply(cid: int, request: Request):
    check_auth(request)
    conn = database.get_db()
    c = conn.execute("SELECT * FROM comments WHERE id=?", (cid,)).fetchone()
    a = conn.execute("SELECT * FROM articles WHERE id=?", (c["article_id"],)).fetchone()
    conn.close()
    t = threading.Thread(target=_gen_ai_reply, args=(cid, a["id"]))
    t.start()
    return {"ok": True}

@app.put("/api/comments/{cid}/reply")
def reply_comment(cid: int, data: ReplyIn, request: Request):
    check_auth(request)
    conn = database.get_db()
    conn.execute("UPDATE comments SET reply=? WHERE id=?", (data.reply, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/comments/{cid}")
def delete_comment(cid: int, request: Request):
    check_auth(request)
    conn = database.get_db()
    conn.execute("DELETE FROM comments WHERE id=?", (cid,))
    conn.commit(); conn.close()
    return {"ok": True}

# ========== 统计 ==========
@app.get("/api/stats")
def get_stats(request: Request):
    check_auth(request)
    conn = database.get_db()
    ac = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    cc = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    ur = conn.execute("SELECT COUNT(*) FROM comments WHERE reply=''").fetchone()[0]
    kc = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
    pt = conn.execute("SELECT COUNT(*) FROM publish_tasks WHERE status='pending'").fetchone()[0]
    conn.close()
    return {"articles": ac, "comments": cc, "unreplied": ur, "knowledge": kc, "pending_tasks": pt}

@app.get("/")
def index():
    return FileResponse(str(BASE_DIR / "index.html"))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
