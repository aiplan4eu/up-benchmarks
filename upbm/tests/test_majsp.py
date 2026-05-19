from upbm.tests.base_domain_test import BaseDomainTest
from upbm.domains.majsp import MaJSPGenerator
from unified_planning.engines.results import ValidationResultStatus
from unified_planning.plans import TimeTriggeredPlan
from fractions import Fraction
from ConfigSpace import Configuration


class TestMaJSP(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "majsp"

    @property
    def generator(self):
        return MaJSPGenerator

    def _get_configs(self):
        gen = MaJSPGenerator(
            MaJSPGenerator.get_domain_parameter_space().get_default_configuration()
        )
        instance_space = gen.instance_parameter_space
        instance_1 = Configuration(
            instance_space,
            {"n_pallets": 2, "n_robots": 1, "n_positions": 3, "n_treatments": 2},
        )

        instance_2 = Configuration(
            instance_space,
            {"n_pallets": 1, "n_robots": 1, "n_positions": 2, "n_treatments": 1},
        )

        return [instance_1, instance_2]

    @property
    def plannable(self):
        return self._get_configs()

    @property
    def object_data(self):
        instances = self._get_configs()
        object_data = {}
        object_data[instances[0]] = [("Pallet", 3), ("Robot", 1), ("Position", 5)]
        object_data[instances[1]] = [("Pallet", 2), ("Robot", 1), ("Position", 4)]
        return object_data

    @property
    def problem_actions(self):
        instances = self._get_configs()
        problem_actions = []
        problem_actions.append((instances[0], 5))
        problem_actions.append((instances[1], 5))
        return problem_actions

    @property
    def validation_cases(self):
        instances = self._get_configs()

        validation_cases = []
        plan_string = """
        0: (load_at_depot r0 b0)
        0.01: (move r0 p0) [1]
        1.02: (make_treatment r0 b0 p0) [20]
        11.03: (load r0 b0 p0) [1]
        """
        validation_cases.append(
            (instances[1], plan_string, ValidationResultStatus.VALID)
        )
        return validation_cases
