"""定时发布调度器"""
import threading
import time
from datetime import datetime, timedelta
import database
import ai_writer

_scheduler_running = False

def _scheduler_loop():
    global _scheduler_running
    _scheduler_running = True
    # 启动时立即检查一次漏掉的任务
    try:
        _check_and_publish()
    except:
        pass
    # 然后每 30 秒检查一次
    while True:
        try:
            _check_and_publish()
        except:
            pass
        time.sleep(30)

def _check_and_publish():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = database.get_db()
    # 找出所有到期的待发布任务
    tasks = conn.execute(
        "SELECT * FROM publish_tasks WHERE status='pending' AND publish_at <= ?",
        (now,)
    ).fetchall()
    
    for task in tasks:
        task = dict(task)
        try:
            title = task["title"] or ""
            content = task["content"] or ""
            summary = task["summary"] or ""
            
            if not content:
                result = ai_writer.generate_article(task["topic"])
                parsed = ai_writer.parse_article(result["raw"])
                title = parsed["title"]
                content = parsed["content"]
                summary = parsed["summary"]
            
            today = datetime.now().strftime("%Y-%m-%d")
            if not title: title = f"关于{task['topic']}的感悟"
            if not content: content = f"<p>关于{task['topic']}的感悟，敬请期待。</p>"
            if not summary: summary = content[:50].replace("<p>","").replace("</p>","").strip()[:50]
            
            conn.execute(
                "INSERT INTO articles (title, summary, content, date, published, status) VALUES (?, ?, ?, ?, 1, 'published')",
                (title, summary, content, today)
            )
            
            conn.execute(
                "UPDATE publish_tasks SET status='published', title=?, content=?, summary=?, published_at=? WHERE id=?",
                (title, content, summary, now, task["id"])
            )
        except Exception as e:
            conn.execute(
                "UPDATE publish_tasks SET status='failed' WHERE id=?",
                (task["id"],)
            )
    
    conn.commit()
    conn.close()

def start_scheduler():
    thread = threading.Thread(target=_scheduler_loop, daemon=True)
    thread.start()

def create_publish_task(topic, publish_at, title="", content="", summary=""):
    conn = database.get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor = conn.execute(
        "INSERT INTO publish_tasks (topic, title, content, summary, status, publish_at, created_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)",
        (topic, title, content, summary, publish_at, now)
    )
    task_id = cursor.lastrowid
    
    # 如果发布时间在 10 分钟内，立即生成内容
    try:
        publish_dt = datetime.strptime(publish_at, "%Y-%m-%d %H:%M")
        now_dt = datetime.now()
        if (publish_dt - now_dt).total_seconds() < 600:
            result = ai_writer.generate_article(topic)
            parsed = ai_writer.parse_article(result["raw"])
            conn.execute(
                "UPDATE publish_tasks SET title=?, content=?, summary=? WHERE id=?",
                (parsed["title"], parsed["content"], parsed["summary"], task_id)
            )
    except:
        pass
    
    conn.commit()
    conn.close()
    return task_id

def list_tasks():
    conn = database.get_db()
    rows = conn.execute("SELECT * FROM publish_tasks ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_task(task_id):
    conn = database.get_db()
    conn.execute("DELETE FROM publish_tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
