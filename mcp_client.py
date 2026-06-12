"""MCP 客户端使用教程
教你如何连接到任何 MCP Server，读取工具列表并调用工具。

用法：
  # 列出你的 MCP Server 上所有可用工具
  python mcp_client.py list --url https://jingang-website-production.up.railway.app
  
  # 调用某个工具
  python mcp_client.py call --url https://jingang-website-production.up.railway.app --tool list_articles
  
  # 搜索知识库
  python mcp_client.py call --url https://jingang-website-production.up.railway.app --tool search_knowledge --param '{"keyword":"金刚经"}'
"""

import sys
import json
import urllib.request
import urllib.error

def mcp_request(url, method, params=None):
    """发送 MCP 请求到任何 MCP Server"""
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {}
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url.rstrip("/") + "/mcp",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        return result
    except urllib.error.HTTPError as e:
        return json.loads(e.read())
    except Exception as e:
        return {"error": str(e)}

def list_tools(url):
    """列出 MCP Server 的所有工具"""
    print(f"🔍 连接到: {url}/mcp")
    print()
    
    # 1. 初始化
    init_resp = mcp_request(url, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {}
    })
    if "error" in init_resp:
        print(f"❌ 初始化失败: {init_resp['error']}")
        return
    print("✅ 连接成功！")
    print(f"   Server: {init_resp.get('result',{}).get('serverInfo',{}).get('name','unknown')}")
    print(f"   协议: {init_resp.get('result',{}).get('protocolVersion','unknown')}")
    print()
    
    # 2. 获取工具列表
    tools_resp = mcp_request(url, "tools/list")
    if "error" in tools_resp:
        print(f"❌ 获取工具列表失败: {tools_resp['error']}")
        return
    
    tools = tools_resp.get("result", {}).get("tools", [])
    print(f"📦 共 {len(tools)} 个工具可用：")
    print()
    for t in tools:
        print(f"  🛠️  {t['name']}")
        print(f"     📝 {t.get('description', '无描述')}")
        schema = t.get("inputSchema", {})
        if schema.get("properties"):
            print(f"     参数: {', '.join(schema['properties'].keys())}")
        print()

def call_tool(url, tool_name, params=None):
    """调用 MCP Server 的某个工具"""
    print(f"🔧 调用工具: {tool_name}")
    print(f"📤 参数: {json.dumps(params, ensure_ascii=False)}")
    print()
    
    # 先初始化
    mcp_request(url, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {}
    })
    
    # 调用工具
    resp = mcp_request(url, "tools/call", {
        "name": tool_name,
        "arguments": params or {}
    })
    
    if "error" in resp:
        print(f"❌ 调用失败: {resp['error']}")
        return
    
    content = resp.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            try:
                data = json.loads(item["text"])
                print(json.dumps(data, ensure_ascii=False, indent=2))
            except:
                print(item["text"])

def demo(url):
    """完整的演示流程"""
    print("=" * 50)
    print("🤖 MCP 协议完整演示")
    print("=" * 50)
    print()
    
    # 1. 列出工具
    list_tools(url)
    
    # 2. 调用 get_stats
    print("=" * 50)
    print("📊 示例：获取网站统计")
    print("=" * 50)
    call_tool(url, "get_stats")
    print()
    
    # 3. 调用 list_articles
    print("=" * 50)
    print("📝 示例：获取文章列表")
    print("=" * 50)
    call_tool(url, "list_articles")
    print()
    
    # 4. 搜索知识库
    print("=" * 50)
    print("📚 示例：搜索知识库")
    print("=" * 50)
    call_tool(url, "search_knowledge", {"keyword": "金刚经"})
    print()
    
    print("✅ 演示完成！")

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    
    cmd = sys.argv[1]
    url = "https://jingang-website-production.up.railway.app"
    tool = None
    params = None
    
    # 解析参数
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--url" and i + 1 < len(sys.argv):
            url = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--tool" and i + 1 < len(sys.argv):
            tool = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--param" and i + 1 < len(sys.argv):
            params = json.loads(sys.argv[i + 1])
            i += 2
        else:
            i += 1
    
    if cmd == "list":
        list_tools(url)
    elif cmd == "call":
        if not tool:
            print("❌ 请指定 --tool 参数")
            sys.exit(1)
        call_tool(url, tool, params)
    elif cmd == "demo":
        demo(url)
    else:
        print(f"❌ 未知命令: {cmd}")
        print("可用命令: list, call, demo")
