"""Base Entity class for all living things in the AURA world."""

from __future__ import annotations

import itertools
import math
import threading
from enum import Enum, auto


class EntityType(Enum):
    """High-level entity classification."""
    FLORA = auto()
    HERBIVORE = auto()
    PREDATOR = auto()
    OMNIVORE = auto()


class GrowthStage(Enum):
    """Growth stages for Flora."""
    SEED = auto()
    SPROUT = auto()
    MATURE = auto()
    DECAYING = auto()


# Thread-safe global ID counter
_id_counter = itertools.count(1)
_id_lock = threading.Lock()


class Entity:
    """
    Base class for every object in the simulation.

    Attributes:
        id:       Unique identifier
        x, y:     Grid position
        energy:   Current energy level (0 = dead)
        age:      Ticks since birth
        alive:    Whether this entity is still active
        entity_type: High-level classification
    """

    __slots__ = ("id", "x", "y", "energy", "max_energy", "age", "alive", "entity_type")

    def __init__(
        self,
        x: int,
        y: int,
        energy: float = 100.0,
        max_energy: float = 100.0,
        entity_type: EntityType = EntityType.FLORA,
    ) -> None:
        with _id_lock:
            self.id: int = next(_id_counter)
        self.x = x
        self.y = y
        self.energy = energy
        self.max_energy = max_energy
        self.age = 0
        self.alive = True
        self.entity_type = entity_type

    def update(self, world) -> None:
        """Called each tick. Override in subclasses."""
        self.age += 1

    def die(self) -> None:
        """Mark this entity as dead."""
        self.alive = False
        self.energy = 0

    def distance_to(self, other: Entity) -> float:
        """Euclidean distance to another entity."""
        return math.hypot(self.x - other.x, self.y - other.y)

    def clamp_energy(self) -> None:
        """Clamp energy to [0, max_energy]."""
        self.energy = max(0.0, min(self.energy, self.max_energy))
        if self.energy <= 0:
            self.die()

    def to_dict(self) -> dict:
        """Serialize for WebSocket broadcast."""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "energy": round(float(self.energy), 1),
            "age": self.age,
            "type": self.entity_type.name,
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} #{self.id} ({self.x},{self.y}) E={self.energy:.0f}>"
