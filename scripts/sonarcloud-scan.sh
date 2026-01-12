#!/bin/bash
# ==============================================================================
# SonarCloud 扫描与问题报告脚本 (Linux/Mac)
# ==============================================================================
# 使用方式:
#   export SONAR_TOKEN="your-token"
#   ./scripts/sonarcloud-scan.sh [backend|frontend|all] [--skip-scan] [--format json|csv|html]
#
# 参数说明:
#   第一个参数    扫描目标: backend, frontend, all (默认: all)
#   --skip-scan   跳过扫描，只下载问题报告
#   --format      导出格式: json, csv, html (默认: json)
#   --org         SonarCloud 组织名 (默认: 从 git remote 获取)
# ==============================================================================

set -e

# SonarCloud API 基础 URL
SONARCLOUD_API="https://sonarcloud.io/api"

# 默认值
TARGET="all"
SKIP_SCAN=false
EXPORT_FORMAT="json"
ORGANIZATION=""

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        backend|frontend|all|help)
            TARGET="$1"
            shift
            ;;
        --skip-scan)
            SKIP_SCAN=true
            shift
            ;;
        --format)
            EXPORT_FORMAT="$2"
            shift 2
            ;;
        --org)
            ORGANIZATION="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}未知参数: $1${NC}"
            exit 1
            ;;
    esac
done

# 检查环境
check_env() {
    if [ -z "$SONAR_TOKEN" ]; then
        echo -e "${RED}错误: SONAR_TOKEN 环境变量未设置${NC}"
        echo "请设置: export SONAR_TOKEN=your-sonarcloud-token"
        exit 1
    fi
    
    if [ "$SKIP_SCAN" = false ] && ! command -v sonar-scanner &> /dev/null; then
        echo -e "${RED}错误: sonar-scanner 未安装${NC}"
        echo "请安装: https://docs.sonarqube.org/latest/analysis/scan/sonarscanner/"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        echo -e "${YELLOW}警告: jq 未安装，JSON 处理功能受限${NC}"
        echo "建议安装: brew install jq 或 apt install jq"
    fi
}

# 获取组织名
get_organization() {
    if [ -n "$ORGANIZATION" ]; then
        echo "$ORGANIZATION"
        return
    fi
    
    # 尝试从 git remote 获取
    local remote_url
    remote_url=$(git remote get-url origin 2>/dev/null || echo "")
    
    if [[ $remote_url =~ github\.com[:/]([^/]+)/ ]]; then
        echo "${BASH_REMATCH[1]}"
        return
    fi
    
    echo -e "${YELLOW}无法自动获取组织名，请使用 --org 参数指定${NC}" >&2
    echo "your-org"
}

# 扫描后端
scan_backend() {
    local org=$1
    
    echo -e "${CYAN}==========================================${NC}"
    echo -e "${CYAN}  扫描后端 (Python) - SonarCloud${NC}"
    echo -e "${CYAN}==========================================${NC}"
    
    cd backend
    
    # 生成覆盖率报告
    echo -e "${BLUE}>> 运行测试并生成覆盖率报告...${NC}"
    python -m pytest --cov --cov-report=xml:coverage.xml --junitxml=test-results.xml -q 2>/dev/null || true
    
    # 运行 SonarCloud 扫描
    echo -e "${BLUE}>> 运行 SonarCloud 扫描...${NC}"
    sonar-scanner \
        -Dsonar.host.url=https://sonarcloud.io \
        -Dsonar.organization="$org" \
        -Dsonar.projectKey="${org}_ai-agent-backend" \
        -Dsonar.token="$SONAR_TOKEN"
    
    cd ..
    echo -e "${GREEN}✓ 后端扫描完成${NC}"
}

