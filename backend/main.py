import os
import sys
import json
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))
import database

app = FastAPI(title="金刚般若后台")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent.parent

@app.on_event("startup")
def startup():
    database.init_db()

app.mount("/admin", StaticFiles(directory=str(BASE_DIR / "admin"), html=True), name="admin")

class ArticleIn(BaseModel):
    title: str
    summary: str
    content: str

class CommentIn(BaseModel):
    article_id: int
    author: str
    content: str

class ReplyIn(BaseModel):
    reply: str

class LoginIn(BaseModel):
    username: str
    password: str

def check_auth(request: Request):
    session = request.cookies.get("session")
    if session != "jingang_admin":
        raise HTTPException(status_code=401, detail="未登录")

@app.post("/api/login")
def login(data: LoginIn):
    conn = database.get_db()
    cur = conn.execute("SELECT * FROM admin WHERE username=? AND password=?", 
                       (data.username, data.password))
    admin = cur.fetchone()
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
    if not row:
        raise HTTPException(status_code=404, detail="文章不存在")
    return dict(row)

@app.post("/api/articles")
def create_article(data: ArticleIn, request: Request):
    check_auth(request)
    conn = database.get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        "INSERT INTO articles (title, summary, content, date) VALUES (?, ?, ?, ?)",
        (data.title, data.summary, data.content, today)
    )
    conn.commit()
    conn.close()
    return {"ok": True}

@app.put("/api/articles/{article_id}")
def update_article(article_id: int, data: ArticleIn, request: Request):
    check_auth(request)
    conn = database.get_db()
    conn.execute(
        "UPDATE articles SET title=?, summary=?, content=? WHERE id=?",
        (data.title, data.summary, data.content, article_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/articles/{article_id}")
def delete_article(article_id: int, request: Request):
    check_auth(request)
    conn = database.get_db()
    conn.execute("DELETE FROM articles WHERE id=?", (article_id,))
    conn.execute("DELETE FROM comments WHERE article_id=?", (article_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.get("/api/comments/{article_id}")
def list_comments(article_id: int):
    conn = database.get_db()
    rows = conn.execute("SELECT * FROM comments WHERE article_id=? ORDER BY created_at DESC", 
                        (article_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/comments")
def list_all_comments(request: Request):
    check_auth(request)
    conn = database.get_db()
    rows = conn.execute("""
        SELECT c.*, a.title as article_title 
        FROM comments c LEFT JOIN articles a ON c.article_id = a.id 
        ORDER BY c.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/comments")
def create_comment(data: CommentIn):
    conn = database.get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute(
        "INSERT INTO comments (article_id, author, content, created_at) VALUES (?, ?, ?, ?)",
        (data.article_id, data.author, data.content, now)
    )
    conn.commit()
    conn.close()
    return {"ok": True}

@app.put("/api/comments/{comment_id}/reply")
def reply_comment(comment_id: int, data: ReplyIn, request: Request):
    check_auth(request)
    conn = database.get_db()
    conn.execute("UPDATE comments SET reply=? WHERE id=?", (data.reply, comment_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/comments/{comment_id}")
def delete_comment(comment_id: int, request: Request):
    check_auth(request)
    conn = database.get_db()
    conn.execute("DELETE FROM comments WHERE id=?", (comment_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.get("/api/stats")
def get_stats(request: Request):
    check_auth(request)
    conn = database.get_db()
    article_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    comment_count = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    unreplied = conn.execute("SELECT COUNT(*) FROM comments WHERE reply=''").fetchone()[0]
    conn.close()
    return {"articles": article_count, "comments": comment_count, "unreplied": unreplied}

@app.get("/")
def index():
    return FileResponse(str(BASE_DIR / "index.html"))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
