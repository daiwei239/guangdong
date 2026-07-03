from app.schemas.resource_schema import DEFAULT_SCHEMA_VERSION, RESOURCE_DESCRIPTION_MODULE, MessageEnvelope, ProcessedResourceState


def build_message_id(timestamp: str, sequence: int) -> str:
    date_part = timestamp[:10].replace("-", "")
    if len(date_part) != 8 or not date_part.isdigit():
        date_part = "00000000"
    return f"MSG-{date_part}-{sequence:06d}"


def build_envelope(
    state: ProcessedResourceState,
    message_type: str,
    target_module: list[str],
    payload: dict,
    sequence: int,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
) -> MessageEnvelope:
    return MessageEnvelope(
        schema_version=schema_version,
        message_id=build_message_id(state.timestamp, sequence),
        message_type=message_type,
        source_module=RESOURCE_DESCRIPTION_MODULE,
        target_module=target_module,
        timestamp=state.timestamp,
        trace_id=state.trace_id,
        payload=payload,
    )
