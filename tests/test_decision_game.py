"""Physics, strategic coupling and information boundaries of the decision lab."""
import unittest

from voltpulse.decision.game import (
    GameConfig, StorageSpec, build_schedule, settle_round, simulate_game, update_value,
)


class DecisionGameTests(unittest.TestCase):
    def test_schedule_has_physical_balance_for_every_action(self):
        spec = StorageSpec()
        for intensity in (0, 0.5, 1):
            s = build_schedule(spec, intensity)
            self.assertAlmostEqual(s["soc"][-1], spec.soc_initial)
            self.assertTrue(all(spec.soc_min - 1e-9 <= x <= spec.soc_max + 1e-9 for x in s["soc"]))
            self.assertTrue(all(0 <= x <= spec.power_mw for x in s["charge_mw"] + s["discharge_mw"]))
            self.assertTrue(all(c * d == 0 for c, d in zip(s["charge_mw"], s["discharge_mw"])))
        slow = build_schedule(StorageSpec(power_mw=1, energy_mwh=1000))
        self.assertAlmostEqual(slow["soc"][-1], 0.5)
        self.assertLess(max(slow["soc"]), 0.9)

    def test_opponent_action_changes_my_payoff_only_with_feedback(self):
        own = build_schedule(StorageSpec())
        idle = build_schedule(StorageSpec(), 0)
        base = [300.0] * 96
        alone = settle_round(base, [own, idle], 2)
        together = settle_round(base, [own, own], 2)
        self.assertLess(together["profits"][0], alone["profits"][0])
        self.assertEqual(settle_round(base, [own, idle], 0)["profits"][0], settle_round(base, [own, own], 0)["profits"][0])

    def test_settlement_matches_hand_calculation(self):
        schedule = {"net_power_mw": [4.0] + [0.0] * 95, "degradation_rmb": 3.0}
        idle = {"net_power_mw": [0.0] * 96, "degradation_rmb": 0}
        result = settle_round([10.0] * 96, [schedule, idle], 2)
        self.assertEqual(result["prices"][0], 18.0)
        self.assertEqual(result["profits"], [-21.0, 0.0])

    def test_only_observed_action_updates(self):
        self.assertEqual(update_value([1, 2, 3], 1, 0, GameConfig(learning_rate=0.5)), [1, 1, 3])

    def test_replay_is_seeded_and_future_prices_do_not_change_past_choices(self):
        days = [[300.0] * 96, [500.0] * 96]
        config = GameConfig(rounds=12)
        first = simulate_game(days, config)
        self.assertEqual(first, simulate_game(days, config))
        changed = simulate_game([days[0], [-50.0] * 96], config)
        self.assertEqual(first["history"][0], changed["history"][0])
        self.assertEqual(first["history"][1]["actions"], changed["history"][1]["actions"])
        self.assertEqual(first["history"][1]["probabilities_before"], changed["history"][1]["probabilities_before"])
        for row in first["history"]:
            for p in row["probabilities_next"]:
                self.assertAlmostEqual(sum(p), 1)
                self.assertTrue(all(0 <= v <= 1 for v in p))

    def test_invalid_inputs_are_rejected(self):
        for kwargs in ({"price_impact": -1}, {"learning_rate": 0}, {"temperature": float("nan")}, {"rounds": 1.5}):
            with self.assertRaises(ValueError):
                GameConfig(**kwargs)
        with self.assertRaises(ValueError):
            simulate_game([[1.0] * 95])


if __name__ == "__main__":
    unittest.main()
