"""定时发布调度器"""
import threading
import time
import os
from datetime import datetime, timezone, timedelta

# 中国时区
CHINA_TZ = timezone(timedelta(hours=8))

def now_china():
    """返回中国时区的当前时间字符串 YYYY-MM-DD HH:MM"""
    return datetime.now(CHINA_TZ).strftime("%Y-%m-%d %H:%M")

import database
import ai_writer

_scheduler_running = False

def _scheduler_loop():
    global _scheduler_running
    _scheduler_running = True
    # 启动时立即检查一次漏掉的任务
    try:
        _check_and_publish()
    except Exception as e:
        print(f"[调度器] 启动检查失败: {e}")
    # 然后每 30 秒检查一次
    while True:
        time.sleep(30)
        try:
            _check_and_publish()
        except Exception as e:
            print(f"[调度器] 运行检查失败: {e}")

def _check_and_publish():
    now = now_china()
    print(f"[调度器] 检查任务, 当前时间: {now}")
    conn = database.get_db()
    tasks = conn.execute(
        "SELECT * FROM publish_tasks WHERE status='pending' AND publish_at <= ?",
        (now,)
    ).fetchall()
    
    if tasks:
        print(f"[调度器] 找到 {len(tasks)} 个到期任务")
    
    for task in tasks:
        task = dict(task)
        print(f"[调度器] 处理任务 #{task['id']}: {task['topic']}")
        try:
            title = task.get("title") or ""
            content = task.get("content") or ""
            summary = task.get("summary") or ""
            
            if not content:
                result = ai_writer.generate_article(task["topic"])
                parsed = ai_writer.parse_article(result["raw"])
                title = parsed["title"]
                content = parsed["content"]
                summary = parsed["summary"]
            
            today = datetime.now(CHINA_TZ).strftime("%Y-%m-%d")
            if not title: title = f"关于{task['topic']}的感悟"
            if not content: content = f"<p>关于{task['topic']}的感悟，敬请期待。</p>"
            if not summary: summary = content[:50].replace("<p>","").replace("</p>","").strip()[:50]
            
            conn.execute(
                "INSERT INTO articles (title, summary, content, date, published, status) VALUES (?, ?, ?, ?, 1, 'published')",
                (title[:100], summary[:200], content, today)
            )
            
            conn.execute(
                "UPDATE publish_tasks SET status='published', title=?, content=?, summary=?, published_at=? WHERE id=?",
                (title[:100], content, summary[:200], now, task["id"])
            )
            print(f"[调度器] ✅ 任务 #{task['id']} 发布成功: {title[:30]}")
            
        except Exception as e:
            print(f"[调度器] ❌ 任务 #{task['id']} 失败: {e}")
            conn.execute(
                "UPDATE publish_tasks SET status='failed' WHERE id=?",
                (task["id"],)
            )
    
    conn.commit()
    conn.close()

def start_scheduler():
    thread = threading.Thread(target=_scheduler_loop, daemon=True)
    thread.start()
    print("[调度器] 已启动")

def create_publish_task(topic, publish_at, title="", content="", summary=""):
    conn = database.get_db()
    now = now_china()
    cursor = conn.execute(
        "INSERT INTO publish_tasks (topic, title, content, summary, status, publish_at, created_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)",
        (topic, title, content, summary, publish_at, now)
    )
    task_id = cursor.lastrowid
    
    # 如果发布时间在 10 分钟内，立即生成内容
    try:
        publish_dt = datetime.strptime(publish_at, "%Y-%m-%d %H:%M")
        now_dt = datetime.now(CHINA_TZ)
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
