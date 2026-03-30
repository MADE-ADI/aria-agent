"""Calculator skill — safe math evaluation."""
import ast
import math
import operator

# Safe operators
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}

FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "abs": abs,
    "round": round,
    "pi": math.pi,
    "e": math.e,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        op = OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    elif isinstance(node, ast.UnaryOp):
        op = OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported unary operator")
        return op(_safe_eval(node.operand))
    elif isinstance(node, ast.Call):
        func_name = node.func.id if isinstance(node.func, ast.Name) else None
        if func_name in FUNCTIONS and callable(FUNCTIONS[func_name]):
            args = [_safe_eval(a) for a in node.args]
            return FUNCTIONS[func_name](*args)
        raise ValueError(f"Unknown function: {func_name}")
    elif isinstance(node, ast.Name):
        if node.id in FUNCTIONS:
            return FUNCTIONS[node.id]
        raise ValueError(f"Unknown variable: {node.id}")
    else:
        raise ValueError(f"Unsupported expression type: {type(node).__name__}")


def execute(expression: str) -> dict:
    """Safely evaluate a math expression."""
    try:
        # Normalize common patterns
        expr = expression.replace("^", "**").replace("×", "*").replace("÷", "/")
        tree = ast.parse(expr, mode="eval")
        result = _safe_eval(tree.body)
        return {"status": "ok", "expression": expression, "result": result}
    except Exception as e:
        return {"status": "error", "expression": expression, "error": str(e)}
