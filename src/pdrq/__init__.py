"""Population Digital Red Queen research scaffold."""

from .algorithms import (
    PopulationConfig,
    run_linear_drq,
    run_population_drq,
    run_static_evolution,
)
from .metrics import generality_score, pairwise_diversity, portfolio_score, role_entropy
from .toy_ecology import ROLE_NAMES, ToyCoreWarSurrogate, Warrior

__all__ = [
    "PopulationConfig",
    "ROLE_NAMES",
    "ToyCoreWarSurrogate",
    "Warrior",
    "generality_score",
    "pairwise_diversity",
    "portfolio_score",
    "role_entropy",
    "run_linear_drq",
    "run_population_drq",
    "run_static_evolution",
]
