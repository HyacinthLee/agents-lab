import unittest
from code_v1_20260310_004608 import (
    ExpressionCalculator, Lexer, Parser, Evaluator, EvalContext,
    FunctionRegistry, Number, TokenType, DivisionByZeroError,
    SyntaxError, InvalidTokenError, UndefinedVariableError,
    UndefinedFunctionError, DomainError
)


class TestExpressionCalculator(unittest.TestCase):
    """测试表达式计算器核心功能"""

    def setUp(self):
        """每个测试用例前初始化计算器"""
        self.calc = ExpressionCalculator()

    # ==================== 正常场景测试 ====================

    def test_basic_addition(self):
        """测试基本加法运算"""
        success, result = self.calc.calculate("1 + 2")
        self.assertTrue(success)
        self.assertEqual(result, "3")

    def test_mixed_operator_precedence(self):
        """测试混合运算优先级（括号优先）"""
        success, result = self.calc.calculate("(1 + 2) * 3")
        self.assertTrue(success)
        self.assertEqual(result, "9")

    def test_complex_expression(self):
        """测试复杂表达式求值"""
        success, result = self.calc.calculate("(100 + 200) / 3 - 50")
        self.assertTrue(success)
        self.assertEqual(result, "50")

    def test_floating_point_calculation(self):
        """测试浮点数运算精度"""
        success, result = self.calc.calculate("3.14159 * 2")
        self.assertTrue(success)
        self.assertAlmostEqual(float(result), 6.28318, places=5)

    # ==================== 异常场景测试 ====================

    def test_division_by_zero(self):
        """测试除零错误处理"""
        success, result = self.calc.calculate("1 / 0")
        self.assertFalse(success)
        self.assertIn("Division by zero", result)

    def test_invalid_input(self):
        """测试无效输入处理"""
        success, result = self.calc.calculate("abc")
        self.assertFalse(success)
        self.assertIn("Error", result)

    def test_syntax_error(self):
        """测试语法错误提示（运算符连续使用）"""
        success, result = self.calc.calculate("1 + * 2")
        self.assertFalse(success)
        self.assertIn("Error", result)

    def test_undefined_function(self):
        """测试未定义函数错误"""
        success, result = self.calc.calculate("unknown_func(1)")
        self.assertFalse(success)
        self.assertIn("Undefined function", result)

    # ==================== 边界条件测试 ====================

    def test_empty_input(self):
        """测试空输入处理"""
        success, result = self.calc.calculate("")
        self.assertFalse(success)

    def test_nested_parentheses(self):
        """测试多层嵌套括号解析"""
        success, result = self.calc.calculate("(((1 + 2) * 3) - 4) / 5")
        self.assertTrue(success)
        self.assertEqual(result, "1")

    def test_large_number_precision(self):
        """测试大数运算精度保持"""
        success, result = self.calc.calculate("999999999 * 999999999")
        self.assertTrue(success)
        self.assertEqual(result, "999999998000000001")

    def test_negative_number(self):
        """测试负数运算"""
        success, result = self.calc.calculate("-5 + 3")
        self.assertTrue(success)
        self.assertEqual(result, "-2")

    def test_scientific_function(self):
        """测试科学计算函数（平方根）"""
        success, result = self.calc.calculate("sqrt(16)")
        self.assertTrue(success)
        self.assertEqual(result, "4")


if __name__ == '__main__':
    unittest.main()
