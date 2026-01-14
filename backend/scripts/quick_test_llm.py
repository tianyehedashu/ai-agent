#!/usr/bin/env python
"""
LLM 快速测试脚本 (不使用 LiteLLM，直接 HTTP 请求)

使用方法:
    cd backend
    python scripts/quick_test_llm.py
"""

import asyncio
import io
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
import httpx

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()


async def test_dashscope():
    """测试阿里云通义千问"""
    print("\n🧪 测试阿里云 DashScope...")

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key or api_key == "your-dashscope-api-key":
        print("   ❌ 未配置")
        return False

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "qwen-turbo",
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 20,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                print(f"   ✅ 成功: {content[:50]}...")
                return True
            else:
                print(f"   ❌ 失败: HTTP {resp.status_code} - {resp.text[:100]}")
                return False
    except (httpx.HTTPError, httpx.RequestError, KeyError, ValueError) as e:
        print(f"   ❌ 错误: {e}")
        return False


async def test_deepseek():
    """测试 DeepSeek"""
    print("\n🧪 测试 DeepSeek...")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == "your-deepseek-api-key":
        print("   ❌ 未配置")
        return False

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 20,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                print(f"   ✅ 成功: {content[:50]}...")
                return True
            else:
                print(f"   ❌ 失败: HTTP {resp.status_code} - {resp.text[:100]}")
                return False
    except (httpx.HTTPError, httpx.RequestError, KeyError, ValueError) as e:
        print(f"   ❌ 错误: {e}")
        return False


async def test_volcengine_chat():
    """测试火山引擎对话模型"""
    print("\n🧪 测试火山引擎 (对话)...")

    api_key = os.getenv("VOLCENGINE_API_KEY")
    endpoint_id = os.getenv("VOLCENGINE_CHAT_ENDPOINT_ID") or os.getenv("VOLCENGINE_ENDPOINT_ID")

    if not api_key or not endpoint_id:
        print("   ❌ 未配置 API_KEY 或 CHAT_ENDPOINT_ID")
        return False

    print(f"   Endpoint: {endpoint_id}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": endpoint_id,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 20,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                print(f"   ✅ 成功: {content[:50]}...")
                return True
            else:
                error_text = resp.text[:150]
                print(f"   ❌ 失败: HTTP {resp.status_code}")
                if "does not support" in error_text:
                    print("      该 endpoint 可能是图像生成模型")
                else:
                    print(f"      {error_text}")
                return False
    except (httpx.HTTPError, httpx.RequestError, KeyError, ValueError) as e:
        print(f"   ❌ 错误: {e}")
        return False


async def test_volcengine_image():
    """测试火山引擎图像生成"""
    print("\n🧪 测试火山引擎 (图像生成)...")

    api_key = os.getenv("VOLCENGINE_API_KEY")
    endpoint_id = os.getenv("VOLCENGINE_IMAGE_ENDPOINT_ID") or os.getenv("VOLCENGINE_ENDPOINT_ID")

    if not api_key or not endpoint_id:
        print("   ❌ 未配置 API_KEY 或 IMAGE_ENDPOINT_ID")
        return False

    print(f"   Endpoint: {endpoint_id}")
    print("   正在生成图像...")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://ark.cn-beijing.volces.com/api/v3/images/generations",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": endpoint_id,
                    "prompt": "一只可爱的小猫",
                    "size": "1920x1920",
                    "n": 1,
                    "response_format": "b64_json",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                images = data.get("data", [])
                if images:
                    size_kb = len(images[0].get("b64_json", "")) * 3 / 4 / 1024
                    print(f"   ✅ 成功: 生成 {len(images)} 张图片 (~{size_kb:.0f}KB)")
                    return True
            else:
                print(f"   ❌ 失败: HTTP {resp.status_code} - {resp.text[:100]}")
                return False
    except (httpx.HTTPError, httpx.RequestError, KeyError, ValueError) as e:
        print(f"   ❌ 错误: {e}")
        return False


async def main():
    """主函数：运行所有 LLM 提供商的测试"""
    print("=" * 50)
    print("🚀 LLM 快速测试 (直接 HTTP 请求)")
    print("=" * 50)

    results = {
        "阿里云通义千问": await test_dashscope(),
        "DeepSeek": await test_deepseek(),
        "火山引擎(对话)": await test_volcengine_chat(),
        "火山引擎(图像)": await test_volcengine_image(),
    }

    print("\n" + "=" * 50)
    print("📊 测试结果")
    print("=" * 50)
    for name, ok in results.items():
        print(f"   {name}: {'✅' if ok else '❌'}")

    passed = sum(results.values())
    print(f"\n   通过: {passed}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
