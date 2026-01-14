#!/usr/bin/env python
"""
LLM 提供商测试脚本

测试各个大模型提供商的 API 连接是否正常。

使用方法:
    cd backend
    python scripts/test_llm_providers.py

    # 测试特定提供商
    python scripts/test_llm_providers.py --provider dashscope
    python scripts/test_llm_providers.py --provider deepseek
    python scripts/test_llm_providers.py --provider volcengine
    python scripts/test_llm_providers.py --provider all
"""

import argparse
import asyncio
import io
import os
from pathlib import Path
import sys

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv  # pylint: disable=wrong-import-position

# 加载环境变量
load_dotenv()


async def test_dashscope():
    """测试阿里云 DashScope (通义千问)"""
    print("\n" + "=" * 60)
    print("🧪 测试阿里云 DashScope (通义千问)")
    print("=" * 60)

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key or api_key == "your-dashscope-api-key":
        print("❌ DASHSCOPE_API_KEY 未配置")
        print("   请在 .env 文件中设置 DASHSCOPE_API_KEY")
        print("   获取地址: https://dashscope.console.aliyun.com/apiKey")
        return False

    try:
        from litellm import acompletion  # pylint: disable=import-outside-toplevel

        print("📡 正在连接 DashScope API...")
        print("   模型: qwen-turbo")

        response = await asyncio.wait_for(
            acompletion(
                model="openai/qwen-turbo",  # LiteLLM 格式
                messages=[{"role": "user", "content": "你好，请用一句话介绍你自己。"}],
                api_key=api_key,
                api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
                max_tokens=100,
                timeout=30,
            ),
            timeout=35,
        )

        content = response.choices[0].message.content
        print("✅ 连接成功!")
        print(f"   响应: {content[:100]}..." if len(content) > 100 else f"   响应: {content}")
        print(f"   Token 使用: {response.usage.total_tokens}")
        return True

    except TimeoutError:
        print("❌ 连接超时 (35秒)")
        print("   提示: 可能是网络问题，请检查网络连接")
        return False
    except (ValueError, KeyError, AttributeError) as e:
        # 捕获 API 响应格式错误、键错误等
        print(f"❌ 连接失败: {e}")
        return False
    except Exception as e:  # pylint: disable=broad-exception-caught
        # 捕获其他未知异常（网络错误、API 错误等）
        print(f"❌ 连接失败: {e}")
        return False


async def test_deepseek():
    """测试 DeepSeek"""
    print("\n" + "=" * 60)
    print("🧪 测试 DeepSeek")
    print("=" * 60)

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == "your-deepseek-api-key":
        print("❌ DEEPSEEK_API_KEY 未配置")
        print("   请在 .env 文件中设置 DEEPSEEK_API_KEY")
        print("   获取地址: https://platform.deepseek.com/api_keys")
        return False

    try:
        from litellm import acompletion  # pylint: disable=import-outside-toplevel

        print("📡 正在连接 DeepSeek API...")
        print("   模型: deepseek-chat")

        response = await asyncio.wait_for(
            acompletion(
                model="deepseek/deepseek-chat",  # LiteLLM 格式
                messages=[{"role": "user", "content": "你好，请用一句话介绍你自己。"}],
                api_key=api_key,
                api_base="https://api.deepseek.com",
                max_tokens=100,
                timeout=30,
            ),
            timeout=35,
        )

        content = response.choices[0].message.content
        print("✅ 连接成功!")
        print(f"   响应: {content[:100]}..." if len(content) > 100 else f"   响应: {content}")
        print(f"   Token 使用: {response.usage.total_tokens}")
        return True

    except TimeoutError:
        print("❌ 连接超时 (35秒)")
        return False
    except (ValueError, KeyError, AttributeError) as e:
        # 捕获 API 响应格式错误、键错误等
        print(f"❌ 连接失败: {e}")
        return False
    except Exception as e:  # pylint: disable=broad-exception-caught
        # 捕获其他未知异常（网络错误、API 错误等）
        print(f"❌ 连接失败: {e}")
        return False


