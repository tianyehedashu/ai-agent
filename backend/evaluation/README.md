# 评估体系使用指南

本目录包含 AI Agent 系统的完整评估体系，包括：

## 评估模块

### 1. 任务完成率评估 (`task_completion.py`)

评估 Agent 完成指定任务的能力。

```python
from evaluation.task_completion import TaskEvaluator

test_cases = [
    {
        "id": "task_001",
        "input": "What is 2 + 2?",
        "expected_output": "4",
        "criteria": {"exact_match": True},
        "timeout": 10,
    }
]

evaluator = TaskEvaluator(test_cases=test_cases)
report = await evaluator.run_evaluation(agent)
print(f"成功率: {report.success_rate:.2%}")
```

### 2. 工具调用准确率评估 (`tool_accuracy.py`)

评估 Agent 工具调用的准确性和正确性。

```python
from evaluation.tool_accuracy import ToolAccuracyEvaluator
from core.types import ToolCall, ToolResult

evaluator = ToolAccuracyEvaluator()

# 评估工具调用
tool_call = ToolCall(
    id="call_1",
    name="read_file",
    arguments={"path": "/tmp/test.txt"},
)

result = evaluator.evaluate_tool_call(
    tool_call=tool_call,
    expected_tool="read_file",
    expected_args={"path": "/tmp/test.txt"},
)

# 生成报告
report = evaluator.generate_report()
print(f"工具准确率: {report.tool_accuracy:.2%}")
print(f"参数准确率: {report.args_accuracy:.2%}")
print(f"总体准确率: {report.overall_accuracy:.2%}")
```

### 3. LLM-as-Judge 评估 (`llm_judge.py`)

使用 LLM 评估 Agent 响应质量。

```python
from evaluation.llm_judge import LLMJudge
from core.llm.gateway import LLMGateway

llm_gateway = LLMGateway()
judge = LLMJudge(llm_gateway=llm_gateway, judge_model="gpt-4")

score = await judge.evaluate(
    query="What is TDD?",
    response="TDD is Test-Driven Development...",
    expected="A development methodology...",
)

print(f"总体得分: {score.overall_score}/10")
print(f"相关性: {score.relevance}/10")
print(f"准确性: {score.accuracy}/10")
```

### 4. GAIA 评估 (`gaia.py`)

GAIA (General AI Assistant) 基准评估。

```python
from evaluation.gaia import GAIAEvaluator

evaluator = GAIAEvaluator()
evaluator.load_benchmark("evaluation/benchmarks/gaia_sample.yaml")

report = await evaluator.evaluate_agent(agent)

print(f"GAIA 准确率: {report.accuracy:.2%}")
print(f"平均得分: {report.average_score:.2f}")
print(f"按难度统计: {report.results_by_difficulty}")
```

## API 使用

### 任务完成率评估

```bash
POST /api/v1/evaluation/task
{
  "agent_id": "agent-123",
  "benchmark_type": "task",
  "test_cases": [
    {
      "id": "task_001",
      "input": "What is 2 + 2?",
      "expected_output": "4",
      "criteria": {"exact_match": true}
    }
  ]
}
```

### 工具调用准确率评估

```bash
POST /api/v1/evaluation/tool-accuracy
{
  "tool_calls": [
    {
      "id": "call_1",
      "name": "read_file",
      "arguments": {"path": "/tmp/test.txt"}
    }
  ],
  "expected_tools": {
    "call_1": "read_file"
  },
  "expected_args": {
    "call_1": {"path": "/tmp/test.txt"}
  }
}
```

### LLM-as-Judge 评估

```bash
POST /api/v1/evaluation/llm-judge
{
  "query": "What is TDD?",
  "response": "TDD is Test-Driven Development...",
  "expected": "A development methodology...",
  "judge_model": "gpt-4"
}
```

### GAIA 评估

```bash
POST /api/v1/evaluation/gaia
{
  "agent_id": "agent-123",
  "benchmark_type": "gaia",
  "benchmark_path": "evaluation/benchmarks/gaia_sample.yaml"
}
```

## 评估指标

### 工具调用准确率指标

- **工具准确率**: 工具选择正确的比例
- **参数准确率**: 参数完全正确的比例
- **执行成功率**: 工具执行成功的比例
- **总体准确率**: 综合得分 (0.0 - 1.0)

### GAIA 评估指标

- **准确率**: 正确答案的比例
- **平均得分**: 平均得分 (0.0 - 1.0)
- **平均时间**: 平均响应时间 (毫秒)
- **平均步数**: 平均执行步数
- **平均 Token**: 平均消耗的 Token 数
- **按难度统计**: 按 simple/medium/hard 分类统计

## 基准测试集

### 内置基准测试集

- `agent_tasks.yaml`: 通用 Agent 任务基准
- `gaia_sample.yaml`: GAIA 评估基准示例

### 自定义基准测试集

可以创建自定义的 YAML 或 JSON 格式基准测试集：

```yaml
benchmark:
  name: "Custom Benchmark"
  version: "1.0"

test_cases:
  - id: "custom_001"
    input: "Your question here"
    expected_output: "Expected answer"
    criteria:
      exact_match: true
    timeout: 30
```

## 最佳实践

1. **评估前准备**: 确保 Agent 已正确配置，工具已注册
2. **基准测试集**: 使用多样化的测试用例，覆盖不同难度和场景
3. **定期评估**: 在代码变更后运行评估，确保性能不下降
4. **结果分析**: 分析失败案例，找出改进方向
5. **持续监控**: 将评估集成到 CI/CD 流程中

## 示例脚本

```python
# examples/evaluation_example.py

import asyncio
from evaluation.gaia import GAIAEvaluator
from evaluation.tool_accuracy import ToolAccuracyEvaluator

async def main():
    # GAIA 评估
    gaia_evaluator = GAIAEvaluator()
    gaia_evaluator.load_benchmark("evaluation/benchmarks/gaia_sample.yaml")
    gaia_report = await gaia_evaluator.evaluate_agent(agent)
    print(f"GAIA 准确率: {gaia_report.accuracy:.2%}")

    # 工具准确率评估
    tool_evaluator = ToolAccuracyEvaluator()
    # ... 评估工具调用
    tool_report = tool_evaluator.generate_report()
    print(f"工具准确率: {tool_report.overall_accuracy:.2%}")

if __name__ == "__main__":
    asyncio.run(main())
```
