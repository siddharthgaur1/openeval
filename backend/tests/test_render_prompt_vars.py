from services.eval_service import render_prompt_vars


def test_render_prompt_vars_substitutes_multiple():
    result = render_prompt_vars("Hello $name, your order $order_id is ready.", {"name": "Ada", "order_id": "42"})
    assert result == "Hello Ada, your order 42 is ready."


def test_render_prompt_vars_leaves_missing_placeholder_literal():
    result = render_prompt_vars("Hello $name, $missing here.", {"name": "Ada"})
    assert result == "Hello Ada, $missing here."
