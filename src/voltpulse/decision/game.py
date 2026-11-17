"""Two storage operators learning from their own realized payoffs.

This is a repeated toy market, not a market-clearing engine. The daily
schedule is price-blind. Only the selected action's value is updated.
"""

from dataclasses import asdict, dataclass
import math
import random
from typing import Sequence


ACTION_LEVELS = (0.0, 0.5, 1.0)
ACTION_LABELS = ("观望", "适中", "积极")


@dataclass(frozen=True)
class StorageSpec:
    power_mw: float = 100.0
    energy_mwh: float = 200.0
    efficiency: float = 0.85  # round-trip efficiency
    degradation_rmb_mwh: float = 30.0  # cell-side throughput
    soc_min: float = 0.1
    soc_max: float = 0.9
    soc_initial: float = 0.5

    def __post_init__(self):
        if not all(math.isfinite(v) for v in asdict(self).values()):
            raise ValueError("Storage parameters must be finite")
        if self.power_mw <= 0 or self.energy_mwh <= 0:
            raise ValueError("Power and capacity must be positive")
        if not 0 < self.efficiency <= 1 or self.degradation_rmb_mwh < 0:
            raise ValueError("Invalid efficiency or degradation cost")
        if not 0 <= self.soc_min <= self.soc_initial < self.soc_max <= 1:
            raise ValueError("Invalid SOC bounds")


@dataclass(frozen=True)
class GameConfig:
    rounds: int = 120
    learning_rate: float = 0.2
    price_impact: float = 1.5  # (RMB/MWh) per MW of net demand
    temperature: float = 0.2
    reward_scale_rmb: float = 50000.0
    seed: int = 17

    def __post_init__(self):
        if isinstance(self.rounds, bool) or not isinstance(self.rounds, int) or not 1 <= self.rounds <= 10000:
            raise ValueError("Rounds must be an integer from 1 to 10000")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("Seed must be an integer")
        if not all(math.isfinite(v) for v in (self.learning_rate, self.price_impact, self.temperature, self.reward_scale_rmb)):
            raise ValueError("Game parameters must be finite")
        if not 0 < self.learning_rate <= 1 or self.price_impact < 0:
            raise ValueError("Invalid learning rate or price impact")
        if self.temperature <= 0 or self.reward_scale_rmb <= 0:
            raise ValueError("Temperature and reward scale must be positive")


def build_schedule(spec: StorageSpec, intensity: float = 1.0) -> dict:
    """15-minute AC schedule: charge 11-15, discharge 18-22, restore SOC.

    Scale a feasible cyclic schedule; no price or opponent information is used.
    Positive net_power denotes grid demand, negative denotes grid injection.
    """
    if not math.isfinite(intensity) or not 0 <= intensity <= 1:
        raise ValueError("Intensity must lie in [0, 1]")
    eta, dt = math.sqrt(spec.efficiency), 0.25
    start = spec.energy_mwh * spec.soc_initial
    energy, charge, discharge = start, [], []
    for t in range(96):
        pc = pd = 0.0
        if 44 <= t < 60:
            pc = min(spec.power_mw, max(0.0, (spec.energy_mwh * spec.soc_max - energy) / (eta * dt)))
        elif 72 <= t < 88:
            pd = min(spec.power_mw, max(0.0, (energy - start) * eta / dt))
        energy += (eta * pc - pd / eta) * dt
        charge.append(pc * intensity)
        discharge.append(pd * intensity)
    if abs(energy - start) > 1e-7:
        raise ValueError("Storage cannot close its daily SOC in the configured windows")
    trajectory, energy = [], start
    for pc, pd in zip(charge, discharge):
        energy += (eta * pc - pd / eta) * dt
        trajectory.append(energy / spec.energy_mwh)
    throughput = sum((eta * pc + pd / eta) * dt for pc, pd in zip(charge, discharge))
    return {"charge_mw": charge, "discharge_mw": discharge,
            "net_power_mw": [pc - pd for pc, pd in zip(charge, discharge)],
            "soc": trajectory, "degradation_rmb": throughput * spec.degradation_rmb_mwh}


