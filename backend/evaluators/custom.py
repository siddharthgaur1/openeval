"""Custom metric support: users upload a Python function `score(input, output,
expected_output, context) -> float`. Executed in-process with a restricted
builtins set. This is NOT a sandbox — only enable custom metrics for trusted
users in a self-hosted deployment.
"""

SAFE_BUILTINS = {"len", "min", "max", "sum", "abs", "round", "str", "float", "int", "bool", "set", "list", "dict"}


def load_custom_scorer(source: str):
    namespace: dict = {"__builtins__": {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k) for k in SAFE_BUILTINS}}
    exec(source, namespace)
    if "score" not in namespace or not callable(namespace["score"]):
        raise ValueError("Custom metric source must define a callable `score(input, output, expected_output, context)`")
    return namespace["score"]
