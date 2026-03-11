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


def cli_parse_args(args: list[str]) -> Result:
    if len(args) != 3:
        return Error(
            ErrorCode.INVALID_ARGUMENT_COUNT,
            f"需要3个参数（操作数1 运算符 操作数2），但提供了 {len(args)} 个参数"
        )
    
    num1_str, op, num2_str = args
    
    num1 = parser_to_number(num1_str)
    if isinstance(num1, Error):
        return num1
    
    num2 = parser_to_number(num2_str)
    if isinstance(num2, Error):
        return num2
    
    return (num1, op, num2)


def main():
    try:
        args = sys.argv[1:]
        
        parsed = cli_parse_args(args)
        if isinstance(parsed, Error):
            print(error_handler_format_error(parsed))
            sys.exit(1)
        
        a, op, b = parsed
        
        result = calculator_calculate(a, op, b)
        if isinstance(result, Error):
            print(error_handler_format_error(result))
            sys.exit(1)
        
        if result == int(result):
            print(int(result))
        else:
            print(result)
        
    except Exception as e:
        print(f"系统错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()