import litellm
from deepeval.models.base_model import DeepEvalBaseLLM


class LiteLLMDeepEvalModel(DeepEvalBaseLLM):
    """Adapts any litellm-supported model (openai/anthropic/gemini/ollama/...) to
    DeepEval's model interface, so DeepEval metrics use the same judge_model the
    rest of the eval engine is configured with instead of requiring a separate
    OPENAI_API_KEY. This is DeepEval's documented pattern for non-OpenAI models.
    """

    def load_model(self):
        return self.name

    def generate(self, prompt: str, schema=None) -> str:
        response = litellm.completion(model=self.name, messages=[{"role": "user", "content": prompt}], temperature=0)
        return response.choices[0].message.content or ""

    async def a_generate(self, prompt: str, schema=None) -> str:
        response = await litellm.acompletion(model=self.name, messages=[{"role": "user", "content": prompt}], temperature=0)
        return response.choices[0].message.content or ""

    def get_model_name(self) -> str:
        return self.name
