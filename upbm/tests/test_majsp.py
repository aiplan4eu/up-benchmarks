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
        gen = MaJSPGenerator(
            MaJSPGenerator.get_domain_parameter_space().get_default_configuration()
        )
        prob = gen.get_instance(instances[1])
        load_at_depot = prob.action("load_at_depot")
        move = prob.action("move")
        make_treatment = prob.action("make_treatment")
        load = prob.action("load")
        robot = prob.object("r0")
        pallet = prob.object("b0")
        position = prob.object("p0")
        valid_plan = TimeTriggeredPlan(
            [
                (
                    Fraction(0, 1),
                    load_at_depot(robot, pallet),
                    Fraction(0, 1),
                ),
                (
                    Fraction(1, 100),
                    move(robot, position),
                    Fraction(1, 1),
                ),
                (
                    Fraction(102, 100),
                    make_treatment(robot, pallet, position),
                    Fraction(2000, 100),
                ),
                (
                    Fraction(1103, 100),
                    load(robot, pallet, position),
                    Fraction(1, 1),
                ),
            ]
        )

        validation_cases = []
        validation_cases.append(
            (instances[1], valid_plan, ValidationResultStatus.VALID)
        )
        return validation_cases
