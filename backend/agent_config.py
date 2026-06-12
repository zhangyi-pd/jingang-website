"""Agent 配置管理模块"""
import database

DEFAULT_SETTINGS = {
    "chat_bot_enabled": "true",
    "chat_bot_style": "温和",
    "chat_bot_knowledge_first": "true",
    "chat_bot_max_length": "200",
    "auto_reply_enabled": "true",
    "auto_reply_requires_review": "true",
    "auto_reply_style": "温和",
    "auto_writer_enabled": "true",
    "auto_writer_knowledge_first": "true",
    "auto_writer_style": "温和",
    "knowledge_priority": "50",
    "agent_identity": "你是一位修持《金刚经》的佛弟子，法号贤仪居士。你的语气温和慈悲，回答简洁有智慧，适当引用经文。",
}

def init_settings():
    """初始化配置表，插入默认值"""
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    for key, val in DEFAULT_SETTINGS.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
    conn.commit()
    conn.close()

def get_all():
    """读取所有配置"""
    conn = database.get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    result = dict(DEFAULT_SETTINGS)
    for r in rows:
        result[r["key"]] = r["value"]
    return result

def get(key, default=None):
    """读取单个配置"""
    conn = database.get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    if row:
        return row["value"]
    return default or DEFAULT_SETTINGS.get(key, default)

def set(key, value):
    """设置单个配置"""
    conn = database.get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def set_many(kv_dict):
    """批量设置配置"""
    conn = database.get_db()
    for key, value in kv_dict.items():
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_bool(key, default=True):
    val = get(key, str(default).lower())
    return val.lower() == "true"

def get_int(key, default=200):
    try:
        return int(get(key, str(default)))
    except:
        return default
