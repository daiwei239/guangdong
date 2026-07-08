import base64
import json
import ssl
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from app.input.adapters.source_adapter import events_from_grouped_sources
from app.input.resource_event import ResourceEvent
from app.input.state_aggregator import StateAggregator
from app.schemas.resource_schema import SensedResourceState


class EventAdapter(Protocol):
    def fetch_events(self) -> list[ResourceEvent]:
        ...


class JsonPlatformAdapter:
    def __init__(
        self,
        source_type: str,
        source_name: str,
        base_url: str | None = None,
        file_path: Path | str | None = None,
        path: str = "/",
        username: str | None = None,
        password: str | None = None,
        bearer_token: str | None = None,
        verify_tls: bool = True,
        timeout_seconds: float = 10.0,
        request_json: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.source_type = source_type
        self.source_name = source_name
        self.base_url = base_url.rstrip("/") + "/" if base_url else None
        self.file_path = Path(file_path) if file_path is not None else None
        self.path = path
        self.username = username
        self.password = password
        self.bearer_token = bearer_token
        self.verify_tls = verify_tls
        self.timeout_seconds = timeout_seconds
        self.request_json = request_json

    def fetch_events(self) -> list[ResourceEvent]:
        payload = self._read_file() if self.file_path is not None else self._request(self.path)
        return self._events_from_payload(payload)

    def _read_file(self) -> dict[str, Any]:
        return json.loads(self.file_path.read_text(encoding="utf-8-sig"))

    def _events_from_payload(self, payload: dict[str, Any]) -> list[ResourceEvent]:
        if "events" in payload:
            return [ResourceEvent.model_validate(event) for event in payload.get("events", [])]

        if "sources" in payload:
            return events_from_grouped_sources(payload)

        if "nodes" in payload:
            grouped_payload = {
                "timestamp": payload.get("timestamp"),
                "trace_id": payload.get("trace_id"),
                "sources": {
                    self.source_type: {
                        "source_name": self.source_name,
                        "timestamp": payload.get("timestamp"),
                        "trace_id": payload.get("trace_id"),
                        "nodes": payload.get("nodes", []),
                        "edges": payload.get("edges", []),
                    }
                },
            }
            return events_from_grouped_sources(grouped_payload)

        raise ValueError("Platform JSON payload must include events, sources, or nodes")

    def _request(self, path: str) -> dict[str, Any]:
        if self.request_json is not None:
            return self.request_json(path)
        if self.base_url is None:
            raise ValueError("base_url is required when request_json is not provided")

        url = self._url_for_path(path)
        request = Request(url, headers={"Accept": "application/json"})
        if self.bearer_token:
            request.add_header("Authorization", f"Bearer {self.bearer_token}")
        elif self.username is not None and self.password is not None:
            token = f"{self.username}:{self.password}".encode("utf-8")
            request.add_header("Authorization", f"Basic {base64.b64encode(token).decode('ascii')}")

        context = None
        if url.startswith("https://") and not self.verify_tls:
            context = ssl._create_unverified_context()

        with urlopen(request, timeout=self.timeout_seconds, context=context) as response:
            return json.loads(response.read().decode("utf-8"))

    def _url_for_path(self, path: str) -> str:
        if self.base_url is None:
            raise ValueError("base_url is required to build platform URL")
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("/"):
            parsed = urlparse(self.base_url)
            origin = f"{parsed.scheme}://{parsed.netloc}/"
            return urljoin(origin, path.lstrip("/"))
        return urljoin(self.base_url, path)


class FusionDirectorAdapter(JsonPlatformAdapter):
    def __init__(
        self,
        source_name: str = "fusiondirector",
        base_url: str | None = None,
        file_path: Path | str | None = None,
        path: str = "/api/resource-events",
        username: str | None = None,
        password: str | None = None,
        bearer_token: str | None = None,
        verify_tls: bool = True,
        timeout_seconds: float = 10.0,
        request_json: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            source_type="fusiondirector",
            source_name=source_name,
            base_url=base_url,
            file_path=file_path,
            path=path,
            username=username,
            password=password,
            bearer_token=bearer_token,
            verify_tls=verify_tls,
            timeout_seconds=timeout_seconds,
            request_json=request_json,
        )


class HuaweiManagementInputAdapter:
    def __init__(
        self,
        adapters: Iterable[EventAdapter],
        timestamp: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.adapters = list(adapters)
        self.timestamp = timestamp
        self.trace_id = trace_id

    def fetch_state(self) -> SensedResourceState:
        aggregator = StateAggregator(timestamp=self.timestamp, trace_id=self.trace_id)
        for adapter in self.adapters:
            for event in adapter.fetch_events():
                aggregator.ingest(event)
        return aggregator.build_state()
