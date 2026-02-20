"""Statistics tracker and emergent behavior analysis."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from .entity import EntityType

if TYPE_CHECKING:
    from .world import World


class StatsTracker:
    """
    Records per-tick simulation data and detects emergent patterns.

    Tracks:
      - Population counts by species
      - Average energy and genetic traits
      - Birth/death rates
      - Biodiversity index
      - Emergent behavior signals (clustering, oscillations)
    """

    def __init__(self, history_length: int = 500) -> None:
        self.history_length = history_length

        # Population histories
        self.herbivore_pop: deque[int] = deque(maxlen=history_length)
        self.predator_pop: deque[int] = deque(maxlen=history_length)
        self.omnivore_pop: deque[int] = deque(maxlen=history_length)
        self.flora_pop: deque[int] = deque(maxlen=history_length)

        # Energy histories
        self.avg_energy: deque[float] = deque(maxlen=history_length)

        # Trait averages
        self.avg_speed: deque[float] = deque(maxlen=history_length)
        self.avg_vision: deque[float] = deque(maxlen=history_length)
        self.avg_size: deque[float] = deque(maxlen=history_length)

        # Birth/death counts per tick
        self.births: deque[int] = deque(maxlen=history_length)
        self.deaths: deque[int] = deque(maxlen=history_length)

        # Running totals
        self.total_births = 0
        self.total_deaths = 0
        self.peak_population = 0
        self.ticks_recorded = 0

        # Last snapshot cache
        self._last_snapshot: dict = {}

    def record(self, world: World) -> None:
        """Record one tick of data."""
        self.ticks_recorded += 1

        herbs = preds = omnis = flora_count = 0
        energies = []
        speeds = []
        visions = []
        sizes = []

        for e in world.entities:
            if not e.alive:
                continue
            if e.entity_type == EntityType.FLORA:
                flora_count += 1
            elif e.entity_type == EntityType.HERBIVORE:
                herbs += 1
            elif e.entity_type == EntityType.PREDATOR:
                preds += 1
            elif e.entity_type == EntityType.OMNIVORE:
                omnis += 1

            if e.entity_type != EntityType.FLORA:
                energies.append(e.energy)
                if hasattr(e, 'genetics'):
                    speeds.append(e.genetics.speed)
                    visions.append(e.genetics.vision_range)
                    sizes.append(e.genetics.size)

        self.herbivore_pop.append(herbs)
        self.predator_pop.append(preds)
        self.omnivore_pop.append(omnis)
        self.flora_pop.append(flora_count)
        self.avg_energy.append(sum(energies) / max(1, len(energies)))
        self.avg_speed.append(sum(speeds) / max(1, len(speeds)))
        self.avg_vision.append(sum(visions) / max(1, len(visions)))
        self.avg_size.append(sum(sizes) / max(1, len(sizes)))

        # Births/deaths from queues
        birth_count = len(world._births)
        death_count = len(world._deaths)
        self.births.append(birth_count)
        self.deaths.append(death_count)
        self.total_births += birth_count
        self.total_deaths += death_count

        total_pop = herbs + preds + omnis
        if total_pop > self.peak_population:
            self.peak_population = total_pop

        # Cache snapshot
        self._last_snapshot = self._build_snapshot(
            herbs, preds, omnis, flora_count, energies, speeds, visions, sizes
        )

    def _build_snapshot(
        self,
        herbs: int, preds: int, omnis: int, flora: int,
        energies: list, speeds: list, visions: list, sizes: list,
    ) -> dict:
        """Build a JSON-serializable snapshot."""
        total_fauna = herbs + preds + omnis
        biodiversity = self._biodiversity_index(herbs, preds, omnis)

        return {
            "population": {
                "herbivores": herbs,
                "predators": preds,
                "omnivores": omnis,
                "flora": flora,
                "total_fauna": total_fauna,
            },
            "averages": {
                "energy": round(sum(energies) / max(1, len(energies)), 1),
                "speed": round(sum(speeds) / max(1, len(speeds)), 2),
                "vision": round(sum(visions) / max(1, len(visions)), 1),
                "size": round(sum(sizes) / max(1, len(sizes)), 2),
            },
            "biodiversity": round(biodiversity, 3),
            "totals": {
                "births": self.total_births,
                "deaths": self.total_deaths,
                "peak_population": self.peak_population,
            },
            "history": {
                "herbivores": list(self.herbivore_pop)[-50:],
                "predators": list(self.predator_pop)[-50:],
                "omnivores": list(self.omnivore_pop)[-50:],
                "flora": list(self.flora_pop)[-50:],
                "energy": [round(e, 1) for e in list(self.avg_energy)[-50:]],
            },
        }

    def _biodiversity_index(self, herbs: int, preds: int, omnis: int) -> float:
        """
        Shannon diversity index across fauna species.

        Higher = more diverse, 0 = only one species.
        """
        import math
        total = herbs + preds + omnis
        if total == 0:
            return 0.0

        index = 0.0
        for count in (herbs, preds, omnis):
            if count > 0:
                p = count / total
                index -= p * math.log(p)
        return index

    def current_snapshot(self) -> dict:
        """Return the last recorded snapshot."""
        return self._last_snapshot

    def summary_string(self) -> str:
        """Human-readable summary of current state."""
        s = self._last_snapshot
        if not s:
            return "No data yet."
        pop = s["population"]
        avg = s["averages"]
        return (
            f"🌿 Flora: {pop['flora']}  |  "
            f"🐇 Herb: {pop['herbivores']}  |  "
            f"🐺 Pred: {pop['predators']}  |  "
            f"🦊 Omni: {pop['omnivores']}  |  "
            f"⚡ Avg Energy: {avg['energy']}  |  "
            f"🧬 Biodiversity: {s['biodiversity']}"
        )
