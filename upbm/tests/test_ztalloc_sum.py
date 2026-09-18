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

from ConfigSpace import Configuration
from unified_planning.engines.results import ValidationResultStatus

from upbm.domains.ztalloc_sum import ZtallocSumGenerator
from upbm.tests.base_domain_test import BaseDomainTest


class TestZtallocSum(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "ztalloc-sum"

    @property
    def generator(self):
        return ZtallocSumGenerator

    def _get_configs(self):
        default_config = (
            ZtallocSumGenerator.get_domain_parameter_space().get_default_configuration()
        )
        gen = ZtallocSumGenerator(default_config)
        space = gen.instance_parameter_space
        tiny = Configuration(space, {"n_registers": 1, "target": 2})
        small = Configuration(space, {"n_registers": 2, "target": 1})
        # the smallest instance of the IPC set
        ipc = Configuration(space, {"n_registers": 3, "target": 187})
        return [(default_config, tiny), (default_config, small), (default_config, ipc)]

    @property
    def plannable(self):
        return self._get_configs()[:2]

    @property
    def object_data(self):
        tiny, small, ipc = self._get_configs()
        return [
            (*tiny, [("register", 1)]),
            (*small, [("register", 2)]),
            (*ipc, [("register", 3)]),
        ]

    @property
    def problem_actions(self):
        return [(*config, 5) for config in self._get_configs()]

    @property
    def validation_cases(self):
        domain_config, instance_config = self._get_configs()[0]
        valid_plan = "(double r1)"
        invalid_plan = ""
        gen = ZtallocSumGenerator(domain_config)
        collatz_config = Configuration(
            gen.instance_parameter_space, {"n_registers": 1, "target": 5}
        )
        collatz_plan = "\n".join(
            ["(double r1)"] * 4
            + ["(m1d3-start r1)", "(m1d3-copy-reset r1)"]
            + ["(m1d3-div-step r1)"] * 5
            + ["(m1d3-finish r1)"]
        )
        return [
            (domain_config, instance_config, valid_plan, ValidationResultStatus.VALID),
            (
                domain_config,
                instance_config,
                invalid_plan,
                ValidationResultStatus.INVALID,
            ),
            (domain_config, collatz_config, collatz_plan, ValidationResultStatus.VALID),
        ]

    def test_initial_state_and_goal(self):
        domain_config, instance_config = self._get_configs()[2]
        gen = ZtallocSumGenerator(domain_config)
        problem = gen.get_instance(instance_config)

        value = problem.fluent("value")
        work_value = problem.fluent("work-value")
        for register in problem.objects(problem.user_type("register")):
            self.assertEqual(problem.initial_value(value(register)).constant_value(), 1)
            self.assertEqual(
                problem.initial_value(work_value(register)).constant_value(), 0
            )
        total_cost = problem.initial_value(problem.fluent("total-cost")())
        self.assertEqual(total_cost.constant_value(), 0)
        self.assertEqual(len(problem.goals), 2 + 2 * 3)

    # NOTE that ANML drops the metric is a property of upbm.io rather than of
    # this domain, so it is tested once in test_io.py instead of here.
    def test_metric_is_kept_in_every_instance(self):
        for domain_config, instance_config in self._get_configs():
            gen = ZtallocSumGenerator(domain_config)
            problem = gen.get_instance(instance_config)
            self.assertEqual(len(problem.quality_metrics), 1)
            self.assertIn("total-cost", str(problem.quality_metrics[0]))