async def test_volcengine():
    """测试火山引擎 (豆包对话模型)"""
    print("\n" + "=" * 60)
    print("🧪 测试火山引擎 (字节豆包 - 文本对话)")
    print("=" * 60)

    api_key = os.getenv("VOLCENGINE_API_KEY")
    if not api_key or api_key == "your-volcengine-api-key":
        print("❌ VOLCENGINE_API_KEY 未配置")
        print("   请在 .env 文件中设置 VOLCENGINE_API_KEY")
        print("   获取地址: https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey")
        return False

    # 支持两种配置方式: 专用对话端点 或 通用端点
    chat_endpoint_id = os.getenv("VOLCENGINE_CHAT_ENDPOINT_ID")
    endpoint_id = os.getenv("VOLCENGINE_ENDPOINT_ID")
    actual_endpoint = chat_endpoint_id or endpoint_id

    if not actual_endpoint:
        print("❌ VOLCENGINE_ENDPOINT_ID 或 VOLCENGINE_CHAT_ENDPOINT_ID 未配置")
        print("   火山引擎需要创建推理接入点才能使用")
        print("   步骤:")
        print("   1. 访问 https://console.volcengine.com/ark/region:ark+cn-beijing/endpoint")
        print("   2. 点击「创建推理接入点」")
        print("   3. 选择 Doubao-pro 或 Doubao-lite 系列模型 (文本对话模型)")
        print("   4. 获取 endpoint_id 并设置到 .env 文件")
        return False

    try:
        from litellm import acompletion  # pylint: disable=import-outside-toplevel

        print("📡 正在连接火山引擎 API...")
        print(f"   Endpoint ID: {actual_endpoint}")
        if chat_endpoint_id:
            print("   (使用 VOLCENGINE_CHAT_ENDPOINT_ID)")

        model = f"volcengine/{actual_endpoint}"

        response = await asyncio.wait_for(
            acompletion(
                model=model,
                messages=[{"role": "user", "content": "你好，请用一句话介绍你自己。"}],
                api_key=api_key,
                api_base="https://ark.cn-beijing.volces.com/api/v3",
                max_tokens=100,
                timeout=30,
            ),
            timeout=35,
        )

        content = response.choices[0].message.content
        print("✅ 对话模型连接成功!")
        print(f"   响应: {content[:100]}..." if len(content) > 100 else f"   响应: {content}")
        print(f"   Token 使用: {response.usage.total_tokens}")
        return True

    except TimeoutError:
        print("❌ 连接超时 (35秒)")
        return False
    except (ValueError, KeyError, AttributeError) as e:
        # 捕获 API 响应格式错误、键错误等
        error_msg = str(e)
        print(f"❌ 连接失败: {e}")

        if "does not support this api" in error_msg:
            print("\n   ⚠️  该 endpoint 是图像生成模型 (如 Seedream)，不支持聊天 API")
            print("   解决方案:")
            print("   1. 创建新的 Doubao-pro 推理接入点用于文本对话")
            print("   2. 配置 VOLCENGINE_CHAT_ENDPOINT_ID = 新接入点ID")
            print("   3. 保留 VOLCENGINE_ENDPOINT_ID 用于图像生成")
        elif "authentication" in error_msg.lower() or "auth" in error_msg.lower():
            print("   提示: API Key 可能无效，请检查 VOLCENGINE_API_KEY")

        return False
    except Exception as e:  # pylint: disable=broad-exception-caught
        # 捕获其他未知异常（网络错误、API 错误等）
        error_msg = str(e)
        print(f"❌ 连接失败: {e}")

        if "does not support this api" in error_msg:
            print("\n   ⚠️  该 endpoint 是图像生成模型 (如 Seedream)，不支持聊天 API")
            print("   解决方案:")
            print("   1. 创建新的 Doubao-pro 推理接入点用于文本对话")
            print("   2. 配置 VOLCENGINE_CHAT_ENDPOINT_ID = 新接入点ID")
            print("   3. 保留 VOLCENGINE_ENDPOINT_ID 用于图像生成")
        elif "authentication" in error_msg.lower() or "auth" in error_msg.lower():
            print("   提示: API Key 可能无效，请检查 VOLCENGINE_API_KEY")

        return False


