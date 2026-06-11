"""AI 文章生成模块"""
import deepseek
import knowledge_search
from datetime import datetime
import database

def generate_article(topic):
    """根据主题生成文章，优先使用知识库素材"""
    # 第一步：从知识库搜索相关素材
    context = knowledge_search.build_search_context(topic)
    
    # 第二步：构造提示词
    system_prompt = """你是一位修持《金刚经》的佛弟子，法号贤仪居士。你擅长用温暖、真诚的文字分享佛法感悟。
写作风格：
- 语言优美自然，有禅意但不晦涩
- 结合生活实际，不说空洞的大道理
- 适当引用《金刚经》原文
- 语气亲切，像在和朋友谈心
- 文章最后可以加一句祝福语"""
    
    user_prompt = f"""请以「贤仪居士」的身份，写一篇关于「{topic}」的佛法感悟文章。

要求：
1. 标题：10-20字，有禅意
2. 摘要：30-50字的一句话概述
3. 正文：600-1000字，分段清晰，可以用 <p> 标签
4. 语气温暖真诚，结合生活实际
5. 如果合适，引用《金刚经》的原文

{context}

如果知识库有相关素材，请优先参考和使用。同时可以结合你自身的佛学知识进行补充。"""

    # 第三步：调用 AI 生成
    content = deepseek.chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], model="deepseek-chat", temperature=0.8)
    
    return {"raw": content}

def parse_article(raw_text):
    """解析 AI 输出的文章，提取标题、摘要、正文"""
    lines = raw_text.strip().split("\n")
    title = ""
    summary = ""
    body_parts = []
    
    in_body = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if not title and ("标题" in line or line.startswith("《") or "。" not in line[:20]):
            title = line.replace("标题：", "").replace("**", "").replace("【标题】", "").strip()
            if title.startswith("《") and title.endswith("》"):
                pass
            elif "。" not in title and len(title) < 30:
                pass
            else:
                title = line[:20]
                body_parts.append(line)
            continue
        if not summary and ("摘要" in line or "概述" in line):
            summary = line.replace("摘要：", "").replace("**", "").strip()
            continue
        if not summary and len(line) < 60 and ("。" in line or "，" in line):
            # 可能是正文第一句
            if not any(k in line for k in ["标题", "摘要", "正文"]):
                summary = line[:50]
                body_parts.append(line)
                continue
        if not in_body:
            if "正文" in line or line.startswith("正文"):
                in_body = True
                continue
            # 如果前面没匹配到，直接当正文
            if title and summary:
                body_parts.append(line)
        else:
            body_parts.append(line)
    
    if not title:
        # 取第一行非空并包含中文字符的作为标题
        for line in lines:
            line = line.strip()
            if line and any('\u4e00' <= c <= '\u9fff' for c in line):
                title = line[:20]
                break
    
    body = "\n".join(body_parts)
    # 加 <p> 标签
    if not body.startswith("<"):
        paragraphs = [p for p in body.split("\n") if p.strip()]
        body = "".join(f"<p>{p}</p>" for p in paragraphs)
    
    if not summary:
        summary = body[:50].replace("<p>", "").replace("</p>", "").replace("。", "。").strip()[:50]
        if len(summary) > 0 and not summary.endswith("。"):
            summary += "。。"
    
    return {"title": title, "summary": summary, "content": body}
