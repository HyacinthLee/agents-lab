#!/bin/bash
# -*- coding: utf-8 -*-
# 部署脚本 - Calculator Application

set -euo pipefail

# 配置变量
APP_NAME="calculator"
DEPLOY_DIR="/opt/${APP_NAME}"
BACKUP_DIR="/opt/backups/${APP_NAME}"
LOG_DIR="/var/log/${APP_NAME}"
SERVICE_NAME="${APP_NAME}.service"
HEALTH_CHECK_URL="http://localhost:8080/health"
HEALTH_CHECK_TIMEOUT=30
MAX_RETRIES=5

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 部署步骤
deploy() {
    log_info "开始部署 ${APP_NAME}..."

    # 创建目录
    mkdir -p "${DEPLOY_DIR}" "${BACKUP_DIR}" "${LOG_DIR}"

    # 备份当前版本
    if [ -f "${DEPLOY_DIR}/calculator.py" ]; then
        BACKUP_FILE="${BACKUP_DIR}/calculator_$(date +%Y%m%d_%H%M%S).py"
        cp "${DEPLOY_DIR}/calculator.py" "${BACKUP_FILE}"
        log_info "已备份当前版本到 ${BACKUP_FILE}"
    fi

    # 部署新代码
    cat > "${DEPLOY_DIR}/calculator.py" << 'EOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass
from typing import Union, Tuple
import sys

type Operator = str
type Result = Union[float, 'Error']


@dataclass
class Error:
    code: int
    message: str


class ErrorCode:
    INVALID_ARGUMENT_COUNT = 1001
    INVALID_NUMBER_FORMAT = 1002
    UNSUPPORTED_OPERATOR = 1003
    DIVISION_BY_ZERO = 1004


def error_handler_format_error(e: Error) -> str:
    error_messages = {
        ErrorCode.INVALID_ARGUMENT_COUNT: f"错误[{e.code}]: 参数数量错误 - {e.message}",
        ErrorCode.INVALID_NUMBER_FORMAT: f"错误[{e.code}]: 非法数字格式 - {e.message}",
        ErrorCode.UNSUPPORTED_OPERATOR: f"错误[{e.code}]: 不支持的操作符 - {e.message}",
        ErrorCode.DIVISION_BY_ZERO: f"错误[{e.code}]: 除零错误 - {e.message}",
    }
    return error_messages.get(e.code, f"错误[{e.code}]: {e.message}")


def parser_to_number(s: str) -> Result:
    try:
        return float(s)
    except ValueError:
        return Error(ErrorCode.INVALID_NUMBER_FORMAT, f"无法将 '{s}' 转换为数字")


def calculator_calculate(a: float, op: Operator, b: float) -> Result:
    if op not in ('+', '-', '*', '/'):
        return Error(ErrorCode.UNSUPPORTED_OPERATOR, f"不支持的操作符 '{op}'，仅支持 + - * /")
    
    if op == '+':
        return a + b
    elif op == '-':
        return a - b
    elif op == '*':
        return a * b
    elif op == '/':
        if b == 0:
            return Error(ErrorCode.DIVISION_BY_ZERO, "除数不能为零")
        return a / b
    
    return Error(ErrorCode.UNSUPPORTED_OPERATOR, f"不支持的操作符 '{op}'")


def main():
    if len(sys.argv) != 4:
        error = Error(ErrorCode.INVALID_ARGUMENT_COUNT, "用法: calculator <数字> <操作符> <数字>")
        print(error_handler_format_error(error))
        sys.exit(1)
    
    a_str, op, b_str = sys.argv[1], sys.argv[2], sys.argv[3]
    
    a = parser_to_number(a_str)
    if isinstance(a, Error):
        print(error_handler_format_error(a))
        sys.exit(1)
    
    b = parser_to_number(b_str)
    if isinstance(b, Error):
        print(error_handler_format_error(b))
        sys.exit(1)
    
    result = calculator_calculate(a, op, b)
    if isinstance(result, Error):
        print(error_handler_format_error(result))
        sys.exit(1)
    
    print(result)


if __name__ == "__main__":
    main()
EOF

    chmod +x "${DEPLOY_DIR}/calculator.py"

    # 创建 systemd 服务
    cat > "/etc/systemd/system/${SERVICE_NAME}" << EOF
[Unit]
Description=Calculator Application
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${DEPLOY_DIR}
ExecStart=/usr/bin/python3 ${DEPLOY_DIR}/calculator.py
Restart=always
RestartSec=5
StandardOutput=append:${LOG_DIR}/app.log
StandardError=append:${LOG_DIR}/error.log

[Install]
WantedBy=multi-user.target
EOF

    # 重载 systemd
    systemctl daemon-reload

    # 启动服务
    systemctl enable "${SERVICE_NAME}"
    systemctl restart "${SERVICE_NAME}"

    log_info "部署完成"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."

    # 检查服务状态
    if ! systemctl is-active --quiet "${SERVICE_NAME}"; then
        log_error "服务未运行"
        return 1
    fi

    # 检查进程
    if ! pgrep -f "calculator.py" > /dev/null; then
        log_error "进程不存在"
        return 1
    fi

    # 测试基本功能
    TEST_RESULT=$("${DEPLOY_DIR}/calculator.py" 2 + 3 2>&1)
    if [ "$TEST_RESULT" != "5.0" ]; then
        log_error "功能测试失败: 期望 5.0, 实际 ${TEST_RESULT}"
        return 1
    fi

    # 测试错误处理
    ERROR_RESULT=$("${DEPLOY_DIR}/calculator.py" 2 / 0 2>&1)
    if [[ ! "$ERROR_RESULT" =~ "除零错误" ]]; then
        log_error "错误处理测试失败"
        return 1
    fi

    log_info "健康检查通过"
    return 0
}

# 回滚
rollback() {
    log_warn "开始回滚..."

    # 停止服务
    systemctl stop "${SERVICE_NAME}" || true

    # 查找最新备份
    LATEST_BACKUP=$(ls -t "${BACKUP_DIR}"/calculator_*.py 2>/dev/null | head -1)

    if [ -z "${LATEST_BACKUP}" ]; then
        log_error "未找到备份文件"
        return 1
    fi

    # 恢复备份
    cp "${LATEST_BACKUP}" "${DEPLOY_DIR}/calculator.py"
    chmod +x "${DEPLOY_DIR}/calculator.py"

    # 重启服务
    systemctl start "${SERVICE_NAME}"

    # 验证回滚
    if health_check; then
        log_info "回滚成功"
    else
        log_error "回滚后健康检查失败"
        return 1
    fi
}

# 主逻辑
case "${1:-deploy}" in
    deploy)
        deploy
        health_check || { log_error "健康检查失败，执行回滚"; rollback; exit 1; }
        ;;
    health|check)
        health_check
        ;;
    rollback)
        rollback
        ;;
    *)
        echo "用法: $0 {deploy|health|rollback}"
        exit 1
        ;;
esac