"""Fauna — intelligent agents that perceive, decide, and act."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from .brain import Brain, NUM_INPUTS
from .entity import Entity, EntityType

if TYPE_CHECKING:
    from .world import World


# ── Genetics ───────────────────────────────────────────────────

@dataclass
class Genetics:
    """Heritable traits that define a creature's physical capabilities."""
    speed: float = 1.0
    vision_range: float = 6.0
    size: float = 1.0
    metabolism: float = 1.0       # multiplier on energy cost
    reproduction_age: int = 50    # min age to reproduce

    def mutate(self, rate: float = 0.1) -> Genetics:
        """Create a mutated copy."""
        return Genetics(
            speed=max(0.3, self.speed + random.gauss(0, rate * 0.3)),
            vision_range=max(2, self.vision_range + random.gauss(0, rate * 1.0)),
            size=max(0.3, self.size + random.gauss(0, rate * 0.2)),
            metabolism=max(0.3, self.metabolism + random.gauss(0, rate * 0.1)),
            reproduction_age=max(20, int(self.reproduction_age + random.gauss(0, rate * 5))),
        )


# ── Fauna Agent ────────────────────────────────────────────────

class Fauna(Entity):
    """
    An intelligent creature in the AURA ecosystem.

    Each Fauna has:
      - A Brain (neural net) for decision making
      - Genetics (inherited physical traits)
      - Needs (hunger, fear, curiosity)
      - A species type (Herbivore, Predator, Omnivore)
    """

    __slots__ = (
        "brain", "genetics", "hunger", "fear", "curiosity",
        "species", "generation", "children_count",
        "_last_action", "_cooldown",
    )

    def __init__(
        self,
        x: int,
        y: int,
        species: EntityType,
        brain: Brain | None = None,
        genetics: Genetics | None = None,
        generation: int = 0,
    ) -> None:
        super().__init__(x, y, energy=80.0, max_energy=100.0, entity_type=species)
        self.brain = brain or Brain()
        self.genetics = genetics or Genetics()
        self.species = species
        self.generation = generation
        self.children_count = 0

        # Needs (0 - 100)
        self.hunger: float = 30.0
        self.fear: float = 0.0
        self.curiosity: float = 50.0

        # State
        self._last_action: str = "rest"
        self._cooldown: int = 0

    # ── Sensory system ─────────────────────────────────────────

    def _perceive(self, world: World) -> dict:
        """Scan the environment and build a perception map."""
        vision = int(self.genetics.vision_range)

        nearby_flora = world.get_neighbors(self.x, self.y, vision, EntityType.FLORA)
        nearby_herbivores = world.get_neighbors(self.x, self.y, vision, EntityType.HERBIVORE)
        nearby_predators = world.get_neighbors(self.x, self.y, vision, EntityType.PREDATOR)
        nearby_omnivores = world.get_neighbors(self.x, self.y, vision, EntityType.OMNIVORE)

        # Nearest of each relevant type
        nearest_food = self._nearest(nearby_flora) if self.species != EntityType.PREDATOR else self._nearest(nearby_herbivores)
        nearest_predator = self._nearest(nearby_predators) if self.species == EntityType.HERBIVORE else None
        nearest_prey = None
        if self.species == EntityType.PREDATOR:
            nearest_prey = self._nearest(nearby_herbivores + nearby_omnivores)
        elif self.species == EntityType.OMNIVORE:
            nearest_prey = self._nearest(nearby_herbivores)

        # Find potential mates (same species, both mature)
        same_species = [e for e in (nearby_herbivores + nearby_predators + nearby_omnivores)
                        if e.entity_type == self.species and e is not self and e.age >= self.genetics.reproduction_age]
        nearest_mate = self._nearest(same_species)

        # Crowding factor
        all_nearby = nearby_herbivores + nearby_predators + nearby_omnivores
        crowding = min(1.0, len(all_nearby) / max(1, vision * 2))

        return {
            "nearest_food": nearest_food,
            "nearest_predator": nearest_predator,
            "nearest_prey": nearest_prey,
            "nearest_mate": nearest_mate,
            "nearby_flora": nearby_flora,
            "crowding": crowding,
        }

    def _nearest(self, entities: list[Entity]) -> Entity | None:
        """Return the nearest entity from a list."""
        if not entities:
            return None
        return min(entities, key=lambda e: self.distance_to(e))

    def _build_inputs(self, perception: dict, world: World) -> np.ndarray:
        """Convert perception into neural net input vector."""
        vision = self.genetics.vision_range

        # Normalize distances to [0, 1] (1 = far/absent)
        food_dist = self.distance_to(perception["nearest_food"]) / vision if perception["nearest_food"] else 1.0
        pred_dist = self.distance_to(perception["nearest_predator"]) / vision if perception["nearest_predator"] else 1.0
        mate_dist = self.distance_to(perception["nearest_mate"]) / vision if perception["nearest_mate"] else 1.0

        # Time of day as 0-1
        time_val = (world.tick_count % world.config.world.day_length) / world.config.world.day_length

        inputs = np.array([
            self.hunger / 100.0,
            self.energy / self.max_energy,
            self.fear / 100.0,
            min(1.0, food_dist),
            min(1.0, pred_dist),
            min(1.0, mate_dist),
            time_val,
            perception["crowding"],
        ], dtype=np.float32)

        return inputs

    # ── Action system ──────────────────────────────────────────

    def update(self, world: World) -> None:
        """One tick of life: perceive → decide → act → age."""
        self.age += 1
        if self._cooldown > 0:
            self._cooldown -= 1

        # Metabolism: energy drains each tick
        energy_cost = abs(world.config.fauna.energy_per_tick) * self.genetics.metabolism
        self.energy -= energy_cost
        self.hunger = min(100.0, self.hunger + 0.5 * self.genetics.metabolism)

        # Fear decays over time
        self.fear = max(0, self.fear - 1.0)

        # Check death by starvation or old age
        if self.energy <= 0 or self.age > world.config.fauna.max_age:
            world.queue_death(self)
            return

        # Perceive
        perception = self._perceive(world)

        # Decide
        inputs = self._build_inputs(perception, world)
        action = self.brain.decide(inputs)

        # Override: force flee if predator very close and we're prey
        if perception["nearest_predator"] and self.species == EntityType.HERBIVORE:
            if self.distance_to(perception["nearest_predator"]) < 2:
                action = "flee"
                self.fear = min(100, self.fear + 30)

        # Act
        self._execute_action(action, perception, world)
        self._last_action = action
        self.clamp_energy()

    def _execute_action(self, action: str, perception: dict, world: World) -> None:
        """Execute the chosen action."""
        if action == "wander":
            self._wander(world)
        elif action == "forage":
            self._forage(perception, world)
        elif action == "flee":
            self._flee(perception, world)
        elif action == "chase":
            self._chase(perception, world)
        elif action == "reproduce":
            self._reproduce(perception, world)
        elif action == "rest":
            self._rest()

    def _wander(self, world: World) -> None:
        """Move in a random direction."""
        dx = random.choice([-1, 0, 1])
        dy = random.choice([-1, 0, 1])
        speed = int(max(1, self.genetics.speed))
        world.move_entity(self, self.x + dx * speed, self.y + dy * speed)
        self.energy -= 0.1 * self.genetics.speed
        self.curiosity = max(0, self.curiosity - 1)

    def _forage(self, perception: dict, world: World) -> None:
        """Move toward food and eat it if close enough."""
        target = perception.get("nearest_food")

        if self.species == EntityType.PREDATOR:
            # Predators "forage" by chasing prey
            self._chase(perception, world)
            return

        if target and target.alive:
            if self.distance_to(target) <= 1.5:
                # Eat it
                cfg = world.config.fauna
                if self.species == EntityType.HERBIVORE:
                    gained = cfg.herbivore.energy_from_flora
                else:
                    gained = cfg.omnivore.energy_from_flora

                self.energy += gained
                self.hunger = max(0, self.hunger - 30)
                world.queue_death(target)
            else:
                # Move toward it
                self._move_toward(target, world)
        else:
            self._wander(world)

    def _flee(self, perception: dict, world: World) -> None:
        """Run away from the nearest predator."""
        threat = perception.get("nearest_predator")
        if threat:
            # Move in opposite direction
            dx = self.x - threat.x
            dy = self.y - threat.y
            # Normalize
            dist = max(1, (dx ** 2 + dy ** 2) ** 0.5)
            speed = int(max(1, self.genetics.speed * 1.3))  # adrenaline boost
            new_x = self.x + int(dx / dist * speed)
            new_y = self.y + int(dy / dist * speed)
            world.move_entity(self, new_x, new_y)
            self.energy -= 0.3 * self.genetics.speed  # fleeing is costly
            self.fear = min(100, self.fear + 10)
        else:
            self._wander(world)

    def _chase(self, perception: dict, world: World) -> None:
        """Pursue and attempt to catch prey."""
        prey = perception.get("nearest_prey")
        if not prey or not prey.alive:
            self._wander(world)
            return

        if self.distance_to(prey) <= 1.5:
            # Attempt to catch
            cfg = world.config.fauna
            if self.species == EntityType.PREDATOR:
                success_rate = cfg.predator.hunt_success_rate
                gained = cfg.predator.energy_from_prey
            else:
                success_rate = cfg.omnivore.hunt_success_rate
                gained = cfg.omnivore.energy_from_prey

            # Size advantage
            if hasattr(prey, 'genetics'):
                size_ratio = self.genetics.size / max(0.1, prey.genetics.size)
                success_rate *= min(2.0, size_ratio)

            if random.random() < success_rate:
                self.energy += gained
                self.hunger = max(0, self.hunger - 50)
                world.queue_death(prey)
            else:
                self.energy -= 2.0  # failed hunt costs energy
        else:
            self._move_toward(prey, world)

    def _reproduce(self, perception: dict, world: World) -> None:
        """Create an offspring if conditions are met."""
        if self._cooldown > 0:
            self._wander(world)
            return

        cfg = world.config.fauna
        if (self.energy < cfg.reproduction_threshold or
                self.age < self.genetics.reproduction_age):
            self._wander(world)
            return

        mate = perception.get("nearest_mate")
        if mate and self.distance_to(mate) <= 2.0 and hasattr(mate, 'brain'):
            # Create offspring
            child_brain = Brain.crossover(self.brain, mate.brain).mutate(cfg.mutation_rate)
            child_genetics = self.genetics.mutate(cfg.mutation_rate)

            # Spawn near parent
            cx = self.x + random.choice([-1, 0, 1])
            cy = self.y + random.choice([-1, 0, 1])

            child = Fauna(
                x=cx, y=cy,
                species=self.species,
                brain=child_brain,
                genetics=child_genetics,
                generation=self.generation + 1,
            )
            child.energy = 50.0

            world.queue_birth(child)
            self.energy -= cfg.reproduction_cost
            self.children_count += 1
            self._cooldown = 30  # can't reproduce again for 30 ticks
        elif mate:
            self._move_toward(mate, world)
        else:
            self._wander(world)

    def _rest(self) -> None:
        """Stay still and recover a bit of energy."""
        self.energy += 0.5
        self.hunger = min(100, self.hunger + 0.2)

    # ── Movement helpers ───────────────────────────────────────

    def _move_toward(self, target: Entity, world: World) -> None:
        """Move one step toward a target entity."""
        dx = target.x - self.x
        dy = target.y - self.y
        dist = max(1, (dx ** 2 + dy ** 2) ** 0.5)
        speed = int(max(1, self.genetics.speed))
        new_x = self.x + int(dx / dist * speed)
        new_y = self.y + int(dy / dist * speed)
        world.move_entity(self, new_x, new_y)
        self.energy -= 0.15 * self.genetics.speed

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict:
        """Extended serialization with fauna-specific data."""
        base = super().to_dict()
        base.update({
            "species": self.species.name,
            "hunger": round(float(self.hunger), 1),
            "fear": round(float(self.fear), 1),
            "generation": self.generation,
            "action": self._last_action,
            "speed": round(float(self.genetics.speed), 2),
            "vision": round(float(self.genetics.vision_range), 1),
            "size": round(float(self.genetics.size), 2),
        })
        return base
