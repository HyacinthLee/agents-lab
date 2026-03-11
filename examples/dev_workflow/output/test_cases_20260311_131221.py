#!/usr/bin/env python3
"""
命令行计算器测试用例
"""

import importlib.util
import sys
from pathlib import Path
import pytest
from io import StringIO

# 动态加载代码文件
spec = importlib.util.spec_from_file_location("calculator", Path(__file__).parent / "code_v1_20260311_131143.py")
calc = importlib.util.module_from_spec(spec)
sys.modules["calculator"] = calc
spec.loader.exec_module(calc)

# 从模块导入需要的函数
parse_args = calc.parse_args
calculate = calc.calculate
handle_error = calc.handle_error
main = calc.main
ErrorCode = calc.ErrorCode


# ==================== parse_args 函数测试 ====================

class TestParseArgs:
    """测试参数解析函数"""

    def test_parse_args_valid_addition(self):
        """TC01: 整数加法参数解析"""
        operands, operator = parse_args(["10", "+", "5"])
        assert operands == [10.0, 5.0]
        assert operator == "+"

    def test_parse_args_valid_float(self):
        """TC02: 浮点数参数解析"""
        operands, operator = parse_args(["3.5", "+", "2.7"])
        assert operands == [3.5, 2.7]
        assert operator == "+"

    def test_parse_args_subtraction(self):
        """TC04: 减法参数解析"""
        operands, operator = parse_args(["20", "-", "8"])
        assert operands == [20.0, 8.0]
        assert operator == "-"

    def test_parse_args_negative_result(self):
        """TC05: 负数结果减法参数解析"""
        operands, operator = parse_args(["5", "-", "10"])
        assert operands == [5.0, 10.0]
        assert operator == "-"

    def test_parse_args_multiplication(self):
        """TC06: 乘法参数解析"""
        operands, operator = parse_args(["6", "*", "7"])
        assert operands == [6.0, 7.0]
        assert operator == "*"

    def test_parse_args_division(self):
        """TC08: 除法参数解析"""
        operands, operator = parse_args(["15", "/", "4"])
        assert operands == [15.0, 4.0]
        assert operator == "/"

    def test_parse_args_division_by_zero(self):
        """TC09: 除零参数解析（解析阶段不报错）"""
        operands, operator = parse_args(["10", "/", "0"])
        assert operands == [10.0, 0.0]
        assert operator == "/"

    def test_parse_args_invalid_operator(self):
        """TC10: 非法运算符处理"""
        with pytest.raises(ValueError) as exc_info:
            parse_args(["10", "&", "5"])
        assert str(exc_info.value) == ErrorCode.E_INVALID_OP

    def test_parse_args_missing_args(self):
        """TC11: 参数缺失处理"""
        with pytest.raises(ValueError) as exc_info:
            parse_args(["10", "+"])
        assert str(exc_info.value) == ErrorCode.E_ARG_COUNT

    def test_parse_args_too_many_args(self):
        """参数过多处理"""
        with pytest.raises(ValueError) as exc_info:
            parse_args(["10", "+", "5", "extra"])
        assert str(exc_info.value) == ErrorCode.E_ARG_COUNT

    def test_parse_args_non_numeric_first(self):
        """TC12: 第一个操作数非数字"""
        with pytest.raises(ValueError) as exc_info:
            parse_args(["abc", "+", "5"])
        assert str(exc_info.value) == ErrorCode.E_TYPE_ERROR

    def test_parse_args_non_numeric_second(self):
        """TC12: 第二个操作数非数字"""
        with pytest.raises(ValueError) as exc_info:
            parse_args(["10", "+", "xyz"])
        assert str(exc_info.value) == ErrorCode.E_TYPE_ERROR

    def test_parse_args_large_numbers(self):
        """TC13: 大数参数解析"""
        operands, operator = parse_args(["999999999", "*", "999999999"])
        assert operands == [999999999.0, 999999999.0]
        assert operator == "*"

    def test_parse_args_zero_values(self):
        """TC14: 零值参数解析"""
        operands, operator = parse_args(["0", "+", "0"])
        assert operands == [0.0, 0.0]
        assert operator == "+"


