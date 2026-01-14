#!/usr/bin/env python3
"""
SonarCloud API 客户端 - 下载和分析代码质量问题

使用方式:
    # 方式 1: 使用 .env 文件 (推荐)
    python scripts/sonarcloud_api.py [命令]

    # 方式 2: 使用环境变量
    export SONAR_TOKEN="your-token"
    python scripts/sonarcloud_api.py --org your-org [命令]

命令:
    issues      下载问题列表
    metrics     获取项目指标
    report      生成完整报告
    dashboard   在浏览器中打开 SonarCloud 仪表板

示例:
    python scripts/sonarcloud_api.py report --format html
    python scripts/sonarcloud_api.py metrics
    python scripts/sonarcloud_api.py issues --format csv
"""

import argparse
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode
import webbrowser

try:
    import requests
except ImportError:
    print("请安装 requests: pip install requests")
    sys.exit(1)


def load_env_file() -> None:
    """从 .env 文件加载环境变量"""
    # 查找 .env 文件（按优先级顺序）
    env_paths = [
        Path.cwd() / ".env",  # 当前目录
        Path(__file__).parent.parent / ".env",  # 项目根目录
        Path.home() / ".env",  # 用户主目录（可选）
    ]

    loaded_path = None
    for env_path in env_paths:
        if env_path.exists():
            loaded_path = env_path
            try:
                with env_path.open(encoding="utf-8") as f:
                    loaded_count = 0
                    for line in f:
                        line = line.strip()
                        # 跳过注释和空行
                        if not line or line.startswith("#"):
                            continue
                        # 解析 KEY=VALUE
                        if "=" in line:
                            key, _, value = line.partition("=")
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            # 只设置未设置的环境变量
                            if key and value and key not in os.environ:
                                os.environ[key] = value
                                loaded_count += 1
                    if loaded_count > 0:
                        print(f"[ENV] 已从 {env_path} 加载 {loaded_count} 个环境变量")
            except Exception as e:
                print(f"[ENV] 警告: 读取 {env_path} 失败: {e}")
            break

    if not loaded_path:
        # 不显示警告，因为环境变量可能通过其他方式设置
        pass


# 自动加载 .env 文件
load_env_file()


# ============================================================================
# 配置
# ============================================================================

SONARCLOUD_API = "https://sonarcloud.io/api"
SONARCLOUD_WEB = "https://sonarcloud.io"

PROJECTS = [
    {
        "key_suffix": "ai-agent-backend",
        "name": "Backend (Python)",
        "language": "python",
    },
    {
        "key_suffix": "ai-agent-frontend",
        "name": "Frontend (TypeScript)",
        "language": "typescript",
    },
]

METRICS = [
    "bugs",
    "vulnerabilities",
    "code_smells",
    "coverage",
    "duplicated_lines_density",
    "ncloc",
    "sqale_rating",
    "reliability_rating",
    "security_rating",
    "alert_status",
]


# ============================================================================
# 数据类
# ============================================================================


@dataclass
class Issue:
    key: str
    severity: str
    type: str
    component: str
    line: int | None
    message: str
    status: str
    effort: str | None
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> "Issue":
        return cls(
            key=data.get("key", ""),
            severity=data.get("severity", "UNKNOWN"),
            type=data.get("type", "UNKNOWN"),
            component=data.get("component", "").split(":")[-1],
            line=data.get("line"),
            message=data.get("message", ""),
            status=data.get("status", ""),
            effort=data.get("effort"),
            tags=data.get("tags", []),
        )


