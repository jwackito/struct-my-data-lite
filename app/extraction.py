import pydantic
from instructor import Instructor


def _find_model(namespace: dict) -> type[pydantic.BaseModel]:
    for obj in namespace.values():
        if isinstance(obj, type) and issubclass(obj, pydantic.BaseModel) and obj is not pydantic.BaseModel:
            return obj
    raise ValueError("No Pydantic model found in schema code")


class ExtractionService:
    def __init__(self, client: Instructor):
        self.client = client

    def extract(self, text: str, schema_code: str, model: str) -> dict:
        namespace = {}
        try:
            exec(schema_code, namespace)
        except Exception as e:
            raise ValueError(f"Invalid schema code: {e}") from e

        model_class = _find_model(namespace)
        try:
            result = self.client.chat.completions.create(
                model=model,
                response_model=model_class,
                messages=[{"role": "user", "content": text}],
            )
        except Exception as e:
            raise RuntimeError(f"Extraction failed: {e}") from e

        return result.model_dump()