# ==================== calculate 函数测试 ====================

class TestCalculate:
    """测试计算函数"""

    def test_calculate_addition_integers(self):
        """TC01: 整数加法运算"""
        result = calculate([10.0, 5.0], "+")
        assert result == 15.0

    def test_calculate_addition_floats(self):
        """TC02: 浮点数加法运算"""
        result = calculate([3.5, 2.7], "+")
        assert abs(result - 6.2) < 1e-6

    def test_calculate_subtraction(self):
        """TC04: 整数减法运算"""
        result = calculate([20.0, 8.0], "-")
        assert result == 12.0

    def test_calculate_subtraction_negative_result(self):
        """TC05: 负数结果减法"""
        result = calculate([5.0, 10.0], "-")
        assert result == -5.0

    def test_calculate_multiplication(self):
        """TC06: 整数乘法运算"""
        result = calculate([6.0, 7.0], "*")
        assert result == 42.0

    def test_calculate_multiplication_float_precision(self):
        """TC07: 浮点数乘法精度"""
        result = calculate([0.1, 0.2], "*")
        assert abs(result - 0.02) < 1e-6

    def test_calculate_division(self):
        """TC08: 正常除法运算"""
        result = calculate([15.0, 4.0], "/")
        assert result == 3.75

    def test_calculate_division_by_zero(self):
        """TC09: 除零错误处理"""
        with pytest.raises(ZeroDivisionError) as exc_info:
            calculate([10.0, 0.0], "/")
        assert str(exc_info.value) == ErrorCode.E_DIV_ZERO

    def test_calculate_invalid_operator(self):
        """TC10: 非法运算符计算"""
        with pytest.raises(ValueError) as exc_info:
            calculate([10.0, 5.0], "&")
        assert str(exc_info.value) == ErrorCode.E_INVALID_OP

    def test_calculate_large_numbers(self):
        """TC13: 大数运算测试"""
        result = calculate([999999999.0, 999999999.0], "*")
        assert result == 999999998000000001.0

    def test_calculate_zero_addition(self):
        """TC14: 零值加法运算"""
        result = calculate([0.0, 0.0], "+")
        assert result == 0.0

    def test_calculate_zero_multiplication(self):
        """TC14: 零值乘法运算"""
        result = calculate([5.0, 0.0], "*")
        assert result == 0.0

    def test_calculate_wrong_operand_count(self):
        """错误操作数数量"""
        with pytest.raises(ValueError) as exc_info:
            calculate([10.0], "+")
        assert str(exc_info.value) == ErrorCode.E_ARG_COUNT

    def test_calculate_three_operands(self):
        """三个操作数（应该报错）"""
        with pytest.raises(ValueError) as exc_info:
            calculate([1.0, 2.0, 3.0], "+")
        assert str(exc_info.value) == ErrorCode.E_ARG_COUNT


# ==================== handle_error 函数测试 ====================

class TestHandleError:
    """测试错误处理函数"""

    def test_handle_zero_division_error(self):
        """TC09: 除零错误提示"""
        error = ZeroDivisionError(ErrorCode.E_DIV_ZERO)
        result = handle_error(error)
        assert result == f"Error: {ErrorCode.E_DIV_ZERO}"

    def test_handle_value_error_invalid_op(self):
        """TC10: 非法运算符错误提示"""
        error = ValueError(ErrorCode.E_INVALID_OP)
        result = handle_error(error)
        assert result == f"Error: {ErrorCode.E_INVALID_OP}"

    def test_handle_value_error_arg_count(self):
        """TC11: 参数数量错误提示"""
        error = ValueError(ErrorCode.E_ARG_COUNT)
        result = handle_error(error)
        assert result == f"Error: {ErrorCode.E_ARG_COUNT}"

    def test_handle_value_error_type_error(self):
        """TC12: 类型错误提示"""
        error = ValueError(ErrorCode.E_TYPE_ERROR)
        result = handle_error(error)
        assert result == f"Error: {ErrorCode.E_TYPE_ERROR}"

    def test_handle_unknown_error(self):
        """未知错误处理"""
        error = RuntimeError("some runtime error")
        result = handle_error(error)
        assert "未知错误" in result
        assert "some runtime error" in result


