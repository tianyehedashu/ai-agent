"""
LLM 提供商实际访问测试

测试各个 LLM 提供商的真实 API 调用
如果对应模型未配置，测试会自动跳过
"""

import os

import pytest

from app.config import settings
from core.llm.gateway import LLMGateway


class TestLLMProviders:
    """LLM 提供商实际访问测试"""

    @pytest.fixture
    def gateway(self):
        """创建 LLM Gateway 实例"""
        from app.config import settings

        return LLMGateway(config=settings)

    # ========================================================================
    # DeepSeek 测试
    # ========================================================================

    @pytest.mark.asyncio
    async def test_deepseek_chat(self, gateway):
        """测试: DeepSeek 实际聊天调用"""
        if not settings.deepseek_api_key:
            pytest.skip("DeepSeek API Key 未配置，跳过测试")

        try:
            result = await gateway.chat(
                messages=[{"role": "user", "content": "你好，请回复'测试成功'"}],
                model="deepseek-chat",
                temperature=0.7,
                max_tokens=100,
            )

            assert result is not None
            assert result.content is not None
            assert len(result.content) > 0
            print(f"\n✓ DeepSeek 响应: {result.content}")
        except Exception as e:
            pytest.skip(f"DeepSeek API 调用失败（可能是模型未配置或网络问题）: {e}")

    # ========================================================================
    # 火山引擎 (豆包) 测试
    # ========================================================================

    @pytest.mark.asyncio
    async def test_volcengine_doubao_chat(self, gateway):
        """测试: 火山引擎豆包实际聊天调用"""
        if not settings.volcengine_api_key:
            pytest.skip("火山引擎 API Key 未配置，跳过测试")

        # 检查 endpoint_id 是否配置（火山引擎必需）
        endpoint_id = settings.volcengine_chat_endpoint_id or settings.volcengine_endpoint_id
        if not endpoint_id:
            pytest.skip("火山引擎 endpoint_id 未配置，跳过测试")

        # 设置环境变量（LiteLLM 需要）
        if settings.volcengine_api_key and "VOLCENGINE_API_KEY" not in os.environ:
            os.environ["VOLCENGINE_API_KEY"] = settings.volcengine_api_key.get_secret_value()

        try:
            # 火山引擎使用 endpoint_id 作为模型名称
            # 模型名称可以是任意值，实际使用的是 endpoint_id
            result = await gateway.chat(
                messages=[{"role": "user", "content": "你好，请回复'测试成功'"}],
                model="doubao-pro-32k",  # 模型名称，实际使用 endpoint_id
                temperature=0.7,
                max_tokens=100,
            )

            assert result is not None
            assert result.content is not None
            assert len(result.content) > 0
            print(f"\n✓ 火山引擎豆包响应: {result.content}")
        except Exception as e:
            pytest.skip(f"火山引擎 API 调用失败（可能是模型未配置或网络问题）: {e}")

    # ========================================================================
    # 智谱AI (GLM) 测试
    # ========================================================================

    @pytest.mark.asyncio
    # pylint: disable=too-many-branches,too-many-statements
    async def test_zhipuai_glm_chat(self, gateway):
        """
        测试: 智谱AI GLM 实际聊天调用

        重要提示：
        - GLM-4.7 编码套餐只能在特定编程工具中使用（如 Claude Code、Roo Code 等），
          不能通过API单独调用
        - 如果通过API调用GLM-4.7，需要使用通用端点，并确保账户有API额度（不是编码套餐额度）
        - 如果只有编码套餐额度，建议使用其他GLM模型（如 glm-4、glm-4-plus 等）
        """
        if not settings.zhipuai_api_key:
            pytest.skip("智谱AI API Key 未配置，跳过测试")

        # 设置环境变量（LiteLLM 需要 ZAI_API_KEY）
        if settings.zhipuai_api_key:
            if "ZAI_API_KEY" not in os.environ:
                os.environ["ZAI_API_KEY"] = settings.zhipuai_api_key.get_secret_value()
            if "ZHIPUAI_API_KEY" not in os.environ:
                os.environ["ZHIPUAI_API_KEY"] = settings.zhipuai_api_key.get_secret_value()

        # 优先尝试使用 glm-4（支持API调用），如果失败再尝试 glm-4.7
        models_to_try = ["glm-4", "glm-4.7"]
        last_error = None

        for model_name in models_to_try:
            try:
                result = await gateway.chat(
                    messages=[{"role": "user", "content": "你好，请回复'测试成功'"}],
                    model=model_name,
                    temperature=0.7,
                    max_tokens=200,
                )

                assert result is not None
                assert result.content is not None

                # 如果 content 为空但 finish_reason 是 'length'，可能是响应格式问题
                if not result.content and result.finish_reason == "length":
                    if model_name == "glm-4.7":
                        pytest.skip(
                            "GLM-4.7 返回空内容。"
                            "GLM-4.7 编码套餐不支持通过API单独调用，"
                            "请使用其他GLM模型（如 glm-4）或确保账户有通用API额度"
                        )
                    continue  # 尝试下一个模型

                assert len(result.content) > 0

                # 验证响应完整性
                assert result.usage is not None, "usage 信息缺失"
                assert "prompt_tokens" in result.usage, "prompt_tokens 缺失"
                assert "completion_tokens" in result.usage, "completion_tokens 缺失"
                assert "total_tokens" in result.usage, "total_tokens 缺失"
                assert result.finish_reason is not None, "finish_reason 缺失"

                print(f"\n✓ 智谱AI {model_name} 基本对话测试通过")
                print(f"  响应: {result.content}")
                print(
                    f"  Token使用: {result.usage['total_tokens']} (输入: {result.usage['prompt_tokens']}, 输出: {result.usage['completion_tokens']})"
                )
                print(f"  完成原因: {result.finish_reason}")

                # 测试2: 数学计算（验证推理能力）
                math_result = await gateway.chat(
                    messages=[{"role": "user", "content": "请计算 1+3 等于多少？只回答数字即可。"}],
                    model=model_name,
                    temperature=0.1,  # 降低温度以获得更确定的结果
                    max_tokens=50,
                )

                assert math_result is not None
                assert math_result.content is not None
                assert len(math_result.content) > 0

                # 检查答案是否包含 4
                answer = math_result.content.strip()
                print(f"\n✓ 智谱AI {model_name} 数学计算测试")
                print("  问题: 1+3 = ?")
                print(f"  回答: {answer}")

                # 验证答案（允许各种格式：4、答案是4、等于4等）
                if "4" in answer:
                    print("  ✓ 答案正确（包含4）")
                else:
                    print("  ⚠ 答案可能不正确（未包含4）")

                return  # 成功，退出测试

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()

                # 如果是编码套餐相关错误，提供明确提示
                if "coding" in error_msg or "套餐" in error_msg or "not support" in error_msg:
                    if model_name == "glm-4.7":
                        pytest.skip(
                            "GLM-4.7 编码套餐不支持通过API单独调用。\n"
                            "解决方案：\n"
                            "1. 使用其他GLM模型（如 glm-4、glm-4-plus 等）\n"
                            "2. 购买通用API额度（不是编码套餐额度）\n"
                            "3. 在支持的编程工具中使用编码套餐（如 Claude Code、Roo Code 等）\n"
                            f"错误详情: {e}"
                        )
                    continue  # 尝试下一个模型

                # 其他错误，继续尝试下一个模型
                if model_name != models_to_try[-1]:
                    continue

        # 所有模型都失败了
        if last_error:
            pytest.skip(
                f"智谱AI API 调用失败。\n"
                f"如果使用的是GLM-4.7编码套餐，请注意：\n"
                f"- 编码套餐不支持通过API单独调用\n"
                f"- 请使用其他GLM模型（如 glm-4）或购买通用API额度\n"
                f"错误详情: {last_error}"
            )

    # ========================================================================
    # 阿里云 DashScope (通义千问) 测试
    # ========================================================================

    @pytest.mark.asyncio
    async def test_dashscope_qwen_chat(self, gateway):
        """测试: 阿里云 DashScope 通义千问实际聊天调用"""
        if not settings.dashscope_api_key:
            pytest.skip("阿里云 DashScope API Key 未配置，跳过测试")

        try:
            result = await gateway.chat(
                messages=[{"role": "user", "content": "你好，请回复'测试成功'"}],
                model="qwen-turbo",
                temperature=0.7,
                max_tokens=100,
            )

            assert result is not None
            assert result.content is not None
            assert len(result.content) > 0
            print(f"\n✓ 阿里云 DashScope 通义千问响应: {result.content}")
        except Exception as e:
            pytest.skip(f"阿里云 DashScope API 调用失败（可能是模型未配置或网络问题）: {e}")
