"""
Safe arithmetic expression evaluation for grading/statistics formulas.

Purpose:
- Replace dynamic `eval(...)` usage with a strict parser/executor.
- Allow only arithmetic over approved variables and numeric literals.

Security model:
- Uses Python AST in `eval` mode.
- Rejects any node types except basic arithmetic expression nodes.
- Rejects function calls, attribute access, indexing, comprehensions, imports, etc.
"""

import ast
from decimal import Decimal


class UnsafeExpressionError(ValueError):
    pass


class _SafeDecimalEvaluator(ast.NodeVisitor):
    _ALLOWED_BINARY_OPS = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
    }
    _ALLOWED_UNARY_OPS = {
        ast.UAdd: lambda a: a,
        ast.USub: lambda a: -a,
    }

    def __init__(self, variables: dict[str, Decimal]):
        self.variables = variables

    def visit_Expression(self, node: ast.Expression) -> Decimal:
        return self.visit(node.body)

    def visit_BinOp(self, node: ast.BinOp) -> Decimal:
        op_type = type(node.op)
        if op_type not in self._ALLOWED_BINARY_OPS:
            raise UnsafeExpressionError(f"Operator not allowed: {op_type.__name__}")
        left = self.visit(node.left)
        right = self.visit(node.right)
        return self._ALLOWED_BINARY_OPS[op_type](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Decimal:
        op_type = type(node.op)
        if op_type not in self._ALLOWED_UNARY_OPS:
            raise UnsafeExpressionError(f"Unary operator not allowed: {op_type.__name__}")
        operand = self.visit(node.operand)
        return self._ALLOWED_UNARY_OPS[op_type](operand)

    def visit_Name(self, node: ast.Name) -> Decimal:
        if node.id not in self.variables:
            raise UnsafeExpressionError(f"Unknown variable: {node.id}")
        return self.variables[node.id]

    def visit_Constant(self, node: ast.Constant) -> Decimal:
        if not isinstance(node.value, (int, float)):
            raise UnsafeExpressionError("Only numeric constants are allowed")
        return Decimal(str(node.value))

    def generic_visit(self, node):
        raise UnsafeExpressionError(f"Expression element not allowed: {type(node).__name__}")


def safe_eval_decimal_expression(expression: str, variables: dict[str, Decimal]) -> Decimal:
    """
    Evaluate an arithmetic expression safely and return a Decimal result.

    Supported:
    - Binary ops: +, -, *, /
    - Unary ops: +, -
    - Numeric constants
    - Named variables provided via `variables`
    """
    parsed = ast.parse(expression, mode="eval")
    evaluator = _SafeDecimalEvaluator(variables)
    return evaluator.visit(parsed)
