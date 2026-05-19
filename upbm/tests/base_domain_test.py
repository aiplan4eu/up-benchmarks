import unittest
from upbm.factory import DomainFactory
from unified_planning.shortcuts import OneshotPlanner, Problem
from unified_planning.engines.plan_validator import (
    TimeTriggeredPlanValidator,
    ValidationResultStatus,
)
from unified_planning.engines.results import POSITIVE_OUTCOMES, Plan
from unified_planning.exceptions import UPNoSuitableEngineAvailableException
from pytest import skip
from typing import Any, List, Tuple, Dict


class BaseDomainTest(unittest.TestCase):
    __test__ = False

    def setUp(self):
        self.factory = DomainFactory()
        self.default_gen = self.generator(
            self.generator.get_domain_parameter_space().get_default_configuration()
        )

    @property
    def domain_name(self) -> str:
        """
        Returns the name of the domain we are testing
        """
        return ""

    @property
    def generator(self) -> Any:
        """
        Returns the generator class of the domain we are testing (imported from upbm.domains. ...)
        """
        return None

    @property
    def validation_cases(
        self,
    ) -> List[Tuple[Problem, Plan, ValidationResultStatus]]:
        """
        Returns a list of validation cases. Every case is a tuple:
            - a problem instance
            - the plan we want to validate on the problem
            - the expected result from the validation
        """
        return []

    @property
    def plannable(self) -> List[Problem]:
        """
        Returns a list of problems we can quickly plan on.
        These problems have to be simple enough so that the tests do note get unreasonably bloated given the amount of domains to test.
        """
        return []

    @property
    def object_data(self) -> Dict[Problem, List[Tuple[str, int]]]:
        """
        Returns a dictionary that maps problems to information about their objects.
        This information is a list of tuples(object_type_name, object_amount) that we are expected to find in the problem.
        """
        return {}

    @property
    def problem_actions(self) -> List[Tuple[Problem, int]]:
        """
        Returns a List of tuples(problem, number_of_actions) that we want to verify are correct.
        """
        return []

    def test_registration(self):
        self.assertIn(self.domain_name, self.factory.get_registered_domains())
        self.assertEqual(self.factory[self.domain_name], self.generator)

    def test_validation(self):
        for (problem_config, plan, expected_status) in self.validation_cases:
            problem = self.default_gen.get_instance(problem_config)
            with TimeTriggeredPlanValidator() as validator:
                v_res = validator.validate(problem, plan)
                print(v_res)
                self.assertEqual(v_res.status, expected_status, f"bad res:\n{v_res}")

    def test_planning(self):
        try:
            for p_c in self.plannable:
                p = self.default_gen.get_instance(p_c)
                with OneshotPlanner(problem_kind=p.kind) as planner:
                    p_res = planner.solve(p)
                    print(p_res)
                    self.assertIn(
                        p_res.status, POSITIVE_OUTCOMES, f"bad plan:\n{p_res}"
                    )
        except UPNoSuitableEngineAvailableException:
            skip("no planner available to test the problem")

    def test_objects_and_actions(self):
        for problem_config, objects_list in self.object_data.items():
            problem = self.default_gen.get_instance(problem_config)
            for (obj_name, n_objs) in objects_list:
                self.assertEqual(
                    sum(1 for _ in problem.objects(problem.user_type(obj_name))), n_objs
                )
        for problem_config, n_acts in self.problem_actions:
            problem = self.default_gen.get_instance(problem_config)
            self.assertEqual(len(problem.actions), n_acts)