# ==================== main 函数测试 ====================

class TestMain:
    """测试主入口函数"""

    def test_main_addition(self, capsys):
        """TC01: 主函数整数加法"""
        exit_code = main(["10", "+", "5"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == "15.000000"

    def test_main_float_addition(self, capsys):
        """TC02: 主函数浮点数加法"""
        exit_code = main(["3.5", "+", "2.7"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == "6.200000"

    def test_main_subtraction(self, capsys):
        """TC04: 主函数减法"""
        exit_code = main(["20", "-", "8"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == "12.000000"

    def test_main_negative_result(self, capsys):
        """TC05: 主函数负数结果"""
        exit_code = main(["5", "-", "10"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == "-5.000000"

    def test_main_multiplication(self, capsys):
        """TC06: 主函数乘法"""
        exit_code = main(["6", "*", "7"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == "42.000000"

    def test_main_float_precision(self, capsys):
        """TC07: 主函数浮点精度"""
        exit_code = main(["0.1", "*", "0.2"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == "0.020000"

    def test_main_division(self, capsys):
        """TC08: 主函数除法"""
        exit_code = main(["15", "/", "4"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == "3.750000"

    def test_main_division_by_zero(self, capsys):
        """TC09: 主函数除零错误"""
        exit_code = main(["10", "/", "0"])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert ErrorCode.E_DIV_ZERO in captured.err

    def test_main_invalid_operator(self, capsys):
        """TC10: 主函数非法运算符"""
        exit_code = main(["10", "&", "5"])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert ErrorCode.E_INVALID_OP in captured.err

    def test_main_missing_args(self, capsys):
        """TC11: 主函数参数缺失"""
        exit_code = main(["10", "+"])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert ErrorCode.E_ARG_COUNT in captured.err

    def test_main_non_numeric(self, capsys):
        """TC12: 主函数非数字输入"""
        exit_code = main(["abc", "+", "5"])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert ErrorCode.E_TYPE_ERROR in captured.err

    def test_main_large_numbers(self, capsys):
        """TC13: 主函数大数运算"""
        exit_code = main(["999999999", "*", "999999999"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "999999998000000001" in captured.out

    def test_main_zero_addition(self, capsys):
        """TC14: 主函数零值加法"""
        exit_code = main(["0", "+", "0"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == "0.000000"

    def test_main_zero_multiplication(self, capsys):
        """TC14: 主函数零值乘法"""
        exit_code = main(["5", "*", "0"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.strip() == "0.000000"


# ==================== 边界条件测试 ====================

class TestEdgeCases:
    """边界条件测试"""

    def test_negative_operands(self):
        """负数操作数"""
        result = calculate([-5.0, -3.0], "+")
        assert result == -8.0

    def test_mixed_positive_negative(self):
        """正负混合"""
        result = calculate([10.0, -5.0], "+")
        assert result == 5.0

    def test_decimal_precision(self):
        """小数精度测试"""
        result = calculate([1.234567, 2.345678], "+")
        assert abs(result - 3.580245) < 1e-6

    def test_very_small_numbers(self):
        """极小数值"""
        result = calculate([0.000001, 0.000002], "+")
        assert abs(result - 0.000003) < 1e-9

    def test_subtraction_to_zero(self):
        """减法得零"""
        result = calculate([5.0, 5.0], "-")
        assert result == 0.0

    def test_division_result_one(self):
        """除法得一"""
        result = calculate([5.0, 5.0], "/")
        assert result == 1.0

    def test_division_fraction(self):
        """除法得小数"""
        result = calculate([1.0, 3.0], "/")
        assert abs(result - 0.333333) < 1e-6

    def test_multiply_by_one(self):
        """乘一不变"""
        result = calculate([42.0, 1.0], "*")
        assert result == 42.0

    def test_add_zero(self):
        """加零不变"""
        result = calculate([42.0, 0.0], "+")
        assert result == 42.0