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
    # TODO make base test class and extend that instead?
    def setUp(self):
        self.factory = DomainFactory()
        # TODO can we change factory to be compatible with os library paths? instad of having to use pathlib
        self.yamlpath = Path(
            os.path.join(os.path.dirname(__file__), "test_yamls", "matchcellar.yml")
        )
        instances, pddl_expressible = self.factory.generate_dataset(self.yamlpath)

        self.domain_name = "matchcellar"
        self.generator = MatchCellarGenerator

        self.plannable = [instances[0][1], instances[1][1]]

        self.object_data = {}
        self.object_data[instances[0][1]] = [("match", 3), ("fuse", 4)]
        self.object_data[instances[1][1]] = [("match", 2), ("fuse", 2)]
        self.problem_actions = {}
        self.problem_actions[instances[0][1]] = 2
        self.problem_actions[instances[1][1]] = 2

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

        self.validation_cases = []
        self.validation_cases.append(
            tuple([instances[1][1], valid_plan, ValidationResultStatus.VALID])
        )

    def test_registration(self):
        self.assertIn(self.domain_name, self.factory.get_registered_domains())
        self.assertEqual(self.factory[self.domain_name], self.generator)

    def test_validation(self):
        for (problem, plan, expected_status) in self.validation_cases:
            with TimeTriggeredPlanValidator() as validator:
                v_res = validator.validate(problem, plan)
                self.assertEqual(v_res.status, expected_status, f"bad res:\n{v_res}")

    def test_planning(self):
        try:
            for p in self.plannable:
                with OneshotPlanner(problem_kind=p.kind) as planner:
                    p_res = planner.solve(p)
                    self.assertIn(
                        p_res.status, POSITIVE_OUTCOMES, f"bad plan:\n{p_res}"
                    )
        except UPNoSuitableEngineAvailableException:
            skip("no planner available to test the problem")

    def test_objects_and_actions(self):
        for problem, objects_list in self.object_data.items():
            for (obj_name, n_objs) in objects_list:
                self.assertEqual(
                    sum(1 for _ in problem.objects(problem.user_type(obj_name))), n_objs
                )
        for problem, n_acts in self.problem_actions.items():
            self.assertEqual(len(problem.actions), n_acts)
