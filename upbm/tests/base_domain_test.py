# Copyright 2026 Unified Planning library and its maintainers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from upbm.factory import DomainFactory
from unified_planning.shortcuts import OneshotPlanner
from unified_planning.engines.plan_validator import (
    TimeTriggeredPlanValidator,
    ValidationResultStatus,
)
from unified_planning.engines.results import POSITIVE_OUTCOMES
from unified_planning.exceptions import UPNoSuitableEngineAvailableException
from pytest import skip
from typing import Any, List, Tuple
from ConfigSpace import Configuration
from upbm.io import parse_plan_string


class BaseDomainTest(unittest.TestCase):
    __test__ = False

    def setUp(self):
        self.factory = DomainFactory()

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
    ) -> List[Tuple[Configuration, Configuration, str, ValidationResultStatus]]:
        """
        Returns a list of validation cases. Every case is a tuple:
            - a generator domain configuration
            - a problem instance configuration
            - the plan we want to validate on the problem, encoded as a string
            - the expected result from the validation
        """
        return []

    @property
    def plannable(self) -> List[Tuple[Configuration, Configuration]]:
        """
        Returns a list of tuples containing domain generator configurations and problem instance configurations we can quickly plan on.
        These problems have to be simple enough so that the tests do note get unreasonably bloated given the amount of domains to test.
        """
        return []

    @property
    def object_data(
        self,
    ) -> List[Tuple[Configuration, Configuration, List[Tuple[str, int]]]]:
        """
        Returns a list that maps pairs of generator domain configurations and problem instance configurations to information about their objects.
        This information is a list of tuples(object_type_name, object_amount) that we are expected to find in the problem.
        """
        return []

    @property
    def problem_actions(self) -> List[Tuple[Configuration, Configuration, int]]:
        """
        Returns a List of tuples(generator domain configuration, problem instance configuration, number_of_actions) that we want to verify are correct.
        """
        return []

    def test_registration(self):
        self.assertIn(self.domain_name, self.factory.get_registered_domains())
        self.assertEqual(self.factory[self.domain_name], self.generator)

    def test_validation(self):
        for (
            domain_config,
            problem_config,
            plan_str,
            expected_status,
        ) in self.validation_cases:
            gen = self.generator(domain_config)
            problem = gen.get_instance(problem_config)
            plan = parse_plan_string(problem, plan_str)
            with TimeTriggeredPlanValidator() as validator:
                v_res = validator.validate(problem, plan)
                print(v_res)
                self.assertEqual(v_res.status, expected_status, f"bad res:\n{v_res}")

    def test_planning(self):
        try:
            for d_c, p_c in self.plannable:
                gen = self.generator(d_c)
                p = gen.get_instance(p_c)
                with OneshotPlanner(problem_kind=p.kind) as planner:
                    p_res = planner.solve(p)
                    print(p_res)
                    self.assertIn(
                        p_res.status, POSITIVE_OUTCOMES, f"bad plan:\n{p_res}"
                    )
        except UPNoSuitableEngineAvailableException:
            skip("no planner available to test the problem")

    def test_objects_and_actions(self):
        for domain_config, problem_config, objects_list in self.object_data:
            gen = self.generator(domain_config)
            problem = gen.get_instance(problem_config)
            for (obj_name, n_objs) in objects_list:
                self.assertEqual(
                    sum(1 for _ in problem.objects(problem.user_type(obj_name))), n_objs
                )
        for domain_config, problem_config, n_acts in self.problem_actions:
            gen = self.generator(domain_config)
            problem = gen.get_instance(problem_config)
            self.assertEqual(len(problem.actions), n_acts)