def settle_round(base_prices: Sequence[float], schedules: Sequence[dict], price_impact: float) -> dict:
    if len(base_prices) != 96 or not all(math.isfinite(float(p)) for p in base_prices):
        raise ValueError("Expected 96 finite base prices")
    if not math.isfinite(price_impact) or price_impact < 0 or len(schedules) != 2:
        raise ValueError("Expected two schedules and nonnegative finite price impact")
    # Shared price feedback creates strategic interaction between operators.
    prices = [float(base_prices[t]) + price_impact * sum(s["net_power_mw"][t] for s in schedules) for t in range(96)]
    profits = [-0.25 * sum(p * n for p, n in zip(prices, s["net_power_mw"])) - s["degradation_rmb"] for s in schedules]
    return {"prices": prices, "profits": profits}


def choice_probabilities(values: Sequence[float], temperature: float) -> list:
    if len(values) != len(ACTION_LEVELS) or not all(math.isfinite(v) for v in values):
        raise ValueError("Expected three finite action values")
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("Temperature must be finite and positive")
    best = max(values)
    weights = [math.exp((v - best) / temperature) for v in values]
    return [w / sum(weights) for w in weights]


def update_value(values: Sequence[float], action: int, payoff: float, config: GameConfig) -> list:
    """Update only an observed payoff; unchosen actions are not revealed."""
    result = list(values)
    result[action] += config.learning_rate * (payoff / config.reward_scale_rmb - result[action])
    return result


def simulate_game(price_days: Sequence[Sequence[float]], config: GameConfig = None,
                  specs: Sequence[StorageSpec] = None) -> dict:
    config = config or GameConfig()
    specs = tuple(specs) if specs is not None else (StorageSpec(), StorageSpec(80, 160, 0.9, 45))
    if len(specs) != 2 or not price_days:
        raise ValueError("Expected two storage operators and at least one price day")
    days = [[float(p) for p in day] for day in price_days]
    if any(len(day) != 96 or not all(math.isfinite(p) for p in day) for day in days):
        raise ValueError("Every price day must contain 96 finite prices")
    schedules = [[build_schedule(spec, level) for level in ACTION_LEVELS] for spec in specs]
    # Separate random streams let one operator's choices be replayed independently.
    rngs = [random.Random(config.seed), random.Random(config.seed + 1)]
    values = [[0.0] * 3 for _ in specs]
    cumulative, fixed_cumulative, rows = [0.0, 0.0], [0.0, 0.0], []
    for r in range(config.rounds):
        probabilities = [choice_probabilities(v, config.temperature) for v in values]
        actions = [rng.choices(range(3), weights=p)[0] for rng, p in zip(rngs, probabilities)]
        day_index = r % len(days)
        actual = settle_round(days[day_index], [schedules[i][a] for i, a in enumerate(actions)], config.price_impact)
        # Independent comparator: both always choose the medium schedule.
        fixed = settle_round(days[day_index], [s[1] for s in schedules], config.price_impact)
        for i in range(2):
            cumulative[i] += actual["profits"][i]
            fixed_cumulative[i] += fixed["profits"][i]
            values[i] = update_value(values[i], actions[i], actual["profits"][i], config)
        rows.append({"round": r + 1, "day_index": day_index, "actions": actions,
                     "probabilities_before": probabilities,
                     "probabilities_next": [choice_probabilities(v, config.temperature) for v in values],
                     "profits": actual["profits"], "cumulative": list(cumulative),
                     "fixed_cumulative": list(fixed_cumulative)})
    return {"config": asdict(config), "storage": [asdict(s) for s in specs],
            "action_levels": list(ACTION_LEVELS), "history": rows,
            "full_schedules": [s[2] for s in schedules]}
