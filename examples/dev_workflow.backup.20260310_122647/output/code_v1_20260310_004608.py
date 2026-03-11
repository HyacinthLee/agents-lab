#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 功能描述：命令行计算器 - 支持基本四则运算、科学计算、进制转换、表达式求值等功能

import sys
import os
import json
import re
import math
from datetime import datetime
from enum import Enum, auto
from typing import List, Dict, Optional, Union, Any, Tuple
from dataclasses import dataclass, field


# ============================================================================
# 错误类型定义
# ============================================================================

class ErrorType(Enum):
    """错误类型枚举"""
    DIVISION_BY_ZERO = "E001"
    SYNTAX_ERROR = "E002"
    INVALID_TOKEN = "E003"
    UNDEFINED_VARIABLE = "E004"
    UNDEFINED_FUNCTION = "E005"
    TYPE_ERROR = "E006"
    ARGUMENT_COUNT = "E007"
    DOMAIN_ERROR = "E008"
    OVERFLOW_ERROR = "E009"
    INVALID_EXPRESSION = "E010"
    IO_ERROR = "E011"


class CalcError(Exception):
    """计算器错误基类"""
    def __init__(self, error_type: ErrorType, message: str, position: int = 0):
        self.error_type = error_type
        self.message = message
        self.position = position
        super().__init__(f"[{error_type.value}] {message}")


class DivisionByZeroError(CalcError):
    """除零错误"""
    def __init__(self, position: int = 0):
        super().__init__(ErrorType.DIVISION_BY_ZERO, "Division by zero", position)


class SyntaxError(CalcError):
    """语法错误"""
    def __init__(self, message: str, position: int = 0):
        super().__init__(ErrorType.SYNTAX_ERROR, message, position)


class InvalidTokenError(CalcError):
    """无效词法单元错误"""
    def __init__(self, token: str, position: int = 0):
        super().__init__(ErrorType.INVALID_TOKEN, f"Invalid token: '{token}'", position)


class UndefinedVariableError(CalcError):
    """未定义变量错误"""
    def __init__(self, name: str, position: int = 0):
        super().__init__(ErrorType.UNDEFINED_VARIABLE, f"Undefined variable: '{name}'", position)


class UndefinedFunctionError(CalcError):
    """未定义函数错误"""
    def __init__(self, name: str, position: int = 0):
        super().__init__(ErrorType.UNDEFINED_FUNCTION, f"Undefined function: '{name}'", position)


class ArgumentCountError(CalcError):
    """参数数量错误"""
    def __init__(self, name: str, expected: int, got: int, position: int = 0):
        super().__init__(ErrorType.ARGUMENT_COUNT, 
                        f"Function '{name}' expects {expected} arguments, got {got}", position)


class DomainError(CalcError):
    """数学定义域错误"""
    def __init__(self, message: str, position: int = 0):
        super().__init__(ErrorType.DOMAIN_ERROR, message, position)


# ============================================================================
# Token 类型定义
# ============================================================================

class TokenType(Enum):
    """词法单元类型枚举"""
    NUMBER = auto()         # 数字（整数或浮点数）
    PLUS = auto()           # + 加号
    MINUS = auto()          # - 减号
    MULTIPLY = auto()       # * 乘号
    DIVIDE = auto()         # / 除号
    POWER = auto()          # ^ 幂运算
    LPAREN = auto()         # ( 左括号
    RPAREN = auto()         # ) 右括号
    COMMA = auto()          # , 逗号
    IDENTIFIER = auto()     # 标识符（函数名、变量名）
    TO = auto()             # to 关键字（进制转换）
    BIN_PREFIX = auto()     # 0b 二进制前缀
    OCT_PREFIX = auto()     # 0o 八进制前缀
    HEX_PREFIX = auto()     # 0x 十六进制前缀
    ASSIGN = auto()         # = 赋值
    EOF = auto()            # 结束符


@dataclass
class Token:
    """词法单元"""
    type: TokenType
    value: str
    position: int = 0


# ============================================================================
# AST 节点定义
# ============================================================================

class ASTNode:
    """抽象语法树节点基类"""
    pass


@dataclass
class NumberNode(ASTNode):
    """数值节点"""
    value: Union[int, float]
    is_integer: bool = True


@dataclass
class BinaryOpNode(ASTNode):
    """二元运算节点"""
    left: ASTNode
    operator: TokenType
    right: ASTNode


