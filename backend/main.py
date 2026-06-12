import os
import sys
import json
import io
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
import chatbot

app = FastAPI(title="金刚般若后台")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
BASE_DIR = Path(__file__).parent.parent

@app.on_event("startup")
def startup():
    database.init_db()
    scheduler.start_scheduler()
    # 自动从 GitHub 恢复数据
    try:
        if backup_manager.auto_restore():
            print('[备份] 从 GitHub 自动恢复数据成功')
        else:
            print('[备份] 没有找到备份文件或恢复失败')
    except Exception as e:
        print(f'[备份] 自动恢复异常: {e}')

app.mount("/admin", StaticFiles(directory=str(BASE_DIR / "admin"), html=True), name="admin")

class ArticleIn(BaseModel): title: str; summary: str; content: str
class CommentIn(BaseModel): article_id: int; author: str; content: str
class ReplyIn(BaseModel): reply: str
class LoginIn(BaseModel): username: str; password: str
class GenTaskIn(BaseModel): topic: str; publish_at: str

def check_auth(request: Request):
    if request.cookies.get("session") != "jingang_admin":
        raise HTTPException(status_code=401, detail="未登录")

@app.post("/api/login")
def login(data: LoginIn):
    conn = database.get_db()
    a = conn.execute("SELECT * FROM admin WHERE username=? AND password=?", (data.username, data.password)).fetchone()
    conn.close()
    if a:
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
    if not row: raise HTTPException(status_code=404)
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
async def add_knowledge(request: Request):
    check_auth(request)
    try:
        form = await request.form()
        title = form.get("title", "")
        content = form.get("content", "")
    except:
        body = await request.json()
        title = body.get("title", "")
        content = body.get("content", "")
    knowledge_search.add_knowledge(title, content, "text")
    return {"ok": True}

@app.post("/api/knowledge/upload")
async def upload_knowledge(request: Request):
    check_auth(request)
    form = await request.form()
    file = form.get("file")
    content = (await file.read()).decode("utf-8", errors="ignore")
    title = file.filename.replace(".txt", "").replace(".md", "")
    knowledge_search.add_knowledge(title, content, "file")
    return {"ok": True, "title": title, "length": len(content)}

@app.delete("/api/knowledge/{kid}")
def delete_knowledge(kid: int, request: Request):
    check_auth(request)
    knowledge_search.delete_knowledge(kid)
    return {"ok": True}

# ========== AI 生成 ==========
@app.post("/api/ai/generate")
def ai_generate(data: GenTaskIn, request: Request):
    check_auth(request)
    result = ai_writer.generate_article(data.topic)
    parsed = ai_writer.parse_article(result["raw"])
    return {"ok": True, **parsed}

@app.post("/api/ai/publish")
def ai_publish(data: GenTaskIn, request: Request):
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

# ========== 备份与恢复 ==========
@app.get("/api/backup")
def backup_database(request: Request):
    """导出全部数据为 JSON"""
    check_auth(request)
    conn = database.get_db()
    data = {
        "backup_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "articles": [dict(r) for r in conn.execute("SELECT * FROM articles").fetchall()],
        "comments": [dict(r) for r in conn.execute("SELECT * FROM comments").fetchall()],
        "knowledge": [dict(r) for r in conn.execute("SELECT * FROM knowledge").fetchall()],
        "publish_tasks": [dict(r) for r in conn.execute("SELECT * FROM publish_tasks").fetchall()]
    }
    conn.close()
    return JSONResponse(content=data)

@app.post("/api/restore")
def restore_database(request: Request):
    """从 JSON 恢复数据"""
    check_auth(request)
    try:
        body = request.json() if hasattr(request, 'json') else json.loads(request.body())
    except:
        raise HTTPException(status_code=400, detail="无效的备份文件")
    
    conn = database.get_db()
    try:
        # 清空现有数据
        for table in ["articles", "comments", "knowledge", "publish_tasks"]:
            conn.execute(f"DELETE FROM {table}")
        
        # 恢复文章
        for a in body.get("articles", []):
            conn.execute(
                "INSERT INTO articles (id, title, summary, content, date, published, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (a.get("id"), a.get("title",""), a.get("summary",""), a.get("content",""), a.get("date",""), a.get("published",1), a.get("status","published"))
            )
        
        # 恢复评论
        for c in body.get("comments", []):
            conn.execute(
                "INSERT INTO comments (id, article_id, author, content, reply, ai_reply, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (c.get("id"), c.get("article_id"), c.get("author","同修"), c.get("content",""), c.get("reply",""), c.get("ai_reply",""), c.get("created_at","")))
        
        # 恢复知识库
        for k in body.get("knowledge", []):
            conn.execute(
                "INSERT INTO knowledge (id, title, content, source, created_at) VALUES (?, ?, ?, ?, ?)",
                (k.get("id"), k.get("title",""), k.get("content",""), k.get("source","text"), k.get("created_at","")))
        
        # 恢复定时任务
        for t in body.get("publish_tasks", []):
            conn.execute(
                "INSERT INTO publish_tasks (id, topic, title, content, summary, status, publish_at, created_at, published_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (t.get("id"), t.get("topic",""), t.get("title",""), t.get("content",""), t.get("summary",""), t.get("status","pending"), t.get("publish_at",""), t.get("created_at",""), t.get("published_at","")))
        
        conn.commit()
        return {"ok": True, "message": "数据恢复成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")
    finally:
        conn.close()

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

@app.post("/api/chat")
def chat_with_ai(data: dict):
    """与佛学小助理对话"""
    messages = data.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="消息不能为空")
    reply = chatbot.chat(messages)
    return {"reply": reply}


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

