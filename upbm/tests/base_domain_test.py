import unittest
from upbm.factory import DomainFactory
import unified_planning as up
from unified_planning.shortcuts import OneshotPlanner
from unified_planning.engines.plan_validator import (
    TimeTriggeredPlanValidator,
    ValidationResultStatus,
)
from unified_planning.engines.results import POSITIVE_OUTCOMES
from unified_planning.exceptions import UPNoSuitableEngineAvailableException
from pytest import skip
from typing import Any, List, Tuple, Dict
import re
from fractions import Fraction
from ConfigSpace import Configuration


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
    ) -> List[Tuple[Configuration, str, ValidationResultStatus]]:
        """
        Returns a list of validation cases. Every case is a tuple:
            - a problem instance configuration
            - the plan we want to validate on the problem, encoded as a string
            - the expected result from the validation
        """
        return []

    @property
    def plannable(self) -> List[Configuration]:
        """
        Returns a list of problem instance configurations we can quickly plan on.
        These problems have to be simple enough so that the tests do note get unreasonably bloated given the amount of domains to test.
        """
        return []

    @property
    def object_data(self) -> Dict[Configuration, List[Tuple[str, int]]]:
        """
        Returns a dictionary that maps problem instance configurations to information about their objects.
        This information is a list of tuples(object_type_name, object_amount) that we are expected to find in the problem.
        """
        return {}

    @property
    def problem_actions(self) -> List[Tuple[Configuration, int]]:
        """
        Returns a List of tuples(problem instance configuration, number_of_actions) that we want to verify are correct.
        """
        return []

    def test_registration(self):
        self.assertIn(self.domain_name, self.factory.get_registered_domains())
        self.assertEqual(self.factory[self.domain_name], self.generator)

    def test_validation(self):
        for (problem_config, plan_str, expected_status) in self.validation_cases:
            problem = self.default_gen.get_instance(problem_config)
            plan = _parse_plan_string(problem, plan_str)
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


def _parse_plan_string(
    problem: "up.model.Problem",
    plan_str: str,
) -> "up.plans.Plan":
    """
    The format of the string must be:
        ``(action-name param1 param2 ... paramN)`` in each line for SequentialPlans
        ``start-time: (action-name param1 param2 ... paramN) [duration]`` in each line for TimeTriggeredPlans,
        where ``[duration]`` is optional and not specified for InstantaneousActions.
    """
    actions: List = []
    is_tt = False
    for line in plan_str.splitlines():
        if re.match(r"^\s*(;.*)?$", line):
            continue
        s_ai = re.match(r"^\s*\(\s*([\w?-]+)((\s+[\w?-]+)*)\s*\)\s*$", line)
        t_ai = re.match(
            r"^\s*(\d+\.?\d*)\s*:\s*\(\s*([\w?-]+)((\s+[\w?-]+)*)\s*\)\s*(\[\s*(\d+\.?\d*)\s*\])?\s*$",
            line,
        )
        if s_ai:
            assert is_tt == False
            name = s_ai.group(1)
            params_name = s_ai.group(2).split()
        elif t_ai:
            is_tt = True
            start = Fraction(t_ai.group(1))
            name = t_ai.group(2)
            params_name = t_ai.group(3).split()
            dur = None
            if t_ai.group(6) is not None:
                dur = Fraction(t_ai.group(6))
        else:
            raise ValueError(f"Error parsing test plan:\n{plan_str}")

        action = problem.action(name)
        assert isinstance(action, up.model.Action), "Wrong plan or renaming."
        parameters = []
        for p in params_name:
            try:
                obj = problem.object(p)
                assert isinstance(obj, up.model.Object)
                parameters.append(problem.environment.expression_manager.ObjectExp(obj))
            except:
                parameters.append(problem.environment.expression_manager.Int(int(p)))
        act_instance = up.plans.ActionInstance(action, tuple(parameters))
        if is_tt:
            actions.append((start, act_instance, dur))
        else:
            actions.append(act_instance)
    if is_tt:
        return up.plans.TimeTriggeredPlan(actions)
    else:
        return up.plans.SequentialPlan(actions)