async def test_volcengine_image():
    """测试火山引擎 Seedream (图像生成)"""
    print("\n" + "=" * 60)
    print("🧪 测试火山引擎 (Seedream - 图像生成)")
    print("=" * 60)

    api_key = os.getenv("VOLCENGINE_API_KEY")
    if not api_key or api_key == "your-volcengine-api-key":
        print("❌ VOLCENGINE_API_KEY 未配置")
        return False

    # 支持专用图像端点或通用端点
    image_endpoint_id = os.getenv("VOLCENGINE_IMAGE_ENDPOINT_ID") or os.getenv(
        "VOLCENGINE_ENDPOINT_ID"
    )

    if not image_endpoint_id:
        print("❌ VOLCENGINE_IMAGE_ENDPOINT_ID 或 VOLCENGINE_ENDPOINT_ID 未配置")
        print("   需要创建 Seedream 图像生成模型的推理接入点")
        return False

    try:
        import httpx  # pylint: disable=import-outside-toplevel

        print("📡 正在连接火山引擎图像生成 API...")
        print(f"   Endpoint ID: {image_endpoint_id}")

        url = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Seedream 要求最小 3686400 像素 (约 1920x1920)
        payload = {
            "model": image_endpoint_id,
            "prompt": "一只可爱的小猫咪，卡通风格，高清",
            "size": "1920x1920",  # Seedream 最小尺寸要求
            "n": 1,
            "response_format": "b64_json",
        }

        print("   正在生成图像，请稍候...")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()
                images = data.get("data", [])
                if images:
                    print("✅ 图像生成成功!")
                    print(f"   生成了 {len(images)} 张图片")
                    for i, img in enumerate(images):
                        if "b64_json" in img:
                            size_kb = len(img["b64_json"]) * 3 / 4 / 1024
                            print(f"   图片 {i+1}: ~{size_kb:.1f} KB (Base64)")
                    return True
                else:
                    print("❌ 响应中没有图片数据")
                    return False
            else:
                error_text = response.text
                print(f"❌ 图像生成失败: HTTP {response.status_code}")
                print(f"   {error_text[:200]}")

                if "does not support" in error_text.lower():
                    print("\n   ⚠️  该 endpoint 可能是对话模型，不支持图像生成")
                    print("   请配置 Seedream 模型的推理接入点")

                return False

    except (httpx.HTTPError, httpx.TimeoutException) as e:
        # 捕获 HTTP 请求相关异常
        print(f"❌ 图像生成异常: {e}")
        return False
    except Exception as e:  # pylint: disable=broad-exception-caught
        # 捕获其他未知异常（JSON 解析错误等）
        print(f"❌ 图像生成异常: {e}")
        return False


async def test_openai():
    """测试 OpenAI"""
    print("\n" + "=" * 60)
    print("🧪 测试 OpenAI")
    print("=" * 60)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-openai-api-key":
        print("❌ OPENAI_API_KEY 未配置")
        return False

    try:
        from litellm import acompletion  # pylint: disable=import-outside-toplevel

        print("📡 正在连接 OpenAI API...")
        print("   模型: gpt-4o-mini")

        response = await asyncio.wait_for(
            acompletion(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": "Hello, introduce yourself in one sentence."}
                ],
                api_key=api_key,
                max_tokens=100,
                timeout=30,
            ),
            timeout=35,
        )

        content = response.choices[0].message.content
        print("✅ 连接成功!")
        print(f"   响应: {content[:100]}..." if len(content) > 100 else f"   响应: {content}")
        print(f"   Token 使用: {response.usage.total_tokens}")
        return True

    except TimeoutError:
        print("❌ 连接超时 (35秒)")
        return False
    except (ValueError, KeyError, AttributeError) as e:
        # 捕获 API 响应格式错误、键错误等
        print(f"❌ 连接失败: {e}")
        return False
    except Exception as e:  # pylint: disable=broad-exception-caught
        # 捕获其他未知异常（网络错误、API 错误等）
        print(f"❌ 连接失败: {e}")
        return False


