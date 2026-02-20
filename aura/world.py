"""World simulation engine — the beating heart of AURA."""

from __future__ import annotations

import random
import time
from enum import Enum, auto
from typing import TYPE_CHECKING

import numpy as np
from rich.console import Console

from .config import AuraConfig
from .entity import Entity, EntityType

if TYPE_CHECKING:
    from .stats import StatsTracker

console = Console()


class Season(Enum):
    SPRING = auto()
    SUMMER = auto()
    AUTUMN = auto()
    WINTER = auto()

    @property
    def growth_modifier(self) -> float:
        return {
            Season.SPRING: 1.5,
            Season.SUMMER: 1.0,
            Season.AUTUMN: 0.6,
            Season.WINTER: 0.2,
        }[self]

    @property
    def label(self) -> str:
        return self.name.capitalize()


class TimeOfDay(Enum):
    DAWN = auto()
    DAY = auto()
    DUSK = auto()
    NIGHT = auto()

    @property
    def activity_modifier(self) -> float:
        return {
            TimeOfDay.DAWN: 0.8,
            TimeOfDay.DAY: 1.0,
            TimeOfDay.DUSK: 0.7,
            TimeOfDay.NIGHT: 0.3,
        }[self]


class ActiveEvent:
    """An environmental event currently in effect."""

    def __init__(self, name: str, duration: int, modifier: float) -> None:
        self.name = name
        self.remaining = duration
        self.modifier = modifier

    def tick(self) -> bool:
        """Advance one tick. Returns True if still active."""
        self.remaining -= 1
        return self.remaining > 0


