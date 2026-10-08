import base64

import pydantic
from instructor import Instructor

from app.schema_sandbox import safe_exec


def _find_model(namespace: dict) -> type[pydantic.BaseModel]:
    found = None
    for obj in namespace.values():
        if isinstance(obj, type) and issubclass(obj, pydantic.BaseModel) and obj is not pydantic.BaseModel:
            found = obj
    if found is None:
        raise ValueError("No Pydantic model found in schema code")
    return found


class ExtractionService:
    def __init__(self, client: Instructor):
        self.client = client

    def extract(self, content: str | dict, schema_code: str, model: str, on_response=None) -> dict:
        namespace = {}
        try:
            safe_exec(schema_code, namespace)
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
            elif isinstance(content, dict) and content.get("type") == "image-pdf":
                parts = [{"type": "text", "text": "Extract structured data from this document"}]
                for img in content["images"]:
                    b64 = base64.b64encode(img["data"]).decode("ascii")
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{img['format']};base64,{b64}"},
                    })
                messages = [{"role": "user", "content": parts}]
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
