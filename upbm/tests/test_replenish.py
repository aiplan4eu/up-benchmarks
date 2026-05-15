from upbm.tests.base_domain_test import BaseDomainTest
from upbm.domains.replenish import ReplenishGenerator
from unified_planning.engines.results import ValidationResultStatus
from unified_planning.plans import TimeTriggeredPlan
from fractions import Fraction
from ConfigSpace import Configuration


class TestReplenish(BaseDomainTest):
    __test__ = True

    def get_domain_name(self):
        return "replenish"

    def get_generator(self):
        return ReplenishGenerator

    def _get_instances(self):
        gen = ReplenishGenerator(
            ReplenishGenerator.get_domain_parameter_space().get_default_configuration()
        )
        instance_space = gen.instance_parameter_space
        instance_1 = gen.get_instance(
            Configuration(
                instance_space,
                {
                    "goal_sequence_length": 3,
                    "n_cardboard_types": 2,
                    "n_drawers": 2,
                    "sequence_seed": 1,
                },
            )
        )
        return [instance_1]

    def get_plannable(self):
        return self._get_instances()

    def get_object_data(self):
        instances = self._get_instances()
        object_data = {}
        object_data[instances[0]] = [("CardboardType", 3), ("Drawer", 2)]
        return object_data

    def get_problem_actions(self):
        instances = self._get_instances()
        problem_actions = []
        problem_actions.append((instances[0], 5))
        return problem_actions

    def get_validation_cases(self):
        instances = self._get_instances()
        initializeDrawer = instances[0].action("initializeDrawer")
        build_box = instances[0].action("build_box")
        cardboard_1 = instances[0].object("cardboard_type_1")
        cardboard_2 = instances[0].object("cardboard_type_2")
        drawer_0 = instances[0].object("drawer_0")
        drawer_1 = instances[0].object("drawer_1")
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
