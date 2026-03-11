```bash
#!/bin/bash
# ==============================================================================
# 命令行计算器部署脚本
# 版本: 1.0.0
# 作者: 运维工程师
# 日期: 2026-03-10
# ==============================================================================

set -euo pipefail

# ==============================================================================
# 配置变量
# ==============================================================================
readonly SCRIPT_NAME=$(basename "$0")
readonly SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
readonly TIMESTAMP=$(date +%Y%m%d_%H%M%S)
readonly LOG_FILE="/var/log/calc_deploy_${TIMESTAMP}.log"

# 部署配置
readonly APP_NAME="calc"
readonly APP_VERSION="1.0.0"
readonly DEPLOY_USER="${DEPLOY_USER:-$(whoami)}"
readonly DEPLOY_DIR="${DEPLOY_DIR:-/opt/calc}"
readonly BACKUP_DIR="${BACKUP_DIR:-/opt/calc/backups}"
readonly CONFIG_DIR="${CONFIG_DIR:-/etc/calc}"
readonly DATA_DIR="${DATA_DIR:-/var/lib/calc}"
readonly SOURCE_CODE="${SOURCE_CODE:-code_v1_20260310_004608.py}"

# Python 配置
readonly REQUIRED_PYTHON_VERSION="3.8"
readonly PYTHON_CMD="${PYTHON_CMD:-python3}"

# ==============================================================================
# 颜色定义
# ==============================================================================
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# ==============================================================================
# 日志函数
# ==============================================================================
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # 输出到控制台
    case "$level" in
        INFO)  echo -e "${GREEN}[INFO]${NC} $message" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $message" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" ;;
        DEBUG) echo -e "${BLUE}[DEBUG]${NC} $message" ;;
    esac
    
    # 写入日志文件
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE" 2>/dev/null || true
}

# ==============================================================================
# 使用说明
# ==============================================================================
show_help() {
    cat << EOF
命令行计算器部署脚本

用法: $SCRIPT_NAME [选项]

选项:
    -h, --help          显示此帮助信息
    -d, --deploy        执行部署
    -r, --rollback      执行回滚
    -c, --check         仅执行健康检查
    -b, --backup        仅执行备份
    -t, --test          部署后运行测试
    -f, --force         强制部署（跳过确认）
    -v, --version       显示版本信息

示例:
    $SCRIPT_NAME --deploy          # 执行完整部署
    $SCRIPT_NAME --deploy --test   # 部署并运行测试
    $SCRIPT_NAME --rollback        # 回滚到上一个版本
    $SCRIPT_NAME --check           # 仅执行健康检查

环境变量:
    DEPLOY_DIR          部署目录 (默认: /opt/calc)
    BACKUP_DIR          备份目录 (默认: /opt/calc/backups)
    CONFIG_DIR          配置目录 (默认: /etc/calc)
    SOURCE_CODE         源代码文件 (默认: code_v1_20260310_004608.py)
    PYTHON_CMD          Python 命令 (默认: python3)
EOF
}

# ==============================================================================
# 版本信息
# ==============================================================================
show_version() {
    echo "$APP_NAME 部署脚本 v$APP_VERSION"
    echo "被测版本: code_v1_20260310_004608.py"
}

# ==============================================================================
# 错误处理
# ==============================================================================
error_exit() {
    log ERROR "$1"
    exit 1
}

trap 'error_exit "脚本执行失败，行号: $LINENO"' ERR

# ==============================================================================
# 1. 环境检查
# ==============================================================================
check_environment() {
    log INFO "开始环境检查..."
    
    # 检查操作系统
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        log WARN "当前不是 Linux 系统，部分功能可能受限"
    fi
    
    # 检查 Python 版本
    if ! command -v "$PYTHON_CMD" &> /dev/null; then
        error_exit "未找到 $PYTHON_CMD，请安装 Python $REQUIRED_PYTHON_VERSION+"
    fi
    
    local python_version=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    log INFO "检测到 Python 版本: $python_version"
    
    # 版本号比较
    if ! $PYTHON_CMD -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
        error_exit "Python 版本必须 >= $REQUIRED_PYTHON_VERSION，当前版本: $python_version"
    fi
    
    # 检查必要的 Python 模块
    log INFO "检查 Python 标准库模块..."
    local required_modules=("math" "json" "re" "datetime" "enum" "typing" "dataclasses")
    for module in "${required_modules[@]}"; do
        if ! $PYTHON_CMD -c "import $module" 2>/dev/null; then
            error_exit "缺少必要的 Python 模块: $module"
        fi
    done
    
    # 检查磁盘空间
    local available_space=$(df "$DEPLOY_DIR" 2>/dev/null | awk 'NR==2 {print $4}' || echo "0")
    if [[ "$available_space" -lt 10240 ]]; then  # 10MB
        log WARN "磁盘空间不足 10MB，请检查磁盘空间"
    else
        log INFO "磁盘空间充足: ${available_space}KB"
    fi
    
    # 检查权限
    if [[ "$EUID" -eq 0 ]]; then
        log WARN "以 root 用户运行，建议以普通用户运行"
    fi
    
    # 检查必要的命令
    local required_commands=("cp" "mv" "chmod" "mkdir" "rm")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            error_exit "缺少必要的命令: $cmd"
        fi
    done
    
    log INFO "环境检查通过"
    return 0
}

# ==============================================================================
# 2. 备份策略
# ==============================================================================
create_backup() {
    log INFO "开始创建备份..."
    
    # 创建备份目录
    if [[ ! -d "$BACKUP_DIR" ]]; then
        mkdir -p "$BACKUP_DIR" || error_exit "无法创建备份目录: $BACKUP_DIR"
    fi
    
    local backup_name="calc_backup_${TIMESTAMP}"
    local backup_path="${BACKUP_DIR}/${backup_name}.tar.gz"
    
    # 如果存在现有部署，则备份
    if [[ -d "$DEPLOY_DIR" ]] && [[ -f "${DEPLOY_DIR}/calc.py" ]]; then
        log INFO "备份现有部署到: $backup_path"
        
        # 创建临时备份清单
        local temp_list=$(mktemp)
        find "$DEPLOY_DIR" -type f > "$temp_list" 2>/dev/null || true
        
        if [[ -s "$temp_list" ]]; then
            tar -czf "$backup_path" -T "$temp_list" 2>/dev/null || {
                rm -f "$temp_list"
                error_exit "备份创建失败"
            }
            log INFO "备份创建成功: $backup_path"
        else
            log INFO "没有现有文件需要备份"
        fi
        
        rm -f "$temp_list"
        
        # 保留最近 10 个备份
        local backup_count=$(ls -1t "${BACKUP_DIR}"/calc_backup_*.tar.gz 2>/dev/null | wc -l)
        if [[ "$backup_count" -gt 10 ]]; then
            log INFO "清理旧备份，保留最近 10 个"
            ls -1t "${BACKUP_DIR}"/calc_backup_*.tar.gz | tail -n +11 | xargs -r rm -f
        fi
    else
        log INFO "没有现有部署，跳过备份"
    fi
    
    echo "$backup_path"
}

# 列出可用备份
list_backups() {
    log INFO "可用备份列表:"
    if [[ -d "$BACKUP_DIR" ]]; then
        ls -1t "${BACKUP_DIR}"/calc_backup_*.tar.gz 2>/dev/null | while read -r backup; do
            local size=$(du -h "$backup" 2>/dev/null | cut -f1)
            local date=$(stat -c %y "$backup" 2>/dev/null | cut -d' ' -f1)
            echo "  - $(basename "$backup") ($size, $date)"
        done
    else
        echo "  无可用备份"
    fi
}

# ==============================================================================
# 3. 部署步骤
# ==============================================================================
deploy_code() {
    log INFO "开始部署代码..."
    
    # 检查源代码文件
    if [[ ! -f "$SOURCE_CODE" ]]; then
        # 尝试在当前目录查找
        if [[ -f "${SCRIPT_DIR}/${SOURCE_CODE}" ]]; then
            SOURCE_CODE="${SCRIPT_DIR}/${SOURCE_CODE}"
        else
            error_exit "源代码文件不存在: $SOURCE_CODE"
        fi
    fi
    
    # 创建部署目录
    log INFO "创建部署目录: $DEPLOY_DIR"
    mkdir -p "$DEPLOY_DIR" || error_exit "无法创建部署目录"
    mkdir -p "$CONFIG_DIR" || error_exit "无法创建配置目录"
    mkdir -p "$DATA_DIR" || error_exit "无法创建数据目录"
    
    # 部署主程序
    local target_file="${DEPLOY_DIR}/calc.py"
    log INFO "复制源代码到: $target_file"
    cp "$SOURCE_CODE" "$target_file" || error_exit "复制源代码失败"
    chmod 755 "$target_file" || error_exit "设置权限失败"
    
    # 创建启动脚本
    local bin_file="/usr/local/bin/calc"
    log INFO "创建启动脚本: $bin_file"
    cat > "$bin_file" << 'EOF'
#!/bin/bash
# 命令行计算器启动脚本
DEPLOY_DIR="${DEPLOY_DIR:-/opt/calc}"
exec python3 "${DEPLOY_DIR}/calc.py" "$@"
EOF
    chmod 755 "$bin_file" || log WARN "设置启动脚本权限失败（可能需要 sudo）"
    
    # 创建配置文件
    local config_file="${CONFIG_DIR}/calc.conf"
    log INFO "创建配置文件: $config_file"
    cat > "$config_file" << EOF
# 命令行计算器配置文件
# 生成时间: $(date)

# 历史记录配置
HISTORY_FILE="${DATA_DIR}/history.json"
MAX_HISTORY=100

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=/var/log/calc.log

# 精度配置
DEFAULT_PRECISION=6
EOF
    chmod 644 "$config_file" || log WARN "设置配置文件权限失败"
    
    log INFO "代码部署完成"
}

# ==============================================================================
# 4. 健康检查
# ==============================================================================
health_check() {
    log INFO "开始健康检查..."
    
    local check_passed=true
    
    # 检查文件是否存在
    local target_file="${DEPLOY_DIR}/calc.py"
    if [[ ! -f "$target_file" ]]; then
        log ERROR "主程序文件不存在: $target_file"
        check_passed=false
    else
        log INFO "✓ 主程序文件存在"
    fi
    
    # 检查文件权限
    if [[ -f "$target_file" ]] && [[ ! -x "$target_file" ]]; then
        log WARN "主程序文件不可执行，尝试修复..."
        chmod 755 "$target_file" || check_passed=false
    fi
    
    # 检查 Python 语法
    if [[ -f "$target_file" ]]; then
        if $PYTHON_CMD -m py_compile "$target_file" 2>/dev/null; then
            log INFO "✓ Python 语法检查通过"
        else
            log ERROR "Python 语法检查失败"
            check_passed=false
        fi
    fi
    
    # 功能测试
    log INFO "执行功能测试..."
    
    # 测试基本运算
    local test_result
    if test_result=$($PYTHON_CMD "$target_file" "1 + 2" 2>&1); then
        if [[ "$test_result" == "3" ]]; then
            log INFO "✓ 基本加法测试通过 (1 + 2 = 3)"
        else
            log ERROR "基本加法测试失败，期望: 3，实际: $test_result"
            check_passed=false
        fi
    else
        log ERROR "基本加法测试执行失败: $test_result"
        check_passed=false
    fi
    
    # 测试复杂表达式
    if test_result=$($PYTHON_CMD "$target_file" "(1 + 2) * 3" 2>&1); then
        if [[ "$test_result" == "9" ]]; then
            log INFO "✓ 复杂表达式测试通过 ((1 + 2) * 3 = 9)"
        else
            log ERROR "复杂表达式测试失败，期望: 9，实际: $test_result"
            check_passed=false
        fi
    else
        log ERROR "复杂表达式测试执行失败: $test_result"
        check_passed=false
    fi
    
    # 测试科学计算
    if test_result=$($PYTHON_CMD "$target_file" "sqrt(16)" 2>&1); then
        if [[ "$test_result" == "4" ]]; then
            log INFO "✓ 科学计算测试通过 (sqrt(16) = 4)"
        else
            log ERROR "科学计算测试失败，期望: 4，实际: $test_result"
            check_passed=false
        fi
    else
        log ERROR "科学计算测试执行失败: $test_result"
        check_passed=false
    fi
    
    # 测试进制转换
    if test_result=$($PYTHON_CMD "$target_file" "255 to hex" 2>&1); then
        if [[ "$test_result" == "0xFF" ]]; then
            log INFO "✓ 进制转换测试通过 (255 to hex = 0xFF)"
        else
            log ERROR "进制转换测试失败，期望: 0xFF，实际: $test_result"
            check_passed=false
        fi
    else
        log ERROR "进制转换测试执行失败: $test_result"
        check_passed=false
    fi
    
    # 测试错误处理
    if test_result=$($PYTHON_CMD "$target_file" "1 / 0" 2>&1); then
        if [[ "$test_result" == *"Error"* ]] || [[ "$test_result" == *"Division by zero"* ]]; then
            log INFO "✓ 错误处理测试通过 (除零错误正确捕获)"
        else
            log WARN "错误处理测试可能存在问题，输出: $test_result"
        fi
    else
        log INFO "✓ 错误处理测试通过 (除零错误正确捕获)"
    fi
    
    # 检查帮助信息
    if $PYTHON_CMD "$target_file" --help &>/dev/null; then
        log INFO "✓ 帮助信息功能正常"
    else
        log WARN "帮助信息功能可能异常"
    fi
    
    if $check_passed; then
        log INFO "健康检查全部通过"
        return 0
    else
        log ERROR "健康检查未通过"
        return 1
    fi
}

# ==============================================================================
# 5. 回滚策略
# ==============================================================================
rollback() {
    log INFO "开始执行回滚..."
    
    # 查找最新的备份
    if [[ ! -d "$BACKUP_DIR" ]]; then
        error_exit "备份目录不存在，无法回滚"
    fi
    
    local latest_backup=$(ls -1t "${BACKUP_DIR}"/calc_backup_*.tar.gz 2>/dev/null | head -1)
    
    if [[ -z "$latest_backup" ]]; then
        error_exit "没有找到可用的备份"
    fi
    
    log INFO "使用备份: $latest_backup"
    
    # 确认回滚
    if [[ "${FORCE:-false}" != "true" ]]; then
        read -p "确定要回滚到上一个版本吗? (y/N): " confirm
        if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
            log INFO "回滚已取消"
            return 0
        fi
    fi
    
    # 备份当前状态（如果存在）
    if [[ -d "$DEPLOY_DIR" ]] && [[ -f "${DEPLOY_DIR}/calc.py" ]]; then
        local current_backup="${BACKUP_DIR}/calc_rollback_${TIMESTAMP}.tar.gz"
        log INFO "备份当前状态到: $current_backup"
        tar -czf "$current_backup" -C "$DEPLOY_DIR" . 2>/dev/null || log WARN "当前状态备份失败"
    fi
    
    # 执行回滚
    log INFO "恢复备份文件..."
    rm -rf "${DEPLOY_DIR:?}"/*
    mkdir -p "$DEPLOY_DIR"
    tar -xzf "$latest_backup" -C "$DEPLOY_DIR" 2>/dev/null || error_exit "解压备份失败"
    
    # 修复路径（如果备份包含完整路径）
    if [[ -d "${DEPLOY_DIR}/opt/calc" ]]; then
        mv "${DEPLOY_DIR}/opt/calc"/* "$DEPLOY_DIR/" 2>/dev/null || true
        rm -rf "${DEPLOY_DIR}/opt" 2>/dev/null || true
    fi
    
    log INFO "回滚完成"
    
    # 回滚后健康检查
    if health_check; then
        log INFO "回滚后健康检查通过"
    else
        log ERROR "回滚后健康检查未通过，请手动检查"
        return 1
    fi
}

# ==============================================================================
# 6. 运行测试
# ==============================================================================
run_tests() {
    log INFO "运行完整测试套件..."
    
    local target_file="${DEPLOY_DIR}/calc.py"
    
    if [[ ! -f "$target_file" ]]; then
        error_exit "主程序文件不存在，无法运行测试"
    fi
    
    local tests_passed=0
    local tests_failed=0
    
    # 定义测试用例
    declare -a test_cases=(
        "1 + 2:3:基本加法"
        "(1 + 2) * 3:9:混合运算"
        "3.14159 * 2:6.28318:浮点数运算"
        "(100 + 200) / 3 - 50:50:复杂表达式"
        "(((1 + 2) * 3) - 4) / 5:1:嵌套括号"
        "999999999 * 999999999:999999998000000001:大数精度"
        "-5 + 3:-2:负数运算"
        "sqrt(16):4:平方根函数"
        "sin(0):0:正弦函数"
        "cos(0):1:余弦函数"
        "2 ^ 10:1024:幂运算"
        "255 to hex:0xFF:十六进制转换"
        "255 to bin:0b11111111:二进制转换"
        "0xFF to dec:255:十六进制转十进制"
        "abs(-5):5:绝对值函数"
    )
    
    for test_case in "${test_cases[@]}"; do
        IFS=':' read -r expression expected description <<< "$test_case"
        
        local result
        if result=$($PYTHON_CMD "$target_file" "$expression" 2>&1); then
            if [[ "$result" == "$expected" ]]; then
                log INFO "✓ PASS: $description ($expression = $expected)"
                ((tests_passed++))
            else
                log ERROR "✗ FAIL: $description (期望: $expected, 实际: $result)"
                ((tests_failed++))
            fi
        else
            log ERROR "✗ FAIL: $description (执行错误: $result)"
            ((tests_failed++))
        fi
    done
    
    log INFO "测试完成: 通过 $tests_passed, 失败 $tests_failed"
    
    if [[ "$tests_failed" -eq 0 ]]; then
        log INFO "所有测试通过"
        return 0
    else
        log ERROR "部分测试失败"
        return 1
    fi
}

# ==============================================================================
# 主函数
# ==============================================================================
main() {
    local action=""
    local run_test=false
    local force=false
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--version)
                show_version
                exit 0
                ;;
            -d|--deploy)
                action="deploy"
                ;;
            -r|--rollback)
                action="rollback"
                ;;
            -c|--check)
                action="check"
                ;;
            -b|--backup)
                action="backup"
                ;;
            -t|--test)
                run_test=true
                ;;
            -f|--force)
                force=true
                ;;
            *)
                error_exit "未知选项: $1，使用 -h 查看帮助"
                ;;
        esac
        shift
    done
    
    # 如果没有指定动作，显示帮助
    if [[ -z "$action" ]]; then
        show_help
        exit 0
    fi
    
    # 创建日志目录
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    
    log INFO "=========================================="
    log INFO "命令行计算器部署脚本启动"
    log INFO "动作: $action"
    log INFO "日志文件: $LOG_FILE"
    log INFO "=========================================="
    
    # 执行指定动作
    case "$action" in
        deploy)
            # 环境检查
            check_environment
            
            # 确认部署
            if [[ "$force" != "true" ]]; then
                echo ""
                echo "部署配置:"
                echo "  部署目录: $DEPLOY_DIR"
                echo "  备份目录: $BACKUP_DIR"
                echo "  配置文件: $CONFIG_DIR"
                echo "  源代码: $SOURCE_CODE"
                echo ""
                read -p "确认执行部署? (y/N): " confirm
                if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
                    log INFO "部署已取消"
                    exit 0
                fi
            fi
            
            # 创建备份
            create_backup
            
            # 执行部署
            deploy_code
            
            # 健康检查
            if health_check; then
                log INFO "部署成功完成"
            else
                log ERROR "部署后健康检查失败，考虑执行回滚"
                exit 1
            fi
            
            # 运行测试（如果指定）
            if [[ "$run_test" == "true" ]]; then
                run_tests || exit 1
            fi
            
            log INFO "部署完成！可以使用 'calc' 命令运行计算器"
            ;;
            
        rollback)
            FORCE="$force" rollback
            ;;
            
        check)
            check_environment
            health_check
            ;;
            
        backup)
            check_environment
            create_backup
            list_backups
            ;;
            
        *)
            error_exit "未知动作: $action"
            ;;
    esac
    
    log INFO "脚本执行完成"
    exit 0
}

# 执行主函数
main "$@"
```
