PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "openai": {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4-turbo": (10.00, 30.00),
        "gpt-4": (30.00, 60.00),
        "gpt-4.1": (2.00, 8.00),
        "gpt-4.1-mini": (0.40, 1.60),
        "gpt-4.1-nano": (0.10, 0.40),
        "o1": (15.00, 60.00),
        "o1-mini": (1.10, 4.40),
        "o3-mini": (1.10, 4.40),
        "__default__": (0.0, 0.0),
    },
    "gemini": {
        "gemini-2.0-flash": (0.10, 0.40),
        "gemini-2.0-pro": (2.00, 8.00),
        "gemini-1.5-pro": (1.25, 5.00),
        "gemini-1.5-flash": (0.075, 0.30),
        "__default__": (0.0, 0.0),
    },
    "ollama": {
        "__default__": (0.0, 0.0),
    },
}


def calculate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING.get(provider, {})
    if model in pricing:
        input_price, output_price = pricing[model]
    else:
        input_price, output_price = pricing.get("__default__", (0.0, 0.0))
        for pattern, (ip, op) in pricing.items():
            if pattern != "__default__" and model.startswith(pattern):
                input_price, output_price = ip, op
                break
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