class World:
    """
    The 2D grid world that owns all entities and drives the tick loop.

    Features:
        - Spatial grid for O(1) neighbor lookups
        - Day/night cycle and seasonal progression
        - Soil nutrient layer that flora consumes and fauna replenishes
        - Environmental event system (rain, drought, storm)
    """

    def __init__(self, config: AuraConfig) -> None:
        self.config = config
        self.width = config.world.width
        self.height = config.world.height

        # Tick state
        self.tick_count = 0
        self.running = False

        # Entity storage
        self.entities: list[Entity] = []
        self._spatial: dict[tuple[int, int], list[Entity]] = {}

        # Environment layers
        self.soil_nutrients: np.ndarray = np.ones((self.height, self.width), dtype=np.float32)

        # Time systems
        self.season = Season.SPRING
        self.time_of_day = TimeOfDay.DAY

        # Active events
        self.active_events: list[ActiveEvent] = []

        # Stats tracker (injected later)
        self.stats: StatsTracker | None = None

        # Birth/death queues (processed at end of each tick)
        self._births: list[Entity] = []
        self._deaths: list[Entity] = []

    # ── Entity management ──────────────────────────────────────

    def add_entity(self, entity: Entity) -> None:
        """Add an entity to the world."""
        entity.x = max(0, min(entity.x, self.width - 1))
        entity.y = max(0, min(entity.y, self.height - 1))
        self.entities.append(entity)
        self._spatial.setdefault((entity.x, entity.y), []).append(entity)

    def remove_entity(self, entity: Entity) -> None:
        """Remove a dead entity from the world."""
        if entity in self.entities:
            self.entities.remove(entity)
        cell = self._spatial.get((entity.x, entity.y), [])
        if entity in cell:
            cell.remove(entity)

    def queue_birth(self, entity: Entity) -> None:
        """Queue a new entity to be added at end of tick."""
        self._births.append(entity)

    def queue_death(self, entity: Entity) -> None:
        """Queue an entity for removal at end of tick."""
        self._deaths.append(entity)

    def move_entity(self, entity: Entity, new_x: int, new_y: int) -> None:
        """Move an entity to a new position with wrapping."""
        # Remove from old cell
        old_cell = self._spatial.get((entity.x, entity.y), [])
        if entity in old_cell:
            old_cell.remove(entity)

        # Wrap around edges (toroidal world)
        entity.x = new_x % self.width
        entity.y = new_y % self.height

        # Add to new cell
        self._spatial.setdefault((entity.x, entity.y), []).append(entity)

    def get_neighbors(self, x: int, y: int, radius: int, entity_type: EntityType | None = None) -> list[Entity]:
        """Get all entities within a radius of (x, y)."""
        results = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue
                nx = (x + dx) % self.width
                ny = (y + dy) % self.height
                for e in self._spatial.get((nx, ny), []):
                    if e.alive and (entity_type is None or e.entity_type == entity_type):
                        dist = (dx * dx + dy * dy) ** 0.5
                        if dist <= radius:
                            results.append(e)
        return results

    def random_position(self) -> tuple[int, int]:
        """Return a random (x, y) position on the grid."""
        return random.randint(0, self.width - 1), random.randint(0, self.height - 1)

    def flora_count(self) -> int:
        return sum(1 for e in self.entities if e.alive and e.entity_type == EntityType.FLORA)

    def fauna_count(self) -> int:
        return sum(1 for e in self.entities if e.alive and e.entity_type != EntityType.FLORA)

    # ── Time systems ───────────────────────────────────────────

    def _update_time(self) -> None:
        """Update day/night cycle and seasons."""
        day_len = self.config.world.day_length
        season_len = self.config.world.season_length

        # Day/night
        day_progress = (self.tick_count % day_len) / day_len
        if day_progress < 0.2:
            self.time_of_day = TimeOfDay.DAWN
        elif day_progress < 0.6:
            self.time_of_day = TimeOfDay.DAY
        elif day_progress < 0.8:
            self.time_of_day = TimeOfDay.DUSK
        else:
            self.time_of_day = TimeOfDay.NIGHT

        # Seasons
        seasons = list(Season)
        season_idx = (self.tick_count // season_len) % len(seasons)
        self.season = seasons[season_idx]

    def _update_events(self) -> None:
        """Tick active events and potentially spawn new ones."""
        # Tick existing
        self.active_events = [ev for ev in self.active_events if ev.tick()]

        # Spawn new events
        eco = self.config.ecosystem
        if random.random() < eco.rain_probability:
            self.active_events.append(ActiveEvent("Rain", duration=30, modifier=eco.rain_boost))
        if random.random() < eco.drought_probability:
            self.active_events.append(ActiveEvent("Drought", duration=50, modifier=eco.drought_penalty))
        if random.random() < eco.storm_probability:
            self.active_events.append(ActiveEvent("Storm", duration=10, modifier=0.0))

    def _update_nutrients(self) -> None:
        """Slowly recover soil nutrients."""
        recovery = self.config.ecosystem.nutrient_recovery_rate
        self.soil_nutrients = np.minimum(1.0, self.soil_nutrients + recovery)

    @property
    def growth_modifier(self) -> float:
        """Combined growth modifier from season + events."""
        mod = self.season.growth_modifier
        for ev in self.active_events:
            if ev.name == "Rain":
                mod *= ev.modifier
            elif ev.name == "Drought":
                mod *= ev.modifier
        return mod

    # ── Storm damage ───────────────────────────────────────────

    def _apply_storm_damage(self) -> None:
        """Storms randomly damage fauna."""
        for ev in self.active_events:
            if ev.name == "Storm":
                for entity in self.entities:
                    if entity.alive and entity.entity_type != EntityType.FLORA:
                        if random.random() < 0.05:
                            entity.energy -= 20
                            entity.clamp_energy()

    # ── Main tick ──────────────────────────────────────────────

    def tick(self) -> None:
        """Advance the simulation by one tick."""
        self.tick_count += 1
        self._update_time()
        self._update_events()
        self._update_nutrients()
        self._apply_storm_damage()

        # Update all entities (flora first, then fauna)
        flora = [e for e in self.entities if e.alive and e.entity_type == EntityType.FLORA]
        fauna = [e for e in self.entities if e.alive and e.entity_type != EntityType.FLORA]

        for entity in flora:
            entity.update(self)

        # Shuffle fauna to avoid order bias
        random.shuffle(fauna)
        for entity in fauna:
            entity.update(self)

        # Process births and deaths
        for entity in self._deaths:
            # Fauna death adds nutrients back to soil
            if entity.entity_type != EntityType.FLORA:
                self.soil_nutrients[entity.y, entity.x] = min(
                    1.0, self.soil_nutrients[entity.y, entity.x] + 0.2
                )
            entity.die()
            self.remove_entity(entity)
        self._deaths.clear()

        for entity in self._births:
            self.add_entity(entity)
        self._births.clear()

        # Remove dead entities that died during update
        dead = [e for e in self.entities if not e.alive]
        for e in dead:
            self.remove_entity(e)

        # Record stats
        if self.stats:
            self.stats.record(self)

    def run(self, max_ticks: int = 0) -> None:
        """Run the simulation loop."""
        self.running = True
        tick_count = 0
        try:
            while self.running:
                start = time.time()
                self.tick()
                tick_count += 1

                if max_ticks > 0 and tick_count >= max_ticks:
                    break

                # Throttle
                elapsed = time.time() - start
                sleep_time = self.config.world.tick_speed - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]⚡ Simulation stopped.[/bold yellow]")
        finally:
            self.running = False

    def to_dict(self) -> dict:
        """Serialize the full world state for WebSocket broadcast."""
        return {
            "tick": self.tick_count,
            "width": self.width,
            "height": self.height,
            "season": self.season.label,
            "time_of_day": self.time_of_day.name,
            "events": [ev.name for ev in self.active_events],
            "growth_modifier": round(self.growth_modifier, 2),
            "entities": [e.to_dict() for e in self.entities if e.alive],
            "stats": self.stats.current_snapshot() if self.stats else {},
        }
