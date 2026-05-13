import unittest
from upbm.factory import DomainFactory
from unified_planning.shortcuts import OneshotPlanner
from unified_planning.engines.plan_validator import TimeTriggeredPlanValidator
from unified_planning.engines.results import POSITIVE_OUTCOMES
from unified_planning.exceptions import UPNoSuitableEngineAvailableException
from pytest import skip


class BaseDomainTest(unittest.TestCase):
    __test__ = False

    def setUp(self):
        self.factory = DomainFactory()
        self.domain_name = ""
        self.generator = None
        self.validation_cases = []
        self.plannable = []
        self.object_data = {}
        self.problem_actions = {}

    def get_domain_name(self) -> str:
        return self.domain_name

    def get_generator(self):
        return self.generator

    def get_validation_cases(self):
        return self.validation_cases

    def get_plannable(self):
        return self.plannable

    def get_object_data(self):
        return self.object_data

    def get_problem_actions(self):
        return self.problem_actions

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
        for problem, n_acts in self.get_problem_actions().items():
            self.assertEqual(len(problem.actions), n_acts)
