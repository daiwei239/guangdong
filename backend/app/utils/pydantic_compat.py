def model_dump_compat(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
