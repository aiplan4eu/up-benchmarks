from upbm.tests.base_domain_test import BaseDomainTest
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


class TestMatchcellar(BaseDomainTest):
    __test__ = True

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
