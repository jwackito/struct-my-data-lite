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

    def extract(self, content: str | dict, schema_code: str, model: str, on_response=None) -> dict:
        namespace = {}
        try:
            exec(schema_code, namespace)
        except Exception as e:
            raise ValueError(f"Invalid schema code: {e}") from e

        model_class = _find_model(namespace)
        try:
            if isinstance(content, dict) and content.get("type") == "image":
                data_uri = f"data:image/{content['format']};base64,{content['data']}"
                messages = [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract structured data from this image"},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }]
            else:
                messages = [{"role": "user", "content": content}]

            result = self.client.chat.completions.create(
                model=model,
                response_model=model_class,
                messages=messages,
            )
            if on_response:
                on_response(result)
        except Exception as e:
            raise RuntimeError(f"Extraction failed: {e}") from e

        return result.model_dump()
