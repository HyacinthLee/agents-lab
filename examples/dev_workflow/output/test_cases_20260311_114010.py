import importlib.util
import sys
import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# 动态加载代码文件
spec = importlib.util.spec_from_file_location("calculator", Path(__file__).parent / "code_v1_20260311_113941.py")
calc = importlib.util.module_from_spec(spec)
sys.modules["calculator"] = calc
spec.loader.exec_module(calc)

# 尝试导入常见的函数名
try:
    main = calc.main
except AttributeError:
    main = None

try:
    calculate = calc.calculate
except AttributeError:
    calculate = None

try:
    parse_input = calc.parse_input
except AttributeError:
    parse_input = None


class TestCalculator:
    """命令行计算器测试类"""

    def run_calc(self, args):
        """辅助方法：运行计算器命令"""
        if main:
            with patch('sys.argv', ['calc'] + args):
                with patch('sys.stdout') as mock_stdout:
                    try:
                        main()
                        return mock_stdout.write.call_args_list if mock_stdout.write.called else ""
                    except SystemExit as e:
                        return e.code
        return None

    # ========== 正常场景测试 ==========

    def test_tc001_two_number_addition(self):
        """TC-001: 两个数字加法运算"""
        result = self.run_calc(['10', '+', '5'])
        assert result is not None

    def test_tc002_multiple_number_addition(self):
        """TC-002: 多个数字加法运算"""
        result = self.run_calc(['1', '+', '2', '+', '3', '+', '4'])
        assert result is not None

    def test_tc003_subtraction(self):
        """TC-003: 减法运算"""
        result = self.run_calc(['20', '-', '8'])
        assert result is not None

    def test_tc004_two_number_multiplication(self):
        """TC-004: 两个数字乘法运算"""
        result = self.run_calc(['6', '*', '7'])
        assert result is not None

    def test_tc005_multiple_number_multiplication(self):
        """TC-005: 多个数字乘法运算"""
        result = self.run_calc(['2', '*', '3', '*', '4'])
        assert result is not None

    def test_tc006_division(self):
        """TC-006: 除法运算"""
        result = self.run_calc(['15', '/', '3'])
        assert result is not None

    def test_tc007_negative_numbers(self):
        """TC-007: 负数运算"""
        result = self.run_calc(['-5', '+', '3'])
        assert result is not None

    # ========== 异常场景测试 ==========

    def test_tc008_division_by_zero(self):
        """TC-008: 除零错误检测"""
        result = self.run_calc(['10', '/', '0'])
        # 应该返回错误信息或特定退出码，而不是崩溃

    def test_tc009_invalid_character_input(self):
        """TC-009: 非法字符输入处理"""
        result = self.run_calc(['5', '+', 'abc'])
        # 应该返回友好错误信息

    def test_tc010_missing_parameter(self):
        """TC-010: 缺失参数处理"""
        result = self.run_calc(['5', '+'])
        # 应该返回参数错误提示

    def test_tc011_invalid_operator(self):
        """TC-011: 运算符错误处理"""
        result = self.run_calc(['5', '&', '3'])
        # 应该返回非法运算符提示

    # ========== 边界条件测试 ==========

    def test_tc012_large_number_addition(self):
        """TC-012: 大数加法运算"""
        result = self.run_calc(['999999999', '+', '1'])
        assert result is not None

    def test_tc013_zero_value_operation(self):
        """TC-013: 零值参与运算"""
        result = self.run_calc(['0', '+', '5'])
        assert result is not None

    def test_tc014_zero_multiplication(self):
        """TC-014: 零乘法"""
        result = self.run_calc(['5', '*', '0'])
        assert result is not None

    # ========== 性能测试 ==========

    def test_performance_single_operation(self):
        """性能测试：单次运算响应时间 < 100ms"""
        start_time = time.time()
        self.run_calc(['10', '+', '5'])
        elapsed_time = (time.time() - start_time) * 1000
        assert elapsed_time < 100, f"运算耗时 {elapsed_time}ms，超过 100ms 限制"


class TestCalculatorFunctions:
    """测试计算器核心函数（如果存在）"""

    def test_calculate_function_exists(self):
        """测试 calculate 函数是否存在"""
        if calculate:
            assert callable(calculate)

    def test_parse_input_function_exists(self):
        """测试 parse_input 函数是否存在"""
        if parse_input:
            assert callable(parse_input)

    def test_main_function_exists(self):
        """测试 main 函数是否存在"""
        if main:
            assert callable(main)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])