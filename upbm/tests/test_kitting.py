from upbm.tests.base_domain_test import BaseDomainTest
from upbm.domains.kitting import KittingGenerator
from unified_planning.engines.results import ValidationResultStatus
from unified_planning.plans import TimeTriggeredPlan
from fractions import Fraction
from ConfigSpace import Configuration


class TestKitting(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "kitting"

    @property
    def generator(self):
        return KittingGenerator

    def _get_configs(self):
        gen = KittingGenerator(
            KittingGenerator.get_domain_parameter_space().get_default_configuration()
        )
        instance_space = gen.instance_parameter_space
        instance_1 = Configuration(
            instance_space,
            {
                "n_components": 3,
                "kit_size": 2,
                "n_kit": 2,
                "n_robots": 1,
                "combination_idx": 1,
            },
        )
        instance_2 = Configuration(
            instance_space,
            {
                "n_components": 1,
                "kit_size": 1,
                "n_kit": 1,
                "n_robots": 1,
                "combination_idx": 1,
            },
        )

        return [instance_1, instance_2]

    @property
    def plannable(self):
        return self._get_configs()

    @property
    def object_data(self):
        instances = self._get_configs()
        object_data = {}
        object_data[instances[0]] = [
            ("Location", 4),
            ("Robot", 1),
            ("Component", 4),
            ("Kit", 1),
        ]
        object_data[instances[1]] = [
            ("Location", 2),
            ("Robot", 1),
            ("Component", 2),
            ("Kit", 1),
        ]
        return object_data

    @property
    def problem_actions(self):
        instances = self._get_configs()
        problem_actions = []
        problem_actions.append((instances[0], 4))
        problem_actions.append((instances[1], 4))
        return problem_actions

    @property
    def validation_cases(self):
        instances = self._get_configs()
        gen = KittingGenerator(
            KittingGenerator.get_domain_parameter_space().get_default_configuration()
        )
        prob = gen.get_instance(instances[1])
        prepare_unload = prob.action("prepare_unload")
        move = prob.action("move")
        load = prob.action("load")
        unload = prob.action("unload")
        robot = prob.object("r0")
        l0 = prob.object("l0")
        l1 = prob.object("l1")
        component = prob.object("c1")
        kit = prob.object("k1")
        valid_plan = TimeTriggeredPlan(
            [
                (Fraction(0, 1), prepare_unload(0), Fraction(30, 1)),
                (
                    Fraction(1, 100),
                    move(robot, l0, l1),
                    Fraction(1, 1),
                ),
                (
                    Fraction(102, 100),
                    load(robot, l1, component, kit, 0),
                    Fraction(5, 1),
                ),
                (
                    Fraction(603, 100),
                    move(robot, l1, l0),
                    Fraction(1, 1),
                ),
                (
                    Fraction(1002, 100),
                    unload(robot, kit, 0),
                    Fraction(5, 1),
                ),
            ]
        )
        validation_cases = []
        validation_cases.append(
            (instances[1], valid_plan, ValidationResultStatus.VALID)
        )
        return validation_cases