@dataclass
class ProjectMetrics:
    bugs: int = 0
    vulnerabilities: int = 0
    code_smells: int = 0
    coverage: float = 0.0
    duplicated_lines_density: float = 0.0
    ncloc: int = 0
    sqale_rating: str = "N/A"
    reliability_rating: str = "N/A"
    security_rating: str = "N/A"
    alert_status: str = "N/A"

    @classmethod
    def from_api(cls, measures: list[dict]) -> "ProjectMetrics":
        metrics = cls()
        rating_map = {"1.0": "A", "2.0": "B", "3.0": "C", "4.0": "D", "5.0": "E"}

        for measure in measures:
            metric = measure.get("metric")
            value = measure.get("value", "0")

            if metric == "bugs":
                metrics.bugs = int(value)
            elif metric == "vulnerabilities":
                metrics.vulnerabilities = int(value)
            elif metric == "code_smells":
                metrics.code_smells = int(value)
            elif metric == "coverage":
                metrics.coverage = float(value)
            elif metric == "duplicated_lines_density":
                metrics.duplicated_lines_density = float(value)
            elif metric == "ncloc":
                metrics.ncloc = int(value)
            elif metric == "sqale_rating":
                metrics.sqale_rating = rating_map.get(value, value)
            elif metric == "reliability_rating":
                metrics.reliability_rating = rating_map.get(value, value)
            elif metric == "security_rating":
                metrics.security_rating = rating_map.get(value, value)
            elif metric == "alert_status":
                metrics.alert_status = value

        return metrics


# ============================================================================
# API 客户端
# ============================================================================


class SonarCloudClient:
    """SonarCloud API 客户端"""

    def __init__(self, token: str, organization: str):
        self.token = token
        self.organization = organization
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }
        )

    def _request(self, endpoint: str, params: dict | None = None) -> dict | None:
        """发送 API 请求"""
        url = f"{SONARCLOUD_API}/{endpoint}"
        if params:
            url = f"{url}?{urlencode(params)}"

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API 请求失败: {e}")
            return None

    def get_project_key(self, suffix: str) -> str:
        """获取完整项目 Key"""
        return f"{self.organization}_{suffix}"

    def get_issues(
        self,
        project_key: str,
        statuses: str = "OPEN,CONFIRMED,REOPENED",
        page_size: int = 100,
        max_pages: int = 10,
    ) -> list[Issue]:
        """获取项目问题列表"""
        issues = []
        page = 1

        while page <= max_pages:
            params = {
                "componentKeys": project_key,
                "statuses": statuses,
                "ps": page_size,
                "p": page,
            }

            response = self._request("issues/search", params)
            if not response:
                break

            for issue_data in response.get("issues", []):
                issues.append(Issue.from_api(issue_data))

            total = response.get("total", 0)
            print(f"  获取问题: 页 {page}, {len(issues)}/{total}")

            if len(issues) >= total:
                break

            page += 1

        return issues

    def get_metrics(self, project_key: str) -> ProjectMetrics:
        """获取项目指标"""
        params = {
            "component": project_key,
            "metricKeys": ",".join(METRICS),
        }

        response = self._request("measures/component", params)
        if not response:
            return ProjectMetrics()

        measures = response.get("component", {}).get("measures", [])
        return ProjectMetrics.from_api(measures)

    def get_quality_gate_status(self, project_key: str) -> dict:
        """获取质量门禁状态"""
        params = {"projectKey": project_key}
        response = self._request("qualitygates/project_status", params)

        if response:
            return response.get("projectStatus", {})
        return {}


# ============================================================================
# 报告生成器
# ============================================================================