# 扫描前端
scan_frontend() {
    local org=$1
    
    echo -e "${CYAN}==========================================${NC}"
    echo -e "${CYAN}  扫描前端 (TypeScript) - SonarCloud${NC}"
    echo -e "${CYAN}==========================================${NC}"
    
    cd frontend
    
    # 安装依赖
    if [ ! -d "node_modules" ]; then
        echo -e "${BLUE}>> 安装依赖...${NC}"
        npm ci
    fi
    
    # 生成覆盖率报告
    echo -e "${BLUE}>> 运行测试并生成覆盖率报告...${NC}"
    npm run test:coverage 2>/dev/null || true
    
    # 运行 SonarCloud 扫描
    echo -e "${BLUE}>> 运行 SonarCloud 扫描...${NC}"
    sonar-scanner \
        -Dsonar.host.url=https://sonarcloud.io \
        -Dsonar.organization="$org" \
        -Dsonar.projectKey="${org}_ai-agent-frontend" \
        -Dsonar.token="$SONAR_TOKEN"
    
    cd ..
    echo -e "${GREEN}✓ 前端扫描完成${NC}"
}

# 调用 SonarCloud API
call_api() {
    local endpoint=$1
    local params=$2
    
    local url="$SONARCLOUD_API/$endpoint"
    if [ -n "$params" ]; then
        url="$url?$params"
    fi
    
    curl -s -H "Authorization: Bearer $SONAR_TOKEN" "$url"
}

# 获取项目问题
get_issues() {
    local project_key=$1
    local page=1
    local page_size=100
    
    echo -e "${BLUE}>> 获取项目问题: $project_key${NC}" >&2
    
    local all_issues="[]"
    
    while true; do
        local response
        response=$(call_api "issues/search" "componentKeys=$project_key&ps=$page_size&p=$page&statuses=OPEN,CONFIRMED,REOPENED")
        
        if [ -z "$response" ]; then
            break
        fi
        
        local total
        total=$(echo "$response" | jq -r '.total // 0')
        local issues
        issues=$(echo "$response" | jq '.issues // []')
        
        if command -v jq &> /dev/null; then
            all_issues=$(echo "$all_issues $issues" | jq -s 'add')
        fi
        
        local count
        count=$(echo "$all_issues" | jq 'length')
        echo -e "   页 $page, 已获取 $count/$total 个问题" >&2
        
        if [ "$count" -ge "$total" ] || [ "$page" -ge 10 ]; then
            break
        fi
        
        ((page++))
    done
    
    echo "$all_issues"
}

# 获取项目指标
get_metrics() {
    local project_key=$1
    local metrics="bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,ncloc"
    
    call_api "measures/component" "component=$project_key&metricKeys=$metrics"
}