@dataclass
class UnaryOpNode(ASTNode):
    """一元运算节点"""
    operator: TokenType
    operand: ASTNode


@dataclass
class CallNode(ASTNode):
    """函数调用节点"""
    func_name: str
    arguments: List[ASTNode]


@dataclass
class ConvertNode(ASTNode):
    """进制转换节点"""
    value: ASTNode
    target_base: str


@dataclass
class VariableNode(ASTNode):
    """变量节点"""
    name: str


@dataclass
class AssignNode(ASTNode):
    """赋值节点"""
    name: str
    value: ASTNode


# ============================================================================
# 数值类型定义
# ============================================================================

@dataclass
class Number:
    """数值类型"""
    value: Union[int, float]
    display_format: str = "dec"  # dec/bin/oct/hex/float
    precision: int = 6
    
    def __str__(self) -> str:
        if self.display_format == "bin":
            if isinstance(self.value, float) and not self.value.is_integer():
                raise TypeError("Cannot convert float to binary")
            return f"0b{int(self.value):b}"
        elif self.display_format == "oct":
            if isinstance(self.value, float) and not self.value.is_integer():
                raise TypeError("Cannot convert float to octal")
            return f"0o{int(self.value):o}"
        elif self.display_format == "hex":
            if isinstance(self.value, float) and not self.value.is_integer():
                raise TypeError("Cannot convert float to hexadecimal")
            return f"0x{int(self.value):X}"
        else:
            if isinstance(self.value, float):
                # 如果是整数形式的浮点数，显示为整数
                if self.value.is_integer():
                    return str(int(self.value))
                # 格式化浮点数，去除末尾的0
                formatted = f"{self.value:.{self.precision}f}"
                return formatted.rstrip('0').rstrip('.') if '.' in formatted else formatted
            return str(self.value)


# ============================================================================
# 历史记录定义
# ============================================================================

@dataclass
class HistoryRecord:
    """历史记录"""
    id: int
    expression: str
    result: str
    timestamp: str
    success: bool
    error_message: str = ""


# ============================================================================
# 词法分析器
# ============================================================================

