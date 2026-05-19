from upbm.tests.base_domain_test import BaseDomainTest
from upbm.domains.replenish import ReplenishGenerator
from unified_planning.engines.results import ValidationResultStatus
from unified_planning.plans import TimeTriggeredPlan
from fractions import Fraction
from ConfigSpace import Configuration


class TestReplenish(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "replenish"

    @property
    def generator(self):
        return ReplenishGenerator

    def _get_configs(self):
        gen = ReplenishGenerator(
            ReplenishGenerator.get_domain_parameter_space().get_default_configuration()
        )
        instance_space = gen.instance_parameter_space
        instance_1 = Configuration(
            instance_space,
            {
                "goal_sequence_length": 3,
                "n_cardboard_types": 2,
                "n_drawers": 2,
                "sequence_seed": 1,
            },
        )
        return [instance_1]

    @property
    def plannable(self):
        return self._get_configs()

    @property
    def object_data(self):
        instances = self._get_configs()
        object_data = {}
        object_data[instances[0]] = [("CardboardType", 3), ("Drawer", 2)]
        return object_data

    @property
    def problem_actions(self):
        instances = self._get_configs()
        problem_actions = []
        problem_actions.append((instances[0], 5))
        return problem_actions

    @property
    def validation_cases(self):
        instances = self._get_configs()
        gen = ReplenishGenerator(
            ReplenishGenerator.get_domain_parameter_space().get_default_configuration()
        )
        prob = gen.get_instance(instances[0])
        initializeDrawer = prob.action("initializeDrawer")
        build_box = prob.action("build_box")
        cardboard_1 = prob.object("cardboard_type_1")
        cardboard_2 = prob.object("cardboard_type_2")
        drawer_0 = prob.object("drawer_0")
        drawer_1 = prob.object("drawer_1")
        valid_plan = TimeTriggeredPlan(
            [
                (
                    Fraction(0, 1),
                    initializeDrawer(drawer_1, cardboard_1, 4),
                    Fraction(1, 1),
                ),
                (
                    Fraction(0, 1),
                    initializeDrawer(drawer_0, cardboard_2, 5),
                    Fraction(1, 1),
                ),
                (
                    Fraction(101, 100),
                    build_box(drawer_1, cardboard_1, 0),
                    Fraction(3, 1),
                ),
                (
                    Fraction(402, 100),
                    build_box(drawer_0, cardboard_2, 1),
                    Fraction(4, 1),
                ),
                (
                    Fraction(803, 100),
                    build_box(drawer_0, cardboard_2, 2),
                    Fraction(4, 1),
                ),
            ]
        )
        validation_cases = []
        validation_cases.append(
            (instances[0], valid_plan, ValidationResultStatus.VALID)
        )
        return validation_cases
