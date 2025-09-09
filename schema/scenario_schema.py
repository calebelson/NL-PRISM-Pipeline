from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum

# ---------- Pydantic models (schema) ----------

# --- Base with extra='forbid' so the server schema has additionalProperties:false ---
class AppModel(BaseModel):
    model_config = ConfigDict(extra="forbid")  # important for strict schemas

class Safety(str, Enum):
    G = "G"; Y = "Y"; R = "R"

class Edge(AppModel):
    from_: str = Field(alias="from")
    to: str
    distance: float = Field(ge=0)
    safety: Safety

class Graph(AppModel):
    nodes: list[str]
    edges: list[Edge]
    undirected: bool

class Team(AppModel):
    id: str; start: str; capacity: int = Field(ge=1)

class Supply(AppModel):
    node: str; qty: int = Field(ge=0)

class Demand(AppModel):
    node: str; qty: int = Field(ge=0)

class SafetyProbs(AppModel):
    G: float = Field(ge=0, le=1)
    Y: float = Field(ge=0, le=1)
    R: float = Field(ge=0, le=1)

class CostWeights(AppModel):
    distance: float = Field(ge=0)
    risk_penalty: float = Field(ge=0)

class Constraints(AppModel):
    safety_probs: SafetyProbs
    cost_weights: CostWeights
    node_capacity: list[Supply] | None = None

class ScenarioObjective(str, Enum):
    max_reach_prob = "max_reach_prob"
    min_expected_cost = "min_expected_cost"
    multi_objective = "multi_objective"

class Scenario(AppModel):
    graph: Graph
    teams: list[Team]
    resources: list[Supply]
    demands: list[Demand]
    constraints: Constraints
    objective: ScenarioObjective