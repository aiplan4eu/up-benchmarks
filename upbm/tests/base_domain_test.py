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

    def get_domain_name(self) -> str:
        """
        Returns the name of the domain we are testing
        """
        return ""

    def get_generator(self) -> Any:
        """
        Returns the generator class of the domain we are testing (imported from upbm.domains. ...)
        """
        return None

    def get_validation_cases(
        self,
    ) -> List[Tuple[Problem, Plan, ValidationResultStatus]]:
        """
        Returns a list of validation cases. Every case is a tuple:
            - a problem instance
            - the plan we want to validate on the problem
            - the expected result from the validation
        """
        return []

    def get_plannable(self) -> List[Problem]:
        """
        Returns a list of problems we can quickly plan on.
        These problems have to be simple enough so that the tests do note get unreasonably bloated given the amount of domains to test.
        """
        return []

    def get_object_data(self) -> Dict[Problem, List[Tuple[str, int]]]:
        """
        Returns a dictionary that maps problems to information about their objects.
        This information is a list of tuples(object_type_name, object_amount) that we are expected to find in the problem.
        """
        return {}

    def get_problem_actions(self) -> List[Tuple[Problem, int]]:
        """
        Returns a List of tuples(problem, number_of_actions) that we want to verify are correct.
        """
        return []

    def test_registration(self):
        self.assertIn(self.get_domain_name(), self.factory.get_registered_domains())
        self.assertEqual(self.factory[self.get_domain_name()], self.get_generator())

    def test_validation(self):
        for (problem, plan, expected_status) in self.get_validation_cases():
            with TimeTriggeredPlanValidator() as validator:
                v_res = validator.validate(problem, plan)
                print(v_res)
                self.assertEqual(v_res.status, expected_status, f"bad res:\n{v_res}")

    def test_planning(self):
        try:
            for p in self.get_plannable():
                with OneshotPlanner(problem_kind=p.kind) as planner:
                    p_res = planner.solve(p)
                    print(p_res)
                    self.assertIn(
                        p_res.status, POSITIVE_OUTCOMES, f"bad plan:\n{p_res}"
                    )
        except UPNoSuitableEngineAvailableException:
            skip("no planner available to test the problem")

    def test_objects_and_actions(self):
        for problem, objects_list in self.get_object_data().items():
            for (obj_name, n_objs) in objects_list:
                self.assertEqual(
                    sum(1 for _ in problem.objects(problem.user_type(obj_name))), n_objs
                )
        for problem, n_acts in self.get_problem_actions():
            self.assertEqual(len(problem.actions), n_acts)