class Lexer:
    """词法分析器"""
    
    def __init__(self, expression: str):
        self.expression = expression
        self.position = 0
        self.tokens: List[Token] = []
    
    def tokenize(self) -> List[Token]:
        """词法分析主函数"""
        while self.position < len(self.expression):
            char = self.expression[self.position]
            
            # 跳过空白字符
            if char.isspace():
                self.position += 1
                continue
            
            # 数字（包括进制前缀）
            if char.isdigit() or (char == '.' and self._peek_next().isdigit()):
                self._read_number()
            # 标识符或关键字
            elif char.isalpha() or char == '_':
                self._read_identifier()
            # 运算符和分隔符
            elif char == '+':
                self.tokens.append(Token(TokenType.PLUS, char, self.position))
                self.position += 1
            elif char == '-':
                self.tokens.append(Token(TokenType.MINUS, char, self.position))
                self.position += 1
            elif char == '*':
                self.tokens.append(Token(TokenType.MULTIPLY, char, self.position))
                self.position += 1
            elif char == '/':
                self.tokens.append(Token(TokenType.DIVIDE, char, self.position))
                self.position += 1
            elif char == '^':
                self.tokens.append(Token(TokenType.POWER, char, self.position))
                self.position += 1
            elif char == '(':
                self.tokens.append(Token(TokenType.LPAREN, char, self.position))
                self.position += 1
            elif char == ')':
                self.tokens.append(Token(TokenType.RPAREN, char, self.position))
                self.position += 1
            elif char == ',':
                self.tokens.append(Token(TokenType.COMMA, char, self.position))
                self.position += 1
            elif char == '=':
                self.tokens.append(Token(TokenType.ASSIGN, char, self.position))
                self.position += 1
            else:
                raise InvalidTokenError(char, self.position)
        
        self.tokens.append(Token(TokenType.EOF, "", self.position))
        return self.tokens
    
    def _peek_next(self) -> str:
        """查看下一个字符"""
        if self.position + 1 < len(self.expression):
            return self.expression[self.position + 1]
        return ""
    
    def _read_number(self):
        """读取数字（支持整数、浮点数、进制前缀）"""
        start_pos = self.position
        num_str = ""
        is_integer = True
        
        # 检查进制前缀
        if self.expression[self.position] == '0' and self.position + 1 < len(self.expression):
            next_char = self.expression[self.position + 1].lower()
            if next_char == 'b':
                # 二进制
                self.position += 2
                bin_str = ""
                while self.position < len(self.expression) and self.expression[self.position] in '01':
                    bin_str += self.expression[self.position]
                    self.position += 1
                if not bin_str:
                    raise SyntaxError("Invalid binary number", start_pos)
                value = int(bin_str, 2)
                self.tokens.append(Token(TokenType.NUMBER, str(value), start_pos))
                return
            elif next_char == 'o':
                # 八进制
                self.position += 2
                oct_str = ""
                while self.position < len(self.expression) and self.expression[self.position] in '01234567':
                    oct_str += self.expression[self.position]
                    self.position += 1
                if not oct_str:
                    raise SyntaxError("Invalid octal number", start_pos)
                value = int(oct_str, 8)
                self.tokens.append(Token(TokenType.NUMBER, str(value), start_pos))
                return
            elif next_char == 'x':
                # 十六进制
                self.position += 2
                hex_str = ""
                while (self.position < len(self.expression) and 
                       self.expression[self.position].lower() in '0123456789abcdef'):
                    hex_str += self.expression[self.position]
                    self.position += 1
                if not hex_str:
                    raise SyntaxError("Invalid hexadecimal number", start_pos)
                value = int(hex_str, 16)
                self.tokens.append(Token(TokenType.NUMBER, str(value), start_pos))
                return
        
        # 普通数字（整数或浮点数）
        while self.position < len(self.expression):
            char = self.expression[self.position]
            if char.isdigit():
                num_str += char
                self.position += 1
            elif char == '.' and is_integer:
                # 检查是否已经有小数点
                if '.' in num_str:
                    break
                num_str += char
                is_integer = False
                self.position += 1
            elif char.lower() == 'e' and not is_integer:
                # 科学计数法
                num_str += char
                self.position += 1
                if self.position < len(self.expression) and self.expression[self.position] in '+-':
                    num_str += self.expression[self.position]
                    self.position += 1
            else:
                break
        
        self.tokens.append(Token(TokenType.NUMBER, num_str, start_pos))
    
    def _read_identifier(self):
        """读取标识符"""
        start_pos = self.position
        ident = ""
        
        while (self.position < len(self.expression) and 
               (self.expression[self.position].isalnum() or self.expression[self.position] == '_')):
            ident += self.expression[self.position]
            self.position += 1
        
        # 检查是否是关键字
        if ident.lower() == 'to':
            self.tokens.append(Token(TokenType.TO, ident, start_pos))
        else:
            self.tokens.append(Token(TokenType.IDENTIFIER, ident, start_pos))


# ============================================================================
# 语法分析器（递归下降解析器）
# ============================================================================

class Parser:
    """语法分析器"""
    
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.position = 0
    
    def parse(self) -> ASTNode:
        """语法分析入口"""
        return self._parse_assignment()
    
    def _current_token(self) -> Token:
        """获取当前词法单元"""
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return self.tokens[-1]  # EOF
    
    def _advance(self):
        """前进到下一个词法单元"""
        if self.position < len(self.tokens) - 1:
            self.position += 1
    
    def _expect(self, token_type: TokenType) -> Token:
        """期望特定类型的词法单元"""
        current = self._current_token()
        if current.type != token_type:
            raise SyntaxError(f"Expected {token_type.name}, got {current.type.name}", current.position)
        self._advance()
        return current
    
    def _parse_assignment(self) -> ASTNode:
        """解析赋值表达式"""
        # 检查是否是赋值语句
        if (self._current_token().type == TokenType.IDENTIFIER and 
            self.position + 1 < len(self.tokens) and 
            self.tokens[self.position + 1].type == TokenType.ASSIGN):
            var_name = self._current_token().value
            self._advance()  # 跳过变量名
            self._advance()  # 跳过等号
            value = self._parse_expression()
            return AssignNode(var_name, value)
        
        return self._parse_expression()
    
    def _parse_expression(self) -> ASTNode:
        """解析加减表达式"""
        return self._parse_add_sub()
    
    def _parse_add_sub(self) -> ASTNode:
        """解析加减运算"""
        left = self._parse_mul_div()
        
        while self._current_token().type in (TokenType.PLUS, TokenType.MINUS):
            op = self._current_token().type
            self._advance()
            right = self._parse_mul_div()
            left = BinaryOpNode(left, op, right)
        
        return left
    
    def _parse_mul_div(self) -> ASTNode:
        """解析乘除运算"""
        left = self._parse_power()
        
        while self._current_token().type in (TokenType.MULTIPLY, TokenType.DIVIDE):
            op = self._current_token().type
            self._advance()
            right = self._parse_power()
            left = BinaryOpNode(left, op, right)
        
        return left
    
    def _parse_power(self) -> ASTNode:
        """解析幂运算（右结合）"""
        left = self._parse_unary()
        
        if self._current_token().type == TokenType.POWER:
            self._advance()
            right = self._parse_power()  # 右结合
            left = BinaryOpNode(left, TokenType.POWER, right)
        
        return left
    
    def _parse_unary(self) -> ASTNode:
        """解析一元运算（正负号）"""
        if self._current_token().type in (TokenType.PLUS, TokenType.MINUS):
            op = self._current_token().type
            self._advance()
            operand = self._parse_unary()
            return UnaryOpNode(op, operand)
        
        return self._parse_conversion()
    
    def _parse_conversion(self) -> ASTNode:
        """解析进制转换"""
        left = self._parse_primary()
        
        # 检查是否有 to 关键字
        if self._current_token().type == TokenType.TO:
            self._advance()
            if self._current_token().type == TokenType.IDENTIFIER:
                target = self._current_token().value.lower()
                if target not in ('bin', 'oct', 'dec', 'hex'):
                    raise SyntaxError(f"Unknown base: {target}", self._current_token().position)
                self._advance()
                return ConvertNode(left, target)
            else:
                raise SyntaxError("Expected base name after 'to'", self._current_token().position)
        
        return left
    
    def _parse_primary(self) -> ASTNode:
        """解析基本元素"""
        current = self._current_token()
        
        # 数字
        if current.type == TokenType.NUMBER:
            self._advance()
            value = float(current.value)
            is_int = '.' not in current.value and 'e' not in current.value.lower()
            if is_int and value == int(value):
                return NumberNode(int(value), True)
            return NumberNode(value, False)
        
        # 标识符（变量或函数调用）
        if current.type == TokenType.IDENTIFIER:
            return self._parse_identifier_or_call()
        
        # 括号表达式
        if current.type == TokenType.LPAREN:
            self._advance()
            node = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return node
        
        raise SyntaxError(f"Unexpected token: {current.value}", current.position)
    
    def _parse_identifier_or_call(self) -> ASTNode:
        """解析标识符（变量或函数调用）"""
        name = self._current_token().value
        position = self._current_token().position
        self._advance()
        
        # 检查是否是函数调用
        if self._current_token().type == TokenType.LPAREN:
            self._advance()  # 跳过左括号
            args = []
            
            # 解析参数列表
            if self._current_token().type != TokenType.RPAREN:
                args.append(self._parse_expression())
                while self._current_token().type == TokenType.COMMA:
                    self._advance()
                    args.append(self._parse_expression())
            
            self._expect(TokenType.RPAREN)
            return CallNode(name, args)
        
        # 变量
        return VariableNode(name)


# ============================================================================
# 求值上下文（变量管理）
# ============================================================================

class EvalContext:
    """求值上下文"""
    
    def __init__(self):
        self.variables: Dict[str, Number] = {}
        self.constants = {
            'pi': Number(math.pi),
            'e': Number(math.e),
        }
    
    def set_variable(self, name: str, value: Number):
        """设置变量"""
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            raise ValueError(f"Invalid variable name: {name}")
        self.variables[name] = value
    
    def get_variable(self, name: str) -> Number:
        """获取变量值"""
        if name in self.variables:
            return self.variables[name]
        if name in self.constants:
            return self.constants[name]
        raise UndefinedVariableError(name)
    
    def list_variables(self) -> Dict[str, Number]:
        """列出所有变量"""
        result = dict(self.constants)
        result.update(self.variables)
        return result


# ============================================================================
# 数学函数库
# ============================================================================

