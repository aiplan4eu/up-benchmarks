import unittest
from upbm.factory import DomainFactory
import os
from upbm.domains.matchcellar import MatchCellarGenerator
from unified_planning.shortcuts import OneshotPlanner
from unified_planning.engines.plan_validator import TimeTriggeredPlanValidator
from unified_planning.engines.results import ValidationResultStatus, POSITIVE_OUTCOMES
from unified_planning.exceptions import UPNoSuitableEngineAvailableException
from unified_planning.plans import TimeTriggeredPlan
from fractions import Fraction
from pathlib import Path
from pytest import skip


class TestMatchcellar(unittest.TestCase):
    # TODO structure and tests could maybe be parametrized and moved to base domain test class?
    def setUp(self):
        self.factory = DomainFactory()
        # TODO can we change factory to be compatible with os library paths? instad of having to use pathlib
        self.yamlpath = Path(
            os.path.join(os.path.dirname(__file__), "test_yamls", "matchcellar.yml")
        )
        self.instances, pddl_expressible = self.factory.generate_dataset(self.yamlpath)
        self.domain_name = "matchcellar"
        self.generator = MatchCellarGenerator

    def test_registration(self):
        self.assertIn(self.domain_name, self.factory.get_registered_domains())
        self.assertEqual(self.factory[self.domain_name], self.generator)

    def test_validation(self):
        light_match = self.instances[1][1].action("light_match")
        mend_fuse = self.instances[1][1].action("mend_fuse")
        match_1 = self.instances[1][1].object("match1")
        fuse_0 = self.instances[1][1].object("fuse0")
        fuse_1 = self.instances[1][1].object("fuse1")
        valid_plan = TimeTriggeredPlan(
            [
                (
                    Fraction(0, 1),
                    light_match(match_1),
                    Fraction(5, 1),
                ),
                (
                    Fraction(1, 100),
                    mend_fuse(fuse_0, match_1),
                    Fraction(2, 1),
                ),
                (
                    Fraction(205, 100),
                    mend_fuse(fuse_1, match_1),
                    Fraction(2, 1),
                ),
            ]
        )
        with TimeTriggeredPlanValidator() as validator:
            v_res = validator.validate(self.instances[1][1], valid_plan)
            self.assertEqual(
                v_res.status, ValidationResultStatus.VALID, f"bad res:\n{v_res}"
            )

    def test_planning(self):
        try:
            with OneshotPlanner(problem_kind=self.instances[0][1].kind) as planner:
                p_res = planner.solve(self.instances[0][1])
                self.assertIn(p_res.status, POSITIVE_OUTCOMES, f"bad plan:\n{p_res}")
        except UPNoSuitableEngineAvailableException:
            skip(
                "no planner available to test the problem - continuing with the other tests"
            )

    def test_objects(self):

        self.assertEqual(
            sum(
                1
                for _ in self.instances[0][1].objects(
                    self.instances[0][1].user_type("match")
                )
            ),
            3,
        )
        self.assertEqual(
            sum(
                1
                for _ in self.instances[1][1].objects(
                    self.instances[1][1].user_type("match")
                )
            ),
            2,
        )
        self.assertEqual(
            sum(
                1
                for _ in self.instances[0][1].objects(
                    self.instances[0][1].user_type("fuse")
                )
            ),
            4,
        )
        self.assertEqual(
            sum(
                1
                for _ in self.instances[1][1].objects(
                    self.instances[1][1].user_type("fuse")
                )
            ),
            2,
        )
        self.assertEqual(len(self.instances[0][1].actions), 2)
        self.assertEqual(len(self.instances[1][1].actions), 2)
