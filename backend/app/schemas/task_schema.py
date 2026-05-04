from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, Field

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover
    ConfigDict = None


class TaskProfileBase(BaseModel):
    task_id: str
    task_type: str
    dag_nodes: List[Dict]
    compute_req: Dict
    memory_req: Dict
    storage_req: Dict
    network_req: Dict
    energy_limit: float
    qos_deadline_sec: float
    priority: int
    constraints: Dict


class TaskProfileCreate(TaskProfileBase):
    pass


class TaskProfileRead(TaskProfileBase):
    created_at: datetime = Field(default_factory=datetime.utcnow)

    if ConfigDict is not None:
        model_config = ConfigDict(from_attributes=True)
    else:
        class Config:
            orm_mode = True
