"""测试用例 - 自动修复导入"""
import importlib.util
import sys
from pathlib import Path

# 动态加载被测代码
spec = importlib.util.spec_from_file_location("calculator", Path(__file__).parent / "code_v1_20260311_132116.py")
calc = importlib.util.module_from_spec(spec)
sys.modules["calculator"] = calc
spec.loader.exec_module(calc)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib.util
import sys
import pytest

# 动态加载代码文件
spec = importlib.util.spec_from_file_location("calculator", Path(__file__).parent / "code_v1_20260311_132116.py")
calc = importlib.util.module_from_spec(spec)
sys.modules["calculator"] = calc
spec.loader.exec_module(calc)

# 从模块导入需要的函数
Error = calc.Error
ErrorCode = calc.ErrorCode
parser_to_number = calc.parser_to_number
calculator_calculate = calc.calculator_calculate
cli_parse_args = calc.cli_parse_args
error_handler_format_error = calc.error_handler_format_error


class TestParserToNumber:
    """测试 parser_to_number 函数"""

    def test_valid_integer(self):
        result = parser_to_number("10")
        assert result == 10.0

    def test_valid_float(self):
        result = parser_to_number("10.5")
        assert result == 10.5

    def test_negative_number(self):
        result = parser_to_number("-5")
        assert result == -5.0

    def test_invalid_string(self):
        result = parser_to_number("abc")
        assert isinstance(result, Error)
        assert result.code == ErrorCode.INVALID_NUMBER_FORMAT

    def test_empty_string(self):
        result = parser_to_number("")
        assert isinstance(result, Error)
        assert result.code == ErrorCode.INVALID_NUMBER_FORMAT


class TestCalculatorCalculate:
    """测试 calculator_calculate 函数"""

    def test_addition(self):
        result = calculator_calculate(10, "+", 5)
        assert result == 15.0

    def test_subtraction_positive_result(self):
        result = calculator_calculate(20, "-", 8)
        assert result == 12.0

    def test_subtraction_negative_result(self):
        result = calculator_calculate(5, "-", 10)
        assert result == -5.0

    def test_multiplication(self):
        result = calculator_calculate(6, "*", 7)
        assert result == 42.0

    def test_division_normal(self):
        result = calculator_calculate(100, "/", 4)
        assert result == 25.0

    def test_division_by_zero(self):
        result = calculator_calculate(10, "/", 0)
        assert isinstance(result, Error)
        assert result.code == ErrorCode.DIVISION_BY_ZERO

    def test_unsupported_operator(self):
        result = calculator_calculate(5, "@", 3)
        assert isinstance(result, Error)
        assert result.code == ErrorCode.UNSUPPORTED_OPERATOR

    def test_float_addition(self):
        result = calculator_calculate(10.5, "+", 2.5)
        assert result == 13.0

    def test_large_numbers(self):
        result = calculator_calculate(999999999, "+", 1)
        assert result == 1000000000.0


class TestCliParseArgs:
    """测试 cli_parse_args 函数"""

    def test_valid_args(self):
        result = cli_parse_args(["10", "+", "5"])
        assert result == (10.0, "+", 5.0)

    def test_negative_number_args(self):
        result = cli_parse_args(["-5", "+", "3"])
        assert result == (-5.0, "+", 3.0)

    def test_float_args(self):
        result = cli_parse_args(["10.5", "+", "2.5"])
        assert result == (10.5, "+", 2.5)

    def test_missing_args(self):
        result = cli_parse_args(["5", "+"])
        assert isinstance(result, Error)
        assert result.code == ErrorCode.INVALID_ARGUMENT_COUNT

    def test_too_many_args(self):
        result = cli_parse_args(["1", "+", "2", "+", "3"])
        assert isinstance(result, Error)
        assert result.code == ErrorCode.INVALID_ARGUMENT_COUNT

    def test_invalid_first_number(self):
        result = cli_parse_args(["a", "+", "5"])
        assert isinstance(result, Error)
        assert result.code == ErrorCode.INVALID_NUMBER_FORMAT

    def test_invalid_second_number(self):
        result = cli_parse_args(["5", "+", "b"])
        assert isinstance(result, Error)
        assert result.code == ErrorCode.INVALID_NUMBER_FORMAT

    def test_missing_operator(self):
        result = cli_parse_args(["5", "3"])
        assert isinstance(result, Error)
        assert result.code == ErrorCode.INVALID_ARGUMENT_COUNT


class TestErrorHandlerFormatError:
    """测试 error_handler_format_error 函数"""

    def test_invalid_argument_count_error(self):
        error = Error(ErrorCode.INVALID_ARGUMENT_COUNT, "测试消息")
        result = error_handler_format_error(error)
        assert "错误[1001]" in result
        assert "参数数量错误" in result
        assert "测试消息" in result

    def test_invalid_number_format_error(self):
        error = Error(ErrorCode.INVALID_NUMBER_FORMAT, "测试消息")
        result = error_handler_format_error(error)
        assert "错误[1002]" in result
        assert "非法数字格式" in result
        assert "测试消息" in result

    def test_unsupported_operator_error(self):
        error = Error(ErrorCode.UNSUPPORTED_OPERATOR, "测试消息")
        result = error_handler_format_error(error)
        assert "错误[1003]" in result
        assert "不支持的操作符" in result
        assert "测试消息" in result

    def test_division_by_zero_error(self):
        error = Error(ErrorCode.DIVISION_BY_ZERO, "测试消息")
        result = error_handler_format_error(error)
        assert "错误[1004]" in result
        assert "除零错误" in result
        assert "测试消息" in result

    def test_unknown_error_code(self):
        error = Error(9999, "未知错误")
        result = error_handler_format_error(error)
        assert "错误[9999]" in result
        assert "未知错误" in result


class TestIntegration:
    """集成测试"""

    def test_full_flow_addition(self):
        parsed = cli_parse_args(["10", "+", "5"])
        assert not isinstance(parsed, Error)
        a, op, b = parsed
        result = calculator_calculate(a, op, b)
        assert result == 15.0

    def test_full_flow_division_by_zero(self):
        parsed = cli_parse_args(["10", "/", "0"])
        assert not isinstance(parsed, Error)
        a, op, b = parsed
        result = calculator_calculate(a, op, b)
        assert isinstance(result, Error)
        assert result.code == ErrorCode.DIVISION_BY_ZERO
        formatted = error_handler_format_error(result)
        assert "除零错误" in formatted

    def test_full_flow_invalid_input(self):
        parsed = cli_parse_args(["a", "+", "5"])
        assert isinstance(parsed, Error)
        formatted = error_handler_format_error(parsed)
        assert "非法数字格式" in formatted

    def test_full_flow_unsupported_operator(self):
        parsed = cli_parse_args(["5", "@", "3"])
        assert not isinstance(parsed, Error)
        a, op, b = parsed
        result = calculator_calculate(a, op, b)
        assert isinstance(result, Error)
        assert result.code == ErrorCode.UNSUPPORTED_OPERATOR


if __name__ == "__main__":
    pytest.main([__file__, "-v"])