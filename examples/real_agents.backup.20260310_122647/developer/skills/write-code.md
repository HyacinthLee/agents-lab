# Skill: Write Code

## 描述
根据技术规格编写高质量代码

## 输入
- PRD 或技术规格
- 技术栈限制（如有）
- 已有代码上下文（如有）

## 编码原则
1. **清晰优于 clever**: 代码是写给人看的
2. **小函数**: 单一职责，不超过 50 行
3. **类型安全**: 使用类型注解
4. **防御式编程**: 验证输入，处理异常

## 输出结构
```
project/
├── src/
│   └── main_module.py
├── tests/
│   └── test_main.py
├── README.md
└── requirements.txt
```

## 代码模板 (Python)
```python
"""模块简短描述.

详细说明模块的功能和使用方式.
"""

from typing import Optional


def example_function(param: str) -> Optional[int]:
    """函数简短描述.
    
    Args:
        param: 参数说明
        
    Returns:
        返回值说明
        
    Raises:
        ValueError: 什么情况下抛出
    """
    # 实现
    pass
```

## 检查清单
- [ ] 代码符合 PEP 8
- [ ] 有类型注解
- [ ] 有文档字符串
- [ ] 错误处理完善
- [ ] 包含单元测试
