"""Flora — dynamic, context-aware plant life in the AURA world."""

from __future__ import annotations

import random
from enum import Enum, auto
from typing import TYPE_CHECKING

from .entity import Entity, EntityType, GrowthStage

if TYPE_CHECKING:
    from .world import World


class FloraType(Enum):
    """Species of flora."""
    GRASS = auto()
    BUSH = auto()
    TREE = auto()


class Flora(Entity):
    """
    A plant entity that grows, spreads, and responds to the environment.

    Flora is context-aware:
      - Growth rate affected by season, soil nutrients, nearby crowding
      - Spreading probability increases when mature
      - Dies of old age or when consumed by fauna
    """

    __slots__ = ("flora_type", "growth_stage", "growth_progress", "_energy_value", "_max_age", "_growth_ticks")

    def __init__(
        self,
        x: int,
        y: int,
        flora_type: FloraType = FloraType.GRASS,
        growth_stage: GrowthStage = GrowthStage.SEED,
    ) -> None:
        super().__init__(x, y, energy=10.0, max_energy=100.0, entity_type=EntityType.FLORA)
        self.flora_type = flora_type
        self.growth_stage = growth_stage
        self.growth_progress: float = 0.0

        # These will be set from config during placement
        self._energy_value: float = 10.0
        self._max_age: int = 200
        self._growth_ticks: int = 20

    @classmethod
    def create(cls, x: int, y: int, flora_type: FloraType, world: World) -> Flora:
        """Factory method that creates a Flora and configures it from world config."""
        plant = cls(x, y, flora_type)
        cfg = world.config.flora

        if flora_type == FloraType.GRASS:
            plant._energy_value = cfg.grass.energy
            plant._growth_ticks = cfg.grass.growth_ticks
            plant._max_age = cfg.grass.max_age
        elif flora_type == FloraType.BUSH:
            plant._energy_value = cfg.bush.energy
            plant._growth_ticks = cfg.bush.growth_ticks
            plant._max_age = cfg.bush.max_age
        elif flora_type == FloraType.TREE:
            plant._energy_value = cfg.tree.energy
            plant._growth_ticks = cfg.tree.growth_ticks
            plant._max_age = cfg.tree.max_age

        plant.energy = plant._energy_value
        return plant

    # ── Growth system ──────────────────────────────────────────

    def update(self, world: World) -> None:
        """Grow, age, and possibly spread."""
        self.age += 1

        # Death check
        if self.age > self._max_age:
            self.growth_stage = GrowthStage.DECAYING
            self.energy -= 2.0
            if self.energy <= 0:
                world.queue_death(self)
                # Return nutrients to soil
                world.soil_nutrients[self.y, self.x] = min(
                    1.0, world.soil_nutrients[self.y, self.x] + 0.15
                )
            return

        # Growth progression
        growth_rate = self._calculate_growth_rate(world)
        self.growth_progress += growth_rate

        # Stage transitions
        if self.growth_stage == GrowthStage.SEED and self.growth_progress >= self._growth_ticks * 0.3:
            self.growth_stage = GrowthStage.SPROUT
        elif self.growth_stage == GrowthStage.SPROUT and self.growth_progress >= self._growth_ticks:
            self.growth_stage = GrowthStage.MATURE
            self.energy = self._energy_value  # full energy when mature

        # Mature plants can spread
        if self.growth_stage == GrowthStage.MATURE:
            self._try_spread(world)

        # Consume soil nutrients
        nutrient = world.soil_nutrients[self.y, self.x]
        if nutrient > 0.05:
            world.soil_nutrients[self.y, self.x] -= 0.005

    def _calculate_growth_rate(self, world: World) -> float:
        """Context-aware growth rate."""
        base_rate = world.config.flora.growth_rate

        # Season modifier
        rate = base_rate * world.growth_modifier

        # Soil nutrient modifier
        nutrient = world.soil_nutrients[self.y, self.x]
        rate *= max(0.1, nutrient)

        # Crowding penalty: too many plants nearby slows growth
        nearby = world.get_neighbors(self.x, self.y, 2, EntityType.FLORA)
        if len(nearby) > 4:
            rate *= 0.5
        elif len(nearby) > 6:
            rate *= 0.2

        return rate

    def _try_spread(self, world: World) -> None:
        """Attempt to plant a seed in an adjacent cell."""
        cfg = world.config.flora

        # Check density cap
        total_cells = world.width * world.height
        current_flora = world.flora_count()
        if current_flora / total_cells >= cfg.max_density:
            return

        # Probability check
        spread_chance = cfg.spread_probability * world.growth_modifier
        if random.random() > spread_chance:
            return

        # Find an empty adjacent cell
        directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        random.shuffle(directions)

        for dx, dy in directions:
            nx = (self.x + dx) % world.width
            ny = (self.y + dy) % world.height

            # Check if cell is relatively empty
            occupants = world.get_neighbors(nx, ny, 0, EntityType.FLORA)
            if len(occupants) < 2:
                seed = Flora.create(nx, ny, self.flora_type, world)
                seed.growth_stage = GrowthStage.SEED
                seed.growth_progress = 0
                seed.energy = self._energy_value * 0.3  # seeds have partial energy
                world.queue_birth(seed)
                return

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict:
        """Extended serialization with flora-specific data."""
        base = super().to_dict()
        base.update({
            "flora_type": self.flora_type.name,
            "stage": self.growth_stage.name,
            "growth": round(float(self.growth_progress), 1),
        })
        return base