class FunctionRegistry:
    """函数注册表"""
    
    def __init__(self):
        self.functions: Dict[str, callable] = {
            # 三角函数
            'sin': self._sin,
            'cos': self._cos,
            'tan': self._tan,
            'asin': self._asin,
            'acos': self._acos,
            'atan': self._atan,
            # 数学函数
            'sqrt': self._sqrt,
            'log': self._log,
            'ln': self._ln,
            'exp': self._exp,
            'abs': self._abs,
            'floor': self._floor,
            'ceil': self._ceil,
            'round': self._round,
            'rad': self._rad,  # 角度转弧度
            'deg': self._deg,  # 弧度转角度
        }
    
    def call(self, name: str, args: List[Number]) -> Number:
        """调用函数"""
        if name not in self.functions:
            raise UndefinedFunctionError(name)
        
        func = self.functions[name]
        
        # 检查参数数量
        import inspect
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        
        # 获取函数期望的参数数量（排除self）
        expected_args = len([p for p in params if p != 'self'])
        
        # 处理可变参数
        if expected_args == 1 and name not in ['log']:
            # 单参数函数
            if len(args) != 1:
                raise ArgumentCountError(name, 1, len(args))
        elif name == 'log':
            # log 可以有1或2个参数
            if len(args) < 1 or len(args) > 2:
                raise ArgumentCountError(name, "1 or 2", len(args))
        
        return func(*[arg.value for arg in args])
    
    def _sin(self, x: float) -> Number:
        return Number(math.sin(x))
    
    def _cos(self, x: float) -> Number:
        return Number(math.cos(x))
    
    def _tan(self, x: float) -> Number:
        return Number(math.tan(x))
    
    def _asin(self, x: float) -> Number:
        if x < -1 or x > 1:
            raise DomainError("asin argument must be in range [-1, 1]")
        return Number(math.asin(x))
    
    def _acos(self, x: float) -> Number:
        if x < -1 or x > 1:
            raise DomainError("acos argument must be in range [-1, 1]")
        return Number(math.acos(x))
    
    def _atan(self, x: float) -> Number:
        return Number(math.atan(x))
    
    def _sqrt(self, x: float) -> Number:
        if x < 0:
            raise DomainError("Cannot compute square root of negative number")
        return Number(math.sqrt(x))
    
    def _log(self, x: float, base: float = 10) -> Number:
        if x <= 0:
            raise DomainError("log argument must be positive")
        if base <= 0 or base == 1:
            raise DomainError("log base must be positive and not equal to 1")
        return Number(math.log(x, base))
    
    def _ln(self, x: float) -> Number:
        if x <= 0:
            raise DomainError("ln argument must be positive")
        return Number(math.log(x))
    
    def _exp(self, x: float) -> Number:
        return Number(math.exp(x))
    
    def _abs(self, x: float) -> Number:
        return Number(abs(x))
    
    def _floor(self, x: float) -> Number:
        return Number(math.floor(x))
    
    def _ceil(self, x: float) -> Number:
        return Number(math.ceil(x))
    
    def _round(self, x: float) -> Number:
        return Number(round(x))
    
    def _rad(self, deg: float) -> Number:
        """角度转弧度"""
        return Number(math.radians(deg))
    
    def _deg(self, rad: float) -> Number:
        """弧度转角度"""
        return Number(math.degrees(rad))


# ============================================================================
# 求值器
# ============================================================================