class ReportGenerator:
    """报告生成器"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_json(self, data: dict, filename: str = "report.json") -> Path:
        """生成 JSON 报告"""
        filepath = self.output_dir / filename
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        print(f"✓ JSON 报告: {filepath}")
        return filepath

    def generate_csv(self, issues: list[Issue], filename: str = "issues.csv") -> Path:
        """生成 CSV 报告"""
        filepath = self.output_dir / filename

        with filepath.open("w", encoding="utf-8") as f:
            # 写入表头
            f.write("Key,Severity,Type,Component,Line,Message,Status,Effort,Tags\n")

            # 写入数据
            for issue in issues:
                # CSV 转义：双引号需要转义为两个双引号
                escaped_message = issue.message.replace('"', '""')
                row = [
                    issue.key,
                    issue.severity,
                    issue.type,
                    issue.component,
                    str(issue.line or ""),
                    f'"{escaped_message}"',
                    issue.status,
                    issue.effort or "",
                    " ".join(issue.tags),
                ]
                f.write(",".join(row) + "\n")

        print(f"✓ CSV 报告: {filepath}")
        return filepath

    def generate_html(self, data: dict, filename: str = "report.html") -> Path:
        """生成 HTML 报告"""
        filepath = self.output_dir / filename

        html = self._build_html_report(data)

        with filepath.open("w", encoding="utf-8") as f:
            f.write(html)

        print(f"✓ HTML 报告: {filepath}")
        return filepath

    def _build_html_report(self, data: dict) -> str:
        """构建 HTML 报告内容"""
        projects_html = ""

        for project in data.get("projects", []):
            metrics = project.get("metrics", {})
            issues = project.get("issues", [])

            # 指标卡片
            metrics_html = f"""
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-value">{metrics.get("bugs", "N/A")}</div>
                    <div class="metric-label">🐛 Bugs</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics.get("vulnerabilities", "N/A")}</div>
                    <div class="metric-label">🔓 漏洞</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics.get("code_smells", "N/A")}</div>
                    <div class="metric-label">🧹 代码异味</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics.get("coverage", "N/A")}%</div>
                    <div class="metric-label">📊 覆盖率</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics.get("duplicated_lines_density", "N/A")}%</div>
                    <div class="metric-label">📋 重复率</div>
                </div>
                <div class="metric-card rating-{metrics.get("reliability_rating", "N")}">
                    <div class="metric-value">{metrics.get("reliability_rating", "N/A")}</div>
                    <div class="metric-label">可靠性</div>
                </div>
                <div class="metric-card rating-{metrics.get("security_rating", "N")}">
                    <div class="metric-value">{metrics.get("security_rating", "N/A")}</div>
                    <div class="metric-label">安全性</div>
                </div>
                <div class="metric-card rating-{metrics.get("sqale_rating", "N")}">
                    <div class="metric-value">{metrics.get("sqale_rating", "N/A")}</div>
                    <div class="metric-label">可维护性</div>
                </div>
            </div>
            """

            # 问题表格
            issues_rows = ""
            for issue in issues[:100]:  # 最多显示 100 个
                severity_class = f"severity-{issue.get('severity', 'UNKNOWN')}"
                type_class = f"type-{issue.get('type', 'UNKNOWN')}"
                issues_rows += f"""
                <tr>
                    <td class="{severity_class}">{issue.get("severity", "")}</td>
                    <td><span class="{type_class}">{issue.get("type", "")}</span></td>
                    <td class="component">{issue.get("component", "")}</td>
                    <td>{issue.get("line", "-")}</td>
                    <td>{self._escape_html(issue.get("message", ""))}</td>
                </tr>
                """

            projects_html += f"""
            <section class="project">
                <h2>📦 {project.get("name", "Unknown")}</h2>
                <p class="project-key">{project.get("key", "")}</p>
                {metrics_html}
                <h3>问题列表 ({len(issues)} 个)</h3>
                <table class="issues-table">
                    <thead>
                        <tr>
                            <th>严重程度</th>
                            <th>类型</th>
                            <th>文件</th>
                            <th>行号</th>
                            <th>描述</th>
                        </tr>
                    </thead>
                    <tbody>
                        {issues_rows}
                    </tbody>
                </table>
            </section>
            """

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SonarCloud 代码质量报告 - AI Agent</title>
    <style>
        :root {{
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --border: #30363d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --accent: #58a6ff;
            --success: #3fb950;
            --warning: #d29922;
            --error: #f85149;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            padding: 2rem;
            line-height: 1.6;
        }}

        .container {{ max-width: 1400px; margin: 0 auto; }}

        header {{
            text-align: center;
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--border);
        }}

        h1 {{
            color: var(--accent);
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }}

        .timestamp {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}

        .project {{
            margin-bottom: 3rem;
            padding: 2rem;
            background: var(--bg-secondary);
            border-radius: 12px;
            border: 1px solid var(--border);
        }}

        .project h2 {{
            color: var(--accent);
            margin-bottom: 0.25rem;
        }}

        .project-key {{
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-bottom: 1.5rem;
        }}

        .project h3 {{
            color: var(--text-secondary);
            margin: 1.5rem 0 1rem;
            font-size: 1.1rem;
        }}

        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}

        .metric-card {{
            background: var(--bg-primary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.25rem;
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .metric-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}

        .metric-value {{
            font-size: 1.75rem;
            font-weight: bold;
            color: var(--accent);
        }}

        .metric-label {{
            color: var(--text-secondary);
            margin-top: 0.5rem;
            font-size: 0.85rem;
        }}

        .rating-A .metric-value {{ color: var(--success); }}
        .rating-B .metric-value {{ color: #7ee787; }}
        .rating-C .metric-value {{ color: var(--warning); }}
        .rating-D .metric-value {{ color: #f0883e; }}
        .rating-E .metric-value {{ color: var(--error); }}

        .issues-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}

        .issues-table th,
        .issues-table td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}

        .issues-table th {{
            background: var(--bg-primary);
            color: var(--text-secondary);
            font-weight: 600;
            position: sticky;
            top: 0;
        }}

        .issues-table tr:hover {{
            background: rgba(56, 139, 253, 0.1);
        }}

        .component {{
            font-family: 'SF Mono', 'Fira Code', monospace;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}

        .severity-BLOCKER, .severity-CRITICAL {{ color: var(--error); font-weight: bold; }}
        .severity-MAJOR {{ color: #f0883e; }}
        .severity-MINOR {{ color: var(--warning); }}
        .severity-INFO {{ color: var(--text-secondary); }}

        .type-BUG {{
            background: rgba(248, 81, 73, 0.2);
            color: var(--error);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.8rem;
        }}

        .type-VULNERABILITY {{
            background: rgba(240, 136, 62, 0.2);
            color: #f0883e;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.8rem;
        }}

        .type-CODE_SMELL {{
            background: rgba(210, 153, 34, 0.2);
            color: var(--warning);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.8rem;
        }}

        footer {{
            text-align: center;
            color: var(--text-secondary);
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border);
        }}

        footer a {{
            color: var(--accent);
            text-decoration: none;
        }}

        footer a:hover {{
            text-decoration: underline;
        }}

        @media (max-width: 768px) {{
            body {{ padding: 1rem; }}
            .project {{ padding: 1rem; }}
            .metrics {{ grid-template-columns: repeat(2, 1fr); }}
            .issues-table {{ font-size: 0.8rem; }}
            .issues-table th, .issues-table td {{ padding: 0.5rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔍 SonarCloud 代码质量报告</h1>
            <p class="timestamp">生成时间: {data.get("timestamp", "")} | 组织: {data.get("organization", "")}</p>
        </header>

        {projects_html}

        <footer>
            <p>由 <a href="https://sonarcloud.io" target="_blank">SonarCloud</a> 提供代码分析服务</p>
            <p>AI Agent Platform - 代码质量持续改进</p>
        </footer>
    </div>
</body>
</html>"""

    @staticmethod
    def _escape_html(text: str) -> str:
        """转义 HTML 特殊字符"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )


# ============================================================================
# CLI 命令
# ============================================================================


def cmd_issues(client: SonarCloudClient, args: argparse.Namespace) -> None:
    """下载问题列表"""
    all_issues = []

    for proj in PROJECTS:
        project_key = client.get_project_key(proj["key_suffix"])
        print(f"\n📦 {proj['name']} ({project_key})")

        issues = client.get_issues(project_key)
        all_issues.extend(
            [{**issue.__dict__, "project": proj["name"]} for issue in issues]
        )

        print(f"  总计: {len(issues)} 个问题")

    # 生成报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("reports") / f"sonarcloud_{timestamp}"
    generator = ReportGenerator(output_dir)

    if args.format == "json":
        generator.generate_json({"issues": all_issues}, "issues.json")
    elif args.format == "csv":
        generator.generate_csv([Issue(**i) for i in all_issues])

    print(f"\n✅ 共获取 {len(all_issues)} 个问题")


def cmd_metrics(client: SonarCloudClient, args: argparse.Namespace) -> None:
    """获取项目指标"""
    print("\n📊 项目指标概览\n")
    print("-" * 80)

    for proj in PROJECTS:
        project_key = client.get_project_key(proj["key_suffix"])
        print(f"\n📦 {proj['name']}")

        metrics = client.get_metrics(project_key)

        print(f"   🐛 Bugs: {metrics.bugs}")
        print(f"   🔓 漏洞: {metrics.vulnerabilities}")
        print(f"   🧹 代码异味: {metrics.code_smells}")
        print(f"   📊 覆盖率: {metrics.coverage}%")
        print(f"   📋 重复率: {metrics.duplicated_lines_density}%")
        print(f"   📏 代码行数: {metrics.ncloc}")
        print(f"   🎯 可靠性评级: {metrics.reliability_rating}")
        print(f"   🔒 安全评级: {metrics.security_rating}")
        print(f"   🔧 可维护性评级: {metrics.sqale_rating}")
        print(f"   🚦 质量门禁: {metrics.alert_status}")


def cmd_report(client: SonarCloudClient, args: argparse.Namespace) -> None:
    """生成完整报告"""
    print("\n📝 生成完整报告...\n")

    report_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "organization": client.organization,
        "projects": [],
    }

    for proj in PROJECTS:
        project_key = client.get_project_key(proj["key_suffix"])
        print(f"📦 {proj['name']} ({project_key})")

        # 获取指标
        metrics = client.get_metrics(project_key)

        # 获取问题
        issues = client.get_issues(project_key)

        project_data = {
            "name": proj["name"],
            "key": project_key,
            "language": proj["language"],
            "metrics": {
                "bugs": metrics.bugs,
                "vulnerabilities": metrics.vulnerabilities,
                "code_smells": metrics.code_smells,
                "coverage": metrics.coverage,
                "duplicated_lines_density": metrics.duplicated_lines_density,
                "ncloc": metrics.ncloc,
                "reliability_rating": metrics.reliability_rating,
                "security_rating": metrics.security_rating,
                "sqale_rating": metrics.sqale_rating,
                "alert_status": metrics.alert_status,
            },
            "issues": [issue.__dict__ for issue in issues],
        }

        report_data["projects"].append(project_data)
        print(f"  ✓ 指标和问题已获取 ({len(issues)} 个问题)")

    # 生成报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("reports") / f"sonarcloud_{timestamp}"
    generator = ReportGenerator(output_dir)

    # 始终生成 JSON
    generator.generate_json(report_data)

    # 根据格式生成其他报告
    if args.format == "csv":
        all_issues = []
        for proj in report_data["projects"]:
            all_issues.extend([Issue(**i) for i in proj["issues"]])
        generator.generate_csv(all_issues)
    elif args.format == "html":
        generator.generate_html(report_data)
    elif args.format == "all":
        all_issues = []
        for proj in report_data["projects"]:
            all_issues.extend([Issue(**i) for i in proj["issues"]])
        generator.generate_csv(all_issues)
        generator.generate_html(report_data)

    print(f"\n✅ 报告已生成: {output_dir}")


def cmd_dashboard(client: SonarCloudClient, args: argparse.Namespace) -> None:
    """打开 SonarCloud 仪表板"""
    for proj in PROJECTS:
        project_key = client.get_project_key(proj["key_suffix"])
        url = f"{SONARCLOUD_WEB}/project/overview?id={project_key}"
        print(f"🌐 打开: {url}")
        webbrowser.open(url)


# ============================================================================
# 主程序
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SonarCloud API 客户端 - 下载和分析代码质量问题",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
快速开始:
  # 1. 在 .env 文件中配置 (推荐)
  #    在项目根目录创建 .env 文件:
  #    SONAR_TOKEN=your-token
  #    SONAR_ORGANIZATION=your-github-org

  # 2. 生成 HTML 报告
  python scripts/sonarcloud_api.py report --format html

  # 3. 查看指标
  python scripts/sonarcloud_api.py metrics

  # 4. 下载问题列表
  python scripts/sonarcloud_api.py issues --format csv

常用命令:
  report --format html    生成完整的 HTML 报告 (默认)
  report --format all     生成所有格式的报告 (json, csv, html)
  metrics                 查看项目指标概览
  issues --format csv     下载问题列表为 CSV
  dashboard               在浏览器中打开 SonarCloud 仪表板

配置文件 (.env):
  位置: 项目根目录或当前目录的 .env 文件
  必需配置:
    SONAR_TOKEN=your-token              # 从 https://sonarcloud.io/account/security 获取
    SONAR_ORGANIZATION=your-github-org   # 你的 GitHub 用户名或组织名

环境变量 (替代方案):
  SONAR_TOKEN         SonarCloud 访问令牌 (必需)
  SONAR_ORGANIZATION  组织名 (可用 --org 参数覆盖)
        """,
    )

    parser.add_argument(
        "--org",
        "-o",
        default=os.environ.get("SONAR_ORGANIZATION", ""),
        help="SonarCloud 组织名 (默认从 SONAR_ORGANIZATION 环境变量读取)",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # issues 命令
    issues_parser = subparsers.add_parser("issues", help="下载问题列表")
    issues_parser.add_argument(
        "--format",
        "-f",
        choices=["json", "csv"],
        default="json",
        help="输出格式 (默认: json)",
    )

    # metrics 命令
    subparsers.add_parser("metrics", help="获取项目指标")

    # report 命令
    report_parser = subparsers.add_parser("report", help="生成完整报告")
    report_parser.add_argument(
        "--format",
        "-f",
        choices=["json", "csv", "html", "all"],
        default="html",
        help="输出格式 (默认: html)",
    )

    # dashboard 命令
    subparsers.add_parser("dashboard", help="在浏览器中打开 SonarCloud 仪表板")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 检查 Token
    token = os.environ.get("SONAR_TOKEN")
    if not token:
        print("❌ 错误: SONAR_TOKEN 未配置")
        print("")
        print("请通过以下方式之一配置:")
        print("")
        print("方式 1: 在 .env 文件中配置 (推荐)")
        print("  在项目根目录或当前目录创建 .env 文件，添加:")
        print("    SONAR_TOKEN=your-token")
        print("    SONAR_ORGANIZATION=your-org")
        print("")
        print("方式 2: 设置环境变量")
        print("  Linux/Mac: export SONAR_TOKEN=your-token")
        print("  Windows:   $env:SONAR_TOKEN = 'your-token'")
        print("")
        print("获取 Token:")
        print("  https://sonarcloud.io/account/security")
        sys.exit(1)

    # 检查组织名
    if not args.org:
        print("❌ 错误: 组织名未配置")
        print("")
        print("请通过以下方式之一配置:")
        print("")
        print("方式 1: 在 .env 文件中添加:")
        print("    SONAR_ORGANIZATION=your-github-username-or-org")
        print("")
        print("方式 2: 使用命令行参数:")
        print("    python sonarcloud_api.py --org your-org report")
        print("")
        print("组织名通常是你的 GitHub 用户名或组织名")
        sys.exit(1)

    print(f"[TOKEN] {'*' * 8}...{token[-4:]}")
    print(f"[ORG] {args.org}")
    print("")

    # 创建客户端
    client = SonarCloudClient(token, args.org)

    # 执行命令
    commands = {
        "issues": cmd_issues,
        "metrics": cmd_metrics,
        "report": cmd_report,
        "dashboard": cmd_dashboard,
    }

    commands[args.command](client, args)


if __name__ == "__main__":
    main()
