import unittest
from unittest.mock import patch
from types import SimpleNamespace

import ai
from tron_light_cycle import Rider, GameArena


class Arena:
    is_team_mode = GameArena.is_team_mode
    team_for_player = staticmethod(GameArena.team_for_player)

    def __init__(self, teams=False):
        self.sim_time = 0.0
        self.final_duel = False
        self.controller = SimpleNamespace(game_mode="training", training_teams=teams)
        self.riders = {}
        self.blocked = set()

    def add(self, pid, cell, is_ai=True):
        rider = Rider(pid, cell, (1, 0), "#00FFFF")
        rider.is_ai = is_ai
        self.riders[pid] = rider
        return rider

    def is_free(self, cell):
        return 0 <= cell[0] < 50 and 0 <= cell[1] < 50 and cell not in self.blocked


class TargetTests(unittest.TestCase):
    def test_ai_can_hunt_another_ai_instead_of_p1(self):
        game = Arena()
        game.add(1, (40, 40), False)
        hunter = game.add(2, (10, 10))
        rival = game.add(3, (12, 10))
        self.assertIs(ai._select_target(game, hunter), rival)

    def test_teams_exclude_even_preferred_ally(self):
        game = Arena(True)
        hunter = game.add(1, (10, 10))
        game.add(3, (11, 10))
        rival = game.add(4, (20, 10))
        self.assertIs(ai._select_target(game, hunter, 3), rival)

    def test_both_teams_exclude_their_partner(self):
        game = Arena(True)
        hunter = game.add(2, (10, 10))
        game.add(4, (11, 10))
        rival = game.add(3, (20, 10))
        self.assertIs(ai._select_target(game, hunter), rival)

    def test_dead_target_is_replaced(self):
        game = Arena()
        hunter = game.add(2, (10, 10))
        first = game.add(1, (12, 10))
        rival = game.add(3, (20, 10))
        ai._select_target(game, hunter)
        first.alive = False
        self.assertIs(ai._select_target(game, hunter), rival)

    def test_target_stays_until_other_is_significantly_closer(self):
        game = Arena()
        hunter = game.add(2, (10, 10))
        first = game.add(1, (20, 10))
        rival = game.add(3, (21, 10))
        ai._select_target(game, hunter)
        rival.cell = (19, 10)
        self.assertIs(ai._select_target(game, hunter), first)
        rival.cell = (16, 10)
        self.assertIs(ai._select_target(game, hunter), rival)

    def test_rinzler_preference_and_no_enemies(self):
        game = Arena()
        hunter = game.add(2, (10, 10))
        human = game.add(1, (40, 40), False)
        rival = game.add(3, (11, 10))
        self.assertIs(ai._select_target(game, hunter, 1), human)
        human.alive = rival.alive = False
        self.assertIsNone(ai._select_target(game, hunter, 1))
        self.assertIsNone(hunter.ai_target_pid)

    def test_final_duel_removes_team_restriction(self):
        game = Arena(True)
        game.final_duel = True
        hunter = game.add(1, (10, 10))
        rival = game.add(3, (20, 10))
        self.assertIs(ai._select_target(game, hunter), rival)


class ReactionTests(unittest.TestCase):
    def test_each_level_waits_and_does_not_dodge_fresh_cut(self):
        for level, cfg in ai.LEVELS.items():
            with self.subTest(level=level), patch("ai.random.random", return_value=0.5):
                game = Arena()
                hunter = game.add(2, (10, 10))
                ai.decide(game, hunter, level)
                game.blocked.add((11, 10))
                game.sim_time = cfg["reaction"] - 0.001
                ai.decide(game, hunter, level)
                self.assertEqual(hunter.queue, [])
                self.assertFalse(game.is_free((11, 10)))
                game.sim_time = cfg["reaction"]
                ai.decide(game, hunter, level)
                self.assertEqual(len(hunter.queue), 1)
                self.assertNotEqual(hunter.queue[0], hunter.dir)

    def test_pause_does_not_advance_reaction(self):
        game = Arena()
        hunter = game.add(2, (10, 10))
        ai.decide(game, hunter)
        deadline = hunter.ai_next_decision_at
        with patch("ai._select_target") as select:
            for _ in range(10):
                ai.decide(game, hunter)
            select.assert_not_called()
        self.assertEqual(hunter.ai_next_decision_at, deadline)

    def test_no_duplicate_turns_and_reset_on_respawn(self):
        game = Arena()
        hunter = game.add(2, (10, 10))
        ai.decide(game, hunter)
        hunter.queue.append((0, 1))
        game.sim_time = 1.0
        ai.decide(game, hunter)
        self.assertEqual(hunter.queue, [(0, 1)])
        hunter.ai_target_pid = 1
        ai.reset(hunter)
        self.assertIsNone(hunter.ai_target_pid)
        self.assertIsNone(hunter.ai_next_decision_at)
        ai.decide(game, hunter)
        self.assertGreater(hunter.ai_next_decision_at, game.sim_time)


if __name__ == "__main__":
    unittest.main()
