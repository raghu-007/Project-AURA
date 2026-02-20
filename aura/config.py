"""Configuration loader for Project-AURA."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ── Default config path ────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = _ROOT / "configs" / "default.yaml"


# ── Nested config dataclasses ──────────────────────────────────

@dataclass
class HerbivoreConfig:
    speed: float = 1.0
    size: float = 1.0
    energy_from_flora: float = 25.0


@dataclass
class PredatorConfig:
    speed: float = 1.5
    size: float = 1.5
    energy_from_prey: float = 50.0
    hunt_success_rate: float = 0.4


@dataclass
class OmnivoreConfig:
    speed: float = 1.2
    size: float = 1.2
    energy_from_flora: float = 15.0
    energy_from_prey: float = 30.0
    hunt_success_rate: float = 0.25


@dataclass
class FaunaConfig:
    initial_herbivores: int = 30
    initial_predators: int = 8
    initial_omnivores: int = 5
    vision_radius: int = 6
    max_age: int = 800
    reproduction_threshold: float = 75.0
    reproduction_cost: float = 40.0
    mutation_rate: float = 0.1
    energy_per_tick: float = -0.3
    herbivore: HerbivoreConfig = field(default_factory=HerbivoreConfig)
    predator: PredatorConfig = field(default_factory=PredatorConfig)
    omnivore: OmnivoreConfig = field(default_factory=OmnivoreConfig)


@dataclass
class FloraTypeConfig:
    energy: float = 10.0
    growth_ticks: int = 20
    max_age: int = 200


@dataclass
class FloraConfig:
    initial_grass: int = 200
    initial_bushes: int = 60
    initial_trees: int = 20
    spread_probability: float = 0.02
    growth_rate: float = 1.0
    max_density: float = 0.6
    grass: FloraTypeConfig = field(default_factory=lambda: FloraTypeConfig(10, 20, 200))
    bush: FloraTypeConfig = field(default_factory=lambda: FloraTypeConfig(25, 60, 500))
    tree: FloraTypeConfig = field(default_factory=lambda: FloraTypeConfig(50, 150, 1500))


@dataclass
class WorldConfig:
    width: int = 80
    height: int = 60
    tick_speed: float = 0.1
    day_length: int = 100
    season_length: int = 500


@dataclass
class EcosystemConfig:
    nutrient_recovery_rate: float = 0.01
    rain_probability: float = 0.005
    drought_probability: float = 0.002
    storm_probability: float = 0.001
    rain_boost: float = 2.0
    drought_penalty: float = 0.3


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    broadcast_interval: int = 2


@dataclass
class AuraConfig:
    """Top-level configuration for the AURA simulation."""
    world: WorldConfig = field(default_factory=WorldConfig)
    fauna: FaunaConfig = field(default_factory=FaunaConfig)
    flora: FloraConfig = field(default_factory=FloraConfig)
    ecosystem: EcosystemConfig = field(default_factory=EcosystemConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


def _merge_dict(target: dict, source: dict) -> dict:
    """Deep-merge source into target."""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _merge_dict(target[key], value)
        else:
            target[key] = value
    return target


def _dict_to_dataclass(cls, data: dict[str, Any]):
    """Recursively convert a dict to a nested dataclass."""
    if not isinstance(data, dict):
        return data
    field_types = {f.name: f.type for f in cls.__dataclass_fields__.values()} if hasattr(cls, '__dataclass_fields__') else {}
    kwargs = {}
    for key, value in data.items():
        if key in field_types:
            # Resolve the actual type for nested dataclasses
            ft = field_types[key]
            actual_type = _resolve_type(ft, cls)
            if actual_type and hasattr(actual_type, '__dataclass_fields__') and isinstance(value, dict):
                kwargs[key] = _dict_to_dataclass(actual_type, value)
            else:
                kwargs[key] = value
    return cls(**kwargs)


def _resolve_type(type_hint, parent_cls) -> type | None:
    """Resolve a type hint string to an actual type."""
    if isinstance(type_hint, type):
        return type_hint
    # Handle string annotations
    if isinstance(type_hint, str):
        # Look up in the module globals
        import sys
        module = sys.modules[parent_cls.__module__]
        return getattr(module, type_hint, None)
    return None


def load_config(path: str | Path | None = None) -> AuraConfig:
    """Load configuration from a YAML file, merged with defaults."""
    # Load defaults
    with open(DEFAULT_CONFIG, "r", encoding="utf-8") as f:
        defaults = yaml.safe_load(f) or {}

    # Load user config if provided
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        _merge_dict(defaults, user_cfg)

    return _dict_to_dataclass(AuraConfig, defaults)