class Evaluator:
    """AST求值器"""
    
    def __init__(self, context: EvalContext, functions: FunctionRegistry):
        self.context = context
        self.functions = functions
    
    def evaluate(self, ast: ASTNode) -> Number:
        """求值AST节点"""
        if isinstance(ast, NumberNode):
            return Number(ast.value, "dec" if not ast.is_integer else "dec")
        
        elif isinstance(ast, BinaryOpNode):
            left = self.evaluate(ast.left)
            right = self.evaluate(ast.right)
            return self._apply_binary_op(ast.operator, left, right)
        
        elif isinstance(ast, UnaryOpNode):
            operand = self.evaluate(ast.operand)
            return self._apply_unary_op(ast.operator, operand)
        
        elif isinstance(ast, CallNode):
            args = [self.evaluate(arg) for arg in ast.arguments]
            return self.functions.call(ast.func_name, args)
        
        elif isinstance(ast, ConvertNode):
            value = self.evaluate(ast.value)
            return self._convert_base(value, ast.target_base)
        
        elif isinstance(ast, VariableNode):
            return self.context.get_variable(ast.name)
        
        elif isinstance(ast, AssignNode):
            value = self.evaluate(ast.value)
            self.context.set_variable(ast.name, value)
            return value
        
        else:
            raise CalcError(ErrorType.INVALID_EXPRESSION, f"Unknown AST node type: {type(ast)}")
    
    def _apply_binary_op(self, op: TokenType, left: Number, right: Number) -> Number:
        """应用二元运算符"""
        lval = left.value
        rval = right.value
        
        if op == TokenType.PLUS:
            return Number(lval + rval)
        elif op == TokenType.MINUS:
            return Number(lval - rval)
        elif op == TokenType.MULTIPLY:
            return Number(lval * rval)
        elif op == TokenType.DIVIDE:
            if rval == 0:
                raise DivisionByZeroError()
            return Number(lval / rval)
        elif op == TokenType.POWER:
            return Number(pow(lval, rval))
        else:
            raise CalcError(ErrorType.INVALID_EXPRESSION, f"Unknown operator: {op}")
    
    def _apply_unary_op(self, op: TokenType, operand: Number) -> Number:
        """应用一元运算符"""
        val = operand.value
        
        if op == TokenType.PLUS:
            return Number(val)
        elif op == TokenType.MINUS:
            return Number(-val)
        else:
            raise CalcError(ErrorType.INVALID_EXPRESSION, f"Unknown unary operator: {op}")
    
    def _convert_base(self, value: Number, target_base: str) -> Number:
        """进制转换"""
        if target_base == "dec":
            return Number(value.value, "dec")
        elif target_base == "bin":
            if isinstance(value.value, float) and not value.value.is_integer():
                raise TypeError("Cannot convert float to binary")
            return Number(int(value.value), "bin")
        elif target_base == "oct":
            if isinstance(value.value, float) and not value.value.is_integer():
                raise TypeError("Cannot convert float to octal")
            return Number(int(value.value), "oct")
        elif target_base == "hex":
            if isinstance(value.value, float) and not value.value.is_integer():
                raise TypeError("Cannot convert float to hexadecimal")
            return Number(int(value.value), "hex")
        else:
            raise ValueError(f"Unknown base: {target_base}")


# ============================================================================
# 历史记录管理
# ============================================================================