async def test_anthropic():
    """测试 Anthropic"""
    print("\n" + "=" * 60)
    print("🧪 测试 Anthropic (Claude)")
    print("=" * 60)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your-anthropic-api-key":
        print("❌ ANTHROPIC_API_KEY 未配置")
        return False

    try:
        from litellm import acompletion  # pylint: disable=import-outside-toplevel

        print("📡 正在连接 Anthropic API...")
        print("   模型: claude-3-5-haiku-20241022")

        response = await asyncio.wait_for(
            acompletion(
                model="claude-3-5-haiku-20241022",
                messages=[
                    {"role": "user", "content": "Hello, introduce yourself in one sentence."}
                ],
                api_key=api_key,
                max_tokens=100,
                timeout=30,
            ),
            timeout=35,
        )

        content = response.choices[0].message.content
        print("✅ 连接成功!")
        print(f"   响应: {content[:100]}..." if len(content) > 100 else f"   响应: {content}")
        print(f"   Token 使用: {response.usage.total_tokens}")
        return True

    except TimeoutError:
        print("❌ 连接超时 (35秒)")
        return False
    except (ValueError, KeyError, AttributeError) as e:
        # 捕获 API 响应格式错误、键错误等
        print(f"❌ 连接失败: {e}")
        return False
    except Exception as e:  # pylint: disable=broad-exception-caught
        # 捕获其他未知异常（网络错误、API 错误等）
        print(f"❌ 连接失败: {e}")
        return False


async def main():
    """主函数：解析命令行参数并执行相应的 LLM 提供商测试"""
    parser = argparse.ArgumentParser(description="测试 LLM 提供商 API 连接")
    parser.add_argument(
        "--provider",
        "-p",
        choices=[
            "dashscope",
            "deepseek",
            "volcengine",
            "volcengine-image",
            "openai",
            "anthropic",
            "all",
            "china",
            "image",
        ],
        default="china",
        help="要测试的提供商 (默认: china - 测试国产模型; image - 测试图像生成)",
    )
    args = parser.parse_args()

    print("🚀 LLM 提供商 API 测试")
    print("=" * 60)

    results = {}

    # 文本对话模型测试
    if args.provider in ["dashscope", "all", "china"]:
        results["阿里云通义千问"] = await test_dashscope()

    if args.provider in ["deepseek", "all", "china"]:
        results["DeepSeek"] = await test_deepseek()

    if args.provider in ["volcengine", "all", "china"]:
        results["火山引擎豆包(对话)"] = await test_volcengine()

    if args.provider in ["openai", "all"]:
        results["OpenAI"] = await test_openai()

    if args.provider in ["anthropic", "all"]:
        results["Anthropic"] = await test_anthropic()

    # 图像生成模型测试
    if args.provider in ["volcengine-image", "all", "image"]:
        results["火山引擎Seedream(图像)"] = await test_volcengine_image()

    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)

    for provider, success in results.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"   {provider}: {status}")

    success_count = sum(results.values())
    total_count = len(results)
    print(f"\n   总计: {success_count}/{total_count} 通过")

    if success_count == total_count:
        print("\n🎉 所有测试通过!")
    else:
        print("\n⚠️  部分测试未通过，请检查配置")

    # 显示配置提示
    print("\n" + "=" * 60)
    print("💡 配置提示")
    print("=" * 60)
    print("   火山引擎支持两种模型类型:")
    print("   • 对话模型: VOLCENGINE_CHAT_ENDPOINT_ID (Doubao-pro/lite)")
    print("   • 图像生成: VOLCENGINE_IMAGE_ENDPOINT_ID (Seedream)")
    print("   如果只配置 VOLCENGINE_ENDPOINT_ID，会同时用于两种测试")


if __name__ == "__main__":
    asyncio.run(main())