# 生成 HTML 报告
generate_html_report() {
    local report_file=$1
    local output_file=$2
    
    cat > "$output_file" << 'EOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SonarCloud 代码质量报告</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 2rem; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #58a6ff; margin-bottom: 1.5rem; border-bottom: 1px solid #30363d; padding-bottom: 1rem; }
        h2 { color: #8b949e; margin: 1.5rem 0 1rem; font-size: 1.2rem; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .metric-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.5rem; text-align: center; }
        .metric-value { font-size: 2rem; font-weight: bold; color: #58a6ff; }
        .metric-label { color: #8b949e; margin-top: 0.5rem; }
        .issues-table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        .issues-table th, .issues-table td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #30363d; }
        .issues-table th { background: #161b22; color: #8b949e; font-weight: 600; }
        .severity-BLOCKER, .severity-CRITICAL { color: #f85149; }
        .severity-MAJOR { color: #f0883e; }
        .severity-MINOR { color: #d29922; }
        .type-BUG { background: #f8514933; color: #f85149; padding: 0.25rem 0.5rem; border-radius: 4px; }
        .type-VULNERABILITY { background: #f0883e33; color: #f0883e; padding: 0.25rem 0.5rem; border-radius: 4px; }
        .type-CODE_SMELL { background: #d2992233; color: #d29922; padding: 0.25rem 0.5rem; border-radius: 4px; }
        .timestamp { color: #8b949e; font-size: 0.875rem; margin-top: 2rem; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 SonarCloud 代码质量报告</h1>
        <p class="timestamp">由 SonarCloud 扫描脚本生成</p>
        <div id="report-content"></div>
    </div>
    <script>
EOF
    
    echo "const reportData = $(cat "$report_file");" >> "$output_file"
    
    cat >> "$output_file" << 'EOF'
        function renderReport() {
            const container = document.getElementById('report-content');
            let html = '';
            
            reportData.projects.forEach(project => {
                html += `<h2>📦 ${project.name}</h2>`;
                html += '<div class="metrics">';
                html += `<div class="metric-card"><div class="metric-value">${project.metrics?.bugs || 'N/A'}</div><div class="metric-label">🐛 Bugs</div></div>`;
                html += `<div class="metric-card"><div class="metric-value">${project.metrics?.vulnerabilities || 'N/A'}</div><div class="metric-label">🔓 漏洞</div></div>`;
                html += `<div class="metric-card"><div class="metric-value">${project.metrics?.code_smells || 'N/A'}</div><div class="metric-label">🧹 代码异味</div></div>`;
                html += `<div class="metric-card"><div class="metric-value">${project.metrics?.coverage || 'N/A'}%</div><div class="metric-label">📊 覆盖率</div></div>`;
                html += '</div>';
                
                html += `<h3>问题列表 (${project.issues?.length || 0} 个)</h3>`;
                html += '<table class="issues-table"><thead><tr><th>严重程度</th><th>类型</th><th>文件</th><th>行号</th><th>描述</th></tr></thead><tbody>';
                
                (project.issues || []).slice(0, 50).forEach(issue => {
                    const component = issue.component?.split(':').pop() || '';
                    html += `<tr>
                        <td class="severity-${issue.severity}">${issue.severity}</td>
                        <td><span class="type-${issue.type}">${issue.type}</span></td>
                        <td>${component}</td>
                        <td>${issue.line || '-'}</td>
                        <td>${issue.message}</td>
                    </tr>`;
                });
                
                html += '</tbody></table>';
            });
            
            container.innerHTML = html;
        }
        renderReport();
    </script>
</body>
</html>
EOF
    
    echo -e "${GREEN}✓ 已导出到: $output_file${NC}"
}

# 下载问题报告
download_issues_report() {
    local org=$1
    
    echo -e "${CYAN}==========================================${NC}"
    echo -e "${CYAN}  下载 SonarCloud 问题报告${NC}"
    echo -e "${CYAN}==========================================${NC}"
    
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local report_dir="reports/sonarcloud_$timestamp"
    mkdir -p "$report_dir"
    
    local projects=(
        "${org}_ai-agent-backend:Backend (Python)"
        "${org}_ai-agent-frontend:Frontend (TypeScript)"
    )
    
    # 初始化报告 JSON
    local report_json='{"timestamp":"'"$(date '+%Y-%m-%d %H:%M:%S')"'","organization":"'"$org"'","projects":[]}'
    
    for proj_info in "${projects[@]}"; do
        IFS=':' read -r project_key project_name <<< "$proj_info"
        
        echo ""
        echo -e "${BLUE}处理项目: $project_name${NC}"
        
        # 获取问题
        local issues
        issues=$(get_issues "$project_key")
        
        # 获取指标
        local metrics_response
        metrics_response=$(get_metrics "$project_key")
        
        # 解析指标
        local bugs vulnerabilities code_smells coverage duplicated
        if command -v jq &> /dev/null; then
            bugs=$(echo "$metrics_response" | jq -r '.component.measures[] | select(.metric=="bugs") | .value // "N/A"')
            vulnerabilities=$(echo "$metrics_response" | jq -r '.component.measures[] | select(.metric=="vulnerabilities") | .value // "N/A"')
            code_smells=$(echo "$metrics_response" | jq -r '.component.measures[] | select(.metric=="code_smells") | .value // "N/A"')
            coverage=$(echo "$metrics_response" | jq -r '.component.measures[] | select(.metric=="coverage") | .value // "N/A"')
            duplicated=$(echo "$metrics_response" | jq -r '.component.measures[] | select(.metric=="duplicated_lines_density") | .value // "N/A"')
        fi
        
        echo -e "   - 总问题数: $(echo "$issues" | jq 'length')"
        echo -e "   - Bugs: $bugs"
        echo -e "   - 漏洞: $vulnerabilities"
        echo -e "   - 代码异味: $code_smells"
        echo -e "   - 覆盖率: ${coverage}%"
        
        # 构建项目报告
        local project_report
        project_report=$(jq -n \
            --arg name "$project_name" \
            --arg key "$project_key" \
            --arg bugs "$bugs" \
            --arg vulnerabilities "$vulnerabilities" \
            --arg code_smells "$code_smells" \
            --arg coverage "$coverage" \
            --arg duplicated "$duplicated" \
            --argjson issues "$issues" \
            '{
                name: $name,
                key: $key,
                metrics: {
                    bugs: $bugs,
                    vulnerabilities: $vulnerabilities,
                    code_smells: $code_smells,
                    coverage: $coverage,
                    duplicated_lines_density: $duplicated
                },
                issues: $issues
            }')
        
        # 添加到报告
        report_json=$(echo "$report_json" | jq --argjson proj "$project_report" '.projects += [$proj]')
    done
    
    # 导出报告
    echo ""
    echo -e "${BLUE}>> 导出报告...${NC}"
    
    local json_file="$report_dir/report.json"
    echo "$report_json" | jq '.' > "$json_file"
    echo -e "${GREEN}✓ 已导出到: $json_file${NC}"
    
    case $EXPORT_FORMAT in
        csv)
            echo "$report_json" | jq -r '.projects[].issues[] | [.key, .severity, .type, .component, .line, .message, .status] | @csv' > "$report_dir/issues.csv"
            echo -e "${GREEN}✓ 已导出到: $report_dir/issues.csv${NC}"
            ;;
        html)
            generate_html_report "$json_file" "$report_dir/report.html"
            ;;
    esac
    
    echo ""
    echo -e "${GREEN}==========================================${NC}"
    echo -e "${GREEN}  报告已生成: $report_dir${NC}"
    echo -e "${GREEN}==========================================${NC}"
}

# 显示帮助
show_help() {
    cat << EOF

SonarCloud 扫描与问题报告脚本

使用方式:
  ./sonarcloud-scan.sh [target] [options]

目标:
  backend     只扫描后端
  frontend    只扫描前端
  all         扫描全部 (默认)
  help        显示此帮助

选项:
  --skip-scan     跳过扫描，只下载问题报告
  --format TYPE   导出格式: json, csv, html (默认: json)
  --org NAME      SonarCloud 组织名 (默认从 git remote 获取)

示例:
  # 完整扫描并生成 JSON 报告
  ./sonarcloud-scan.sh

  # 只扫描后端
  ./sonarcloud-scan.sh backend

  # 跳过扫描，只下载问题并生成 HTML 报告
  ./sonarcloud-scan.sh --skip-scan --format html

  # 指定组织名
  ./sonarcloud-scan.sh --org myorg --skip-scan

环境变量:
  SONAR_TOKEN    SonarCloud 访问令牌 (必需)

依赖:
  - sonar-scanner (扫描需要)
  - jq (JSON 处理，强烈建议安装)
  - curl

EOF
}

# 主函数
main() {
    if [ "$TARGET" = "help" ]; then
        show_help
        exit 0
    fi
    
    check_env
    
    local org
    org=$(get_organization)
    
    echo -e "${CYAN}组织: $org${NC}"
    echo ""
    
    # 运行扫描
    if [ "$SKIP_SCAN" = false ]; then
        case $TARGET in
            backend)
                scan_backend "$org"
                ;;
            frontend)
                scan_frontend "$org"
                ;;
            all)
                scan_backend "$org"
                scan_frontend "$org"
                ;;
        esac
        
        echo ""
        echo -e "${YELLOW}等待 SonarCloud 处理结果 (30秒)...${NC}"
        sleep 30
    fi
    
    # 下载问题报告
    download_issues_report "$org"
}

main