class HistoryManager:
    """历史记录管理器"""
    
    MAX_HISTORY = 100
    
    def __init__(self):
        self.history_file = os.path.expanduser("~/.calc_history.json")
        self.records: List[HistoryRecord] = []
        self._load()
    
    def _load(self):
        """加载历史记录"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.records = [HistoryRecord(**record) for record in data]
        except Exception:
            # 如果加载失败，重置为空列表
            self.records = []
    
    def _save(self):
        """保存历史记录"""
        try:
            # 确保目录存在
            history_dir = os.path.dirname(self.history_file)
            if history_dir and not os.path.exists(history_dir):
                os.makedirs(history_dir, exist_ok=True)
            
            # 保存到文件，设置权限为仅当前用户可读写
            data = [record.__dict__ for record in self.records]
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 设置文件权限（仅当前用户可读写）
            os.chmod(self.history_file, 0o600)
        except Exception as e:
            # 历史记录保存失败不影响主功能
            pass
    
    def add(self, expression: str, result: str, success: bool = True, error_message: str = ""):
        """添加历史记录"""
        record = HistoryRecord(
            id=len(self.records) + 1,
            expression=expression,
            result=result,
            timestamp=datetime.now().isoformat(),
            success=success,
            error_message=error_message
        )
        
        self.records.append(record)
        
        # 限制历史记录数量
        if len(self.records) > self.MAX_HISTORY:
            self.records = self.records[-self.MAX_HISTORY:]
            # 重新编号
            for i, rec in enumerate(self.records):
                rec.id = i + 1
        
        self._save()
    
    def get_all(self, limit: int = 100) -> List[HistoryRecord]:
        """获取所有历史记录"""
        return self.records[-limit:][::-1]  # 倒序返回
    
    def clear(self):
        """清空历史记录"""
        self.records = []
        self._save()
    
    def display(self):
        """显示历史记录"""
        if not self.records:
            print("暂无历史记录")
            return
        
        print("\n计算历史记录：")
        print("-" * 60)
        print(f"{'ID':<5}{'表达式':<30}{'结果':<15}{'时间':<20}")
        print("-" * 60)
        
        for record in self.get_all():
            expr = record.expression[:28] + ".." if len(record.expression) > 30 else record.expression
            result = record.result[:13] + ".." if len(record.result) > 15 else record.result
            time_str = record.timestamp[:19]  # 去掉毫秒
            status = "✓" if record.success else "✗"
            print(f"{record.id:<5}{expr:<30}{result:<15}{time_str:<18} {status}")
        
        print("-" * 60)


# ============================================================================
# 表达式计算器（整合解析和求值）
# ============================================================================

class ExpressionCalculator:
    """表达式计算器"""
    
    def __init__(self):
        self.context = EvalContext()
        self.functions = FunctionRegistry()
        self.history = HistoryManager()
    
    def calculate(self, expression: str) -> Tuple[bool, str]:
        """
        计算表达式
        返回: (是否成功, 结果或错误信息)
        """
        try:
            # 词法分析
            lexer = Lexer(expression)
            tokens = lexer.tokenize()
            
            # 语法分析
            parser = Parser(tokens)
            ast = parser.parse()
            
            # 求值
            evaluator = Evaluator(self.context, self.functions)
            result = evaluator.evaluate(ast)
            
            # 格式化结果
            result_str = str(result)
            
            # 添加到历史记录
            self.history.add(expression, result_str, True)
            
            return True, result_str
            
        except CalcError as e:
            error_msg = f"Error: {e.message}"
            self.history.add(expression, "", False, error_msg)
            return False, error_msg
        except TypeError as e:
            error_msg = f"Error: {str(e)}"
            self.history.add(expression, "", False, error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.history.add(expression, "", False, error_msg)
            return False, error_msg


# ============================================================================
# 命令行参数解析
# ============================================================================

class Args:
    """命令行参数"""
    def __init__(self):
        self.mode: str = "direct"  # direct|interactive|history|help|file|vars
        self.expression: Optional[str] = None
        self.file_path: Optional[str] = None


def parse_args(argv: List[str]) -> Args:
    """解析命令行参数"""
    args = Args()
    
    if len(argv) <= 1:
        # 无参数，进入交互模式
        args.mode = "interactive"
        return args
    
    # 解析选项
    i = 1
    while i < len(argv):
        arg = argv[i]
        
        if arg in ('-h', '--help'):
            args.mode = "help"
            return args
        elif arg in ('-i', '--interactive'):
            args.mode = "interactive"
        elif arg == '--history':
            args.mode = "history"
        elif arg in ('-f', '--file'):
            args.mode = "file"
            i += 1
            if i < len(argv):
                args.file_path = argv[i]
            else:
                print("Error: Missing file path after -f/--file")
                sys.exit(1)
        elif arg == '--vars':
            args.mode = "vars"
        elif arg == '--clear-history':
            args.mode = "clear_history"
        else:
            # 表达式参数
            if args.expression is None:
                args.expression = arg
            else:
                args.expression += " " + arg
        
        i += 1
    
    # 如果没有表达式且不是其他模式，进入交互模式
    if args.mode == "direct" and args.expression is None:
        args.mode = "interactive"
    
    return args


# ============================================================================
# 帮助信息
# ============================================================================

HELP_TEXT = """
命令行计算器 - 使用说明

用法：
    calc <表达式>           直接计算表达式
    calc -i, --interactive  进入交互模式
    calc --history          查看计算历史
    calc --clear-history    清空历史记录
    calc --vars             查看已定义变量
    calc -f <文件>          从文件批量计算
    calc -h, --help         显示此帮助信息

基本运算：
    +  加法        例: calc 1 + 2
    -  减法        例: calc 5 - 3
    *  乘法        例: calc 4 * 5
    /  除法        例: calc 10 / 2
    ^  幂运算      例: calc 2 ^ 10
    %  取模        例: calc 10 % 3

科学计算函数：
    sin(x)      正弦函数（弧度）
    cos(x)      余弦函数（弧度）
    tan(x)      正切函数（弧度）
    asin(x)     反正弦
    acos(x)     反余弦
    atan(x)     反正切
    sqrt(x)     平方根
    log(x,base) 对数（默认底数为10）
    ln(x)       自然对数
    exp(x)      e的x次幂
    abs(x)      绝对值
    floor(x)    向下取整
    ceil(x)     向上取整
    round(x)    四舍五入
    rad(deg)    角度转弧度
    deg(rad)    弧度转角度

