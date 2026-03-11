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
    if len(operands) != 2:
        raise ValueError(ErrorCode.E_ARG_COUNT)
    
    a, b = operands
    
    if operator == Operator.ADD.value:
        return a + b
    elif operator == Operator.SUB.value:
        return a - b
    elif operator == Operator.MUL.value:
        return a * b
    elif operator == Operator.DIV.value:
        if b == 0:
            raise ZeroDivisionError(ErrorCode.E_DIV_ZERO)
        return a / b
    else:
        raise ValueError(ErrorCode.E_INVALID_OP)


# ==================== 3.3 错误处理器 ====================

def handle_error(error: Exception) -> str:
    """
    输入: 异常对象
    输出: 用户友好的错误提示字符串
    """
    if isinstance(error, ZeroDivisionError):
        return f"Error: {ErrorCode.E_DIV_ZERO}"
    elif isinstance(error, ValueError):
        return f"Error: {str(error)}"
    else:
        return f"Error: 未知错误 - {str(error)}"


# ==================== 3.4 主入口 ====================

def main(argv: List[str]) -> int:
    """
    输入: 命令行参数
    输出: 退出码 (0=成功, 1=错误)
    """
    try:
        # 解析参数
        operands, operator = parse_args(argv)
        
        # 执行计算
        result = calculate(operands, operator)
        
        # 格式化输出 (6位小数精度)
        print(f"{result:.6f}")
        
        return 0
        
    except Exception as e:
        error_msg = handle_error(e)
        print(error_msg, file=sys.stderr)
        return 1


# ==================== 命令行交互入口 ====================

if __name__ == "__main__":
    # 跳过脚本名，只传递参数
    exit_code = main(sys.argv[1:])
    sys.exit(exit_code)