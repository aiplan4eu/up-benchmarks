import unittest
from upbm.factory import DomainFactory
import importlib
import json
import os
from upbm.domains.matchcellar import MatchCellarGenerator
from unified_planning.shortcuts import OneshotPlanner
from unified_planning.engines.plan_validator import TimeTriggeredPlanValidator
from unified_planning.engines.results import ValidationResultStatus, POSITIVE_OUTCOMES
from unified_planning.exceptions import UPNoRequestedEngineAvailableException
from unified_planning.plans import TimeTriggeredPlan
import warnings
from fractions import Fraction

NAME = "matchcellar"
GENERATOR = MatchCellarGenerator


class TestGenericYAMLS(unittest.TestCase):
    def setUp(self):
        self.factory = DomainFactory()

    # TODO split into smaller tests

    def test_placeholder_name(self):
        yamlpath = os.path.join(
            os.path.dirname(__file__), "test_yamls", "matchcellar.yml"
        )

        self.assertIn(NAME, self.factory.get_registered_domains())
        self.assertEqual(self.factory[NAME], GENERATOR)

        instances, pddl_expressible = self.factory.generate_dataset(yamlpath)

        light_match = instances[1][1].action("light_match")
        mend_fuse = instances[1][1].action("mend_fuse")
        match_1 = instances[1][1].object("match1")
        fuse_0 = instances[1][1].object("fuse0")
        fuse_1 = instances[1][1].object("fuse1")
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
        # plan validator should always be available, no need for try catch
        with TimeTriggeredPlanValidator() as validator:
            v_res = validator.validate(instances[1][1], valid_plan)
            # print(v_res)
            self.assertEqual(v_res.status, ValidationResultStatus.VALID)

        try:
            with OneshotPlanner(problem_kind=instances[0][1].kind) as planner:
                p_res = planner.solve(instances[0][1])
                # print (res)
                self.assertIn(p_res.status, POSITIVE_OUTCOMES)
        except UPNoRequestedEngineAvailableException:
            warnings.warn(
                "no planner available to test the problem - continuing with the other tests"
            )

        self.assertEqual(
            sum(1 for _ in instances[0][1].objects(instances[0][1].user_type("match"))),
            3,
        )
        self.assertEqual(
            sum(1 for _ in instances[1][1].objects(instances[1][1].user_type("match"))),
            2,
        )
        self.assertEqual(
            sum(1 for _ in instances[0][1].objects(instances[0][1].user_type("fuse"))),
            4,
        )
        self.assertEqual(
            sum(1 for _ in instances[1][1].objects(instances[0][1].user_type("fuse"))),
            2,
        )
        self.assertEqual(len(instances[0][1].actions), 2)
        self.assertEqual(len(instances[1][1].actions), 2)
