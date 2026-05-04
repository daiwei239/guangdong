import uuid


def generate_id(prefix: str) -> str:
    return "{0}-{1}".format(prefix, uuid.uuid4().hex[:10])
