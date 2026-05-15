from upbm.tests.base_domain_test import BaseDomainTest
from upbm.domains.matchcellar import MatchCellarGenerator
from unified_planning.engines.results import ValidationResultStatus
from unified_planning.plans import TimeTriggeredPlan
from fractions import Fraction
from ConfigSpace import Configuration


class TestMatchcellar(BaseDomainTest):
    __test__ = True

    def get_domain_name(self):
        return "matchcellar"

    def get_generator(self):
        return MatchCellarGenerator

    def _get_instances(self):
        gen = MatchCellarGenerator(
            MatchCellarGenerator.get_domain_parameter_space().get_default_configuration()
        )
        instance_space = gen.instance_parameter_space
        instance_1 = gen.get_instance(
            Configuration(instance_space, {"n_matches": 3, "n_fuses": 4})
        )
        instance_2 = gen.get_instance(
            Configuration(instance_space, {"n_matches": 2, "n_fuses": 2})
        )
        return [instance_1, instance_2]

    def get_plannable(self):
        return self._get_instances()

    def get_object_data(self):
        instances = self._get_instances()
        object_data = {}
        object_data[instances[0]] = [("match", 3), ("fuse", 4)]
        object_data[instances[1]] = [("match", 2), ("fuse", 2)]
        return object_data

    def get_problem_actions(self):
        instances = self._get_instances()
        problem_actions = []
        problem_actions.append((instances[0], 2))
        problem_actions.append((instances[1], 2))
        return problem_actions

    def get_validation_cases(self):
        instances = self._get_instances()
        light_match = instances[1].action("light_match")
        mend_fuse = instances[1].action("mend_fuse")
        match_1 = instances[1].object("match1")
        fuse_0 = instances[1].object("fuse0")
        fuse_1 = instances[1].object("fuse1")
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

        validation_cases = []
        validation_cases.append(
            (instances[1], valid_plan, ValidationResultStatus.VALID)
        )
        return validation_cases
