"""数据库管理模块"""
import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "jingang.db")

def get_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            date TEXT NOT NULL,
            published INTEGER NOT NULL DEFAULT 1
        );
        
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            author TEXT NOT NULL DEFAULT '同修',
            content TEXT NOT NULL,
            reply TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles(id)
        );
        
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        );
    """)
    
    cursor.execute("SELECT COUNT(*) FROM admin")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO admin (username, password) VALUES (?, ?)",
            ("admin", "admin123")
        )
    
    cursor.execute("SELECT COUNT(*) FROM articles")
    if cursor.fetchone()[0] == 0:
        sample = [
            ("初读《金刚经》的感悟",
             "初遇《金刚经》，被降伏其心四字深深触动...",
             "<p>第一次捧起《金刚经》，心中满是敬畏。善男子、善女人，发阿耨多罗三藐三菩提心，应如是住，如是降伏其心。</p><p>读到这里，我问自己：我的心，真的安住了吗？</p><p>生活在喧嚣中，我们的心常常被外境所转。工作上的得失、人际间的纷扰，无时无刻不在扰动这颗心。而佛陀一开始就告诉我们：应如是住，如是降伏其心。</p><p>不需要刻意求静，不需要远离尘世，就在当下，就在此时，观照自心。</p>",
             "2025-03-15"),
            ("应无所住而生其心的体会",
             "在生活中体会应无所住的妙用...",
             "<p>应无所住而生其心——这七个字，我反复品味了很久。</p><p>什么是无所住？不执着。不执着于过去的烦恼，不执着于未来的期待，也不执着于当下的境界。</p><p>生活中，当遇到不如意事，我们习惯性地住在为什么是我的抱怨中；当遇到顺心事，我们住在希望一直这样的贪求里。这不正是有所住吗？</p><p>而生其心——不是没有心，而是生清净心，生慈悲心，生智慧心。</p>",
             "2025-04-02"),
            ("共修的力量",
             "一个人走得快，一群人走得远...",
             "<p>学佛的路上，既需要独处的静修，也需要同修的砥砺。</p><p>一个人诵经时，容易懈怠；一群人共修时，互相策励。一个人读经时，理解可能偏颇；有人讨论时，更能开阔见地。</p><p>愿以此网站为缘，与有缘同修共同精进，在般若智慧的光明中，互相照亮，共证菩提。</p>",
             "2025-05-01")
        ]
        for title, summary, content, date in sample:
            cursor.execute(
                "INSERT INTO articles (title, summary, content, date, published) VALUES (?, ?, ?, ?, 1)",
                (title, summary, content, date)
            )
    
    conn.commit()
    conn.close()
