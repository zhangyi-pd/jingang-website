"""DeepSeek AI 工具模块"""
import json
import urllib.request
import urllib.error

API_KEY = "sk-531fde47ef2748eab6832bbbc1a619fc"
API_URL = "https://api.deepseek.com/v1/chat/completions"

def chat(messages, model="deepseek-chat", temperature=0.7):
    data = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 500
    }).encode("utf-8")
    
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[AI 生成失败: {str(e)}]"

def generate_reply(article_title, article_content, comment_author, comment_content):
    prompt = f"""你是一个佛学网站的助手「贤仪居士」。请根据以下文章和用户留言，生成一段温暖、真诚的回复。

文章标题：{article_title}
文章内容摘要：{article_content[:500]}
留言者：{comment_author}
留言内容：{comment_content}

要求：
- 语气温和慈悲，有佛学韵味
- 结合文章内容回应留言者的感悟
- 自然引用《金刚经》中的相关经文（如果合适）
- 字数 50-150 字
- 用「贤仪居士」的口吻回复，开头可加"🙏"
"""
    return chat([
        {"role": "system", "content": "你是一位修持《金刚经》的佛弟子，法号贤仪居士。你的回答温和、慈悲、有智慧。"},
        {"role": "user", "content": prompt}
    ], temperature=0.8)
