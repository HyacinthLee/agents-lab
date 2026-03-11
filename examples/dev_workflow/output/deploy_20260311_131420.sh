#!/bin/bash
# 计算器应用部署脚本

set -e

APP_NAME="calculator"
DEPLOY_DIR="/opt/calculator"
BACKUP_DIR="/opt/calculator-backup"
LOG_FILE="/var/log/calculator-deploy.log"
PYTHON_BIN="/usr/bin/python3"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# ==================== 部署步骤 ====================

deploy() {
    log "开始部署 $APP_NAME..."
    
    # 创建目录
    mkdir -p "$DEPLOY_DIR"
    mkdir -p "$BACKUP_DIR"
    
    # 备份现有版本
    if [ -f "$DEPLOY_DIR/calculator.py" ]; then
        log "备份现有版本..."
        cp "$DEPLOY_DIR/calculator.py" "$BACKUP_DIR/calculator-$(date +%Y%m%d%H%M%S).py.bak"
    fi
    
    # 部署新代码
    log "部署新代码..."
    cat > "$DEPLOY_DIR/calculator.py" << 'EOF'
#!/usr/bin/env python3
"""
命令行计算器 - 严格按照规格说明书实现
"""

import sys
from typing import List, Tuple, Union
from enum import Enum


# ==================== 4.1 核心类型定义 ====================

class Operator(Enum):
    """支持的运算符枚举"""
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"


# 操作数类型 (支持整数和浮点数)
Operand = Union[int, float]

# 解析结果类型
ParseResult = Tuple[List[Operand], Operator]


# ==================== 4.2 错误码定义 ====================

class ErrorCode:
    """错误码定义"""
    E_INVALID_OP = "非法运算符"
    E_DIV_ZERO = "除数不能为零"
    E_ARG_COUNT = "参数数量错误"
    E_TYPE_ERROR = "操作数类型非法"


# ==================== 3.1 CLI解析器 ====================

def parse_args(args: List[str]) -> Tuple[List[float], str]:
    """
    输入: 命令行参数列表 (如 ["10", "+", "5"])
    输出: (操作数列表, 运算符) 或抛出 ValueError
    """
    if len(args) != 3:
        raise ValueError(ErrorCode.E_ARG_COUNT)
    
    # 解析运算符
    operator = args[1]
    valid_operators = [op.value for op in Operator]
    if operator not in valid_operators:
        raise ValueError(ErrorCode.E_INVALID_OP)
    
    # 解析操作数
    operands = []
    for i in [0, 2]:
        try:
            num = float(args[i])
            operands.append(num)
        except ValueError:
            raise ValueError(ErrorCode.E_TYPE_ERROR)
    
    return operands, operator


# ==================== 3.2 运算引擎 ====================

def calculate(operands: List[float], operator: str) -> float:
    """
    输入: 操作数列表, 运算符
    输出: 计算结果 (float)
    异常: ZeroDivisionError, ValueError
    """
    a, b = operands[0], operands[1]
    
    if operator == "+":
        return a + b
    elif operator == "-":
        return a - b
    elif operator == "*":
        return a * b
    elif operator == "/":
        if b == 0:
            raise ZeroDivisionError(ErrorCode.E_DIV_ZERO)
        return a / b
    
    raise ValueError(ErrorCode.E_INVALID_OP)


# ==================== 3.3 主入口 ====================

def main():
    """主函数"""
    try:
        args = sys.argv[1:]
        operands, operator = parse_args(args)
        result = calculate(operands, operator)
        print(result)
        return 0
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    except ZeroDivisionError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
EOF
    
    chmod +x "$DEPLOY_DIR/calculator.py"
    
    # 创建软链接到系统路径
    ln -sf "$DEPLOY_DIR/calculator.py" /usr/local/bin/calculator
    
    log "部署完成"
}

# ==================== 健康检查 ====================

health_check() {
    log "执行健康检查..."
    
    local failed=0
    
    # 检查文件存在
    if [ ! -f "$DEPLOY_DIR/calculator.py" ]; then
        log "❌ 文件不存在"
        return 1
    fi
    
    # 检查语法
    if ! $PYTHON_BIN -m py_compile "$DEPLOY_DIR/calculator.py"; then
        log "❌ Python语法错误"
        return 1
    fi
    
    # 功能测试
    test_cases=(
        "10 + 5:15.0"
        "10 - 5:5.0"
        "10 \* 5:50.0"
        "10 / 5:2.0"
        "3.5 + 2.5:6.0"
    )
    
    for tc in "${test_cases[@]}"; do
        IFS=':' read -r input expected <<< "$tc"
        result=$($PYTHON_BIN "$DEPLOY_DIR/calculator.py" $input 2>/dev/null || echo "ERROR")
        if [ "$result" != "$expected" ]; then
            log "❌ 测试失败: $input = $result (期望: $expected)"
            failed=1
        else
            log "✓ 测试通过: $input = $result"
        fi
    done
    
    # 错误处理测试
    error_result=$($PYTHON_BIN "$DEPLOY_DIR/calculator.py" 10 / 0 2>&1 || true)
    if [[ "$error_result" == *"除数不能为零"* ]]; then
        log "✓ 除零错误处理正常"
    else
        log "❌ 除零错误处理异常"
        failed=1
    fi
    
    invalid_op=$($PYTHON_BIN "$DEPLOY_DIR/calculator.py" 10 ^ 5 2>&1 || true)
    if [[ "$invalid_op" == *"非法运算符"* ]]; then
        log "✓ 非法运算符处理正常"
    else
        log "❌ 非法运算符处理异常"
        failed=1
    fi
    
    if [ $failed -eq 0 ]; then
        log "✓ 所有健康检查通过"
        return 0
    else
        log "❌ 健康检查失败"
        return 1
    fi
}

# ==================== 回滚 ====================

rollback() {
    log "开始回滚..."
    
    latest_backup=$(ls -t "$BACKUP_DIR"/*.py.bak 2>/dev/null | head -1)
    
    if [ -z "$latest_backup" ]; then
        log "❌ 没有可用的备份"
        return 1
    fi
    
    cp "$latest_backup" "$DEPLOY_DIR/calculator.py"
    chmod +x "$DEPLOY_DIR/calculator.py"
    
    log "✓ 回滚完成: $(basename "$latest_backup")"
}

# ==================== 主逻辑 ====================

case "${1:-deploy}" in
    deploy)
        deploy && health_check
        ;;
    health)
        health_check
        ;;
    rollback)
        rollback && health_check
        ;;
    *)
        echo "用法: $0 {deploy|health|rollback}"
        exit 1
        ;;
esac