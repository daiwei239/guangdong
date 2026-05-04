from time import perf_counter

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from app.api.routes_match import router as match_router
from app.api.routes_resource import router as resource_router
from app.api.routes_simulate import router as simulate_router
from app.api.routes_task import router as task_router
from app.api.routes_ws import router as ws_router
from app.core.config import get_settings
from app.core.database import init_db
from app.services.matching_service import matching_service
from app.services.resource_service import resource_service


settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

resource_node_count = Gauge("resource_node_count", "Current resource node count")
resource_edge_count = Gauge("resource_edge_count", "Current resource edge count")
match_request_total = Counter("match_request_total", "Total match requests")
match_latency_seconds = Histogram("match_latency_seconds", "Match request latency")
candidate_subgraph_count = Gauge("candidate_subgraph_count", "Candidate subgraph count")
top1_score = Gauge("top1_score", "Top1 candidate score")


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    latency = perf_counter() - start
    if request.url.path.endswith("/match") or request.url.path.endswith("/simulate"):
        match_request_total.inc()
        match_latency_seconds.observe(latency)
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@app.get("/metrics")
def metrics() -> Response:
    resource_node_count.set(len(resource_service.get_resources()))
    resource_edge_count.set(len(resource_service.get_edges()))
    current_task = matching_service._results
    if current_task:
        latest = list(current_task.values())[-1]
        candidate_subgraph_count.set(len(latest.candidates))
        top1_score.set(latest.top1.final_score)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(resource_router, prefix=settings.api_prefix)
app.include_router(task_router, prefix=settings.api_prefix)
app.include_router(match_router, prefix=settings.api_prefix)
app.include_router(simulate_router, prefix=settings.api_prefix)
app.include_router(ws_router)