进制转换：
    to bin      转换为二进制    例: calc 255 to bin
    to oct      转换为八进制    例: calc 64 to oct
    to dec      转换为十进制    例: calc 0xFF to dec
    to hex      转换为十六进制  例: calc 255 to hex

进制前缀：
    0b          二进制          例: calc 0b1010 + 0b1100
    0o          八进制          例: calc 0o77
    0x          十六进制        例: calc 0xFF

变量：
    定义变量:   例: calc "x = 10"
    使用变量:   例: calc "x + 5"
    常量:       pi, e

交互模式命令：
    exit, quit  退出交互模式
    help        显示帮助信息
    history     显示历史记录
    vars        显示变量列表
    clear       清空历史记录

示例：
    calc "1 + 2 * 3"              # 输出: 7
    calc "(1 + 2) * 3"            # 输出: 9
    calc "sqrt(16) + 2 ^ 3"       # 输出: 12
    calc "sin(3.14159/2)"         # 输出: 1
    calc "0xFF to bin"            # 输出: 0b11111111
    calc "x = 100"                # 定义变量x
    calc "x / 4"                  # 使用变量x
"""


# ============================================================================
# 交互模式（REPL）
# ============================================================================

def run_interactive(calculator: ExpressionCalculator):
    """运行交互式REPL环境"""
    print("命令行计算器 - 交互模式")
    print("输入 'help' 查看帮助，输入 'exit' 或按 Ctrl+C 退出")
    print()
    
    while True:
        try:
            # 读取用户输入
            try:
                expression = input("calc> ").strip()
            except EOFError:
                print()
                break
            
            # 空输入则继续
            if not expression:
                continue
            
            # 处理特殊命令
            cmd = expression.lower()
            if cmd in ('exit', 'quit', 'q'):
                print("再见！")
                break
            elif cmd == 'help':
                print(HELP_TEXT)
                continue
            elif cmd == 'history':
                calculator.history.display()
                continue
            elif cmd == 'vars':
                display_variables(calculator.context)
                continue
            elif cmd == 'clear':
                calculator.history.clear()
                print("历史记录已清空")
                continue
            
            # 计算表达式
            success, result = calculator.calculate(expression)
            if success:
                print(result)
            else:
                print(result)
                
        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"Error: {str(e)}")


def display_variables(context: EvalContext):
    """显示变量列表"""
    variables = context.list_variables()
    if not variables:
        print("暂无变量")
        return
    
    print("\n变量列表：")
    print("-" * 40)
    print(f"{'名称':<20}{'值':<20}")
    print("-" * 40)
    
    for name, value in variables.items():
        val_str = str(value)
        print(f"{name:<20}{val_str:<20}")
    
    print("-" * 40)


# ============================================================================
# 批处理模式
# ============================================================================

def run_batch(calculator: ExpressionCalculator, file_path: str):
    """从文件批量计算"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"从文件 {file_path} 批量计算：")
        print("-" * 60)
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            print(f"[{i}] {line}")
            success, result = calculator.calculate(line)
            if success:
                print(f"    = {result}")
            else:
                print(f"    {result}")
        
        print("-" * 60)
        print("批量计算完成")
        
    except FileNotFoundError:
        print(f"Error: 文件不存在: {file_path}")
    except Exception as e:
        print(f"Error: 读取文件失败: {str(e)}")


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主入口函数"""
    try:
        # 解析命令行参数
        args = parse_args(sys.argv)
        
        # 创建计算器实例
        calculator = ExpressionCalculator()
        
        # 根据模式执行相应操作
        if args.mode == "help":
            print(HELP_TEXT)
        
        elif args.mode == "interactive":
            run_interactive(calculator)
        
        elif args.mode == "history":
            calculator.history.display()
        
        elif args.mode == "clear_history":
            calculator.history.clear()
            print("历史记录已清空")
        
        elif args.mode == "vars":
            display_variables(calculator.context)
        
        elif args.mode == "file":
            if args.file_path:
                run_batch(calculator, args.file_path)
            else:
                print("Error: 请指定文件路径")
                sys.exit(1)
        
        elif args.mode == "direct":
            if args.expression:
                success, result = calculator.calculate(args.expression)
                print(result)
                if not success:
                    sys.exit(1)
            else:
                # 无表达式，进入交互模式
                run_interactive(calculator)
        
        else:
            print(f"Error: 未知模式: {args.mode}")
            sys.exit(1)
    
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
