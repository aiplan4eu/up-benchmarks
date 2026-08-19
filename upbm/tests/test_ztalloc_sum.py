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

import tempfile
import warnings
from pathlib import Path

from ConfigSpace import Configuration
from unified_planning.engines.plan_validator import SequentialPlanValidator
from unified_planning.engines.results import ValidationResultStatus

from upbm.domains.ztalloc_sum import ZtallocSumGenerator
from upbm.io import Format, dump_instance, parse_plan_string
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
        # one register that only needs a double, and two registers where the
        # second one has to be emptied
        tiny = Configuration(space, {"n_registers": 1, "target": 2})
        small = Configuration(space, {"n_registers": 2, "target": 1})
        # the smallest instance of the IPC set
        ipc = Configuration(space, {"n_registers": 3, "target": 187})
        return [(default_config, tiny), (default_config, small), (default_config, ipc)]

    @property
    def plannable(self):
        # only the two tiny ones, the IPC targets need a long search
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
        # double, m1d3-start, m1d3-copy-reset, m1d3-div-step and m1d3-finish
        return [(*config, 5) for config in self._get_configs()]

    # NOTE the validation cases of the base class use the temporal plan
    # validator, while ztalloc-sum is an instantaneous domain, so the sequential
    # plans are validated here instead.
    def test_sequential_validation(self):
        domain_config, instance_config = self._get_configs()[0]
        gen = ZtallocSumGenerator(domain_config)
        problem = gen.get_instance(instance_config)

        for plan_str, expected in [
            # a single double takes the register from 1 to the target of 2
            ("(double r1)", ValidationResultStatus.VALID),
            # doing nothing leaves the register at 1, so the sum is wrong
            ("", ValidationResultStatus.INVALID),
        ]:
            plan = parse_plan_string(problem, plan_str)
            with SequentialPlanValidator() as validator:
                v_res = validator.validate(problem, plan)
                self.assertEqual(v_res.status, expected, f"bad res:\n{v_res}")

    def test_reversed_collatz_step(self):
        """1 -> 2 -> 4 -> 8 -> 16, then the m1d3 gadget gives (16 - 1) / 3 = 5."""
        domain_config = (
            ZtallocSumGenerator.get_domain_parameter_space().get_default_configuration()
        )
        gen = ZtallocSumGenerator(domain_config)
        instance_config = Configuration(
            gen.instance_parameter_space, {"n_registers": 1, "target": 5}
        )
        problem = gen.get_instance(instance_config)

        plan_str = "\n".join(
            ["(double r1)"] * 4
            + ["(m1d3-start r1)", "(m1d3-copy-reset r1)"]
            + ["(m1d3-div-step r1)"] * 5
            + ["(m1d3-finish r1)"]
        )
        plan = parse_plan_string(problem, plan_str)
        with SequentialPlanValidator() as validator:
            v_res = validator.validate(problem, plan)
            self.assertEqual(v_res.status, ValidationResultStatus.VALID, f"{v_res}")

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
        # the sum goal plus free, and normal / work-value for each register
        self.assertEqual(len(problem.goals), 2 + 2 * 3)

    def test_metric_is_kept_in_every_instance(self):
        for domain_config, instance_config in self._get_configs():
            gen = ZtallocSumGenerator(domain_config)
            problem = gen.get_instance(instance_config)
            self.assertEqual(len(problem.quality_metrics), 1)
            self.assertIn("total-cost", str(problem.quality_metrics[0]))

    def test_anml_warns_about_lost_metric(self):
        domain_config, instance_config = self._get_configs()[0]
        gen = ZtallocSumGenerator(domain_config)
        problem = gen.get_instance(instance_config)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "problem.anml"
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                dump_instance(problem, Format.ANML, out)
            # the warning must not stop the file from being written
            self.assertTrue(out.exists())
            self.assertEqual(len(caught), 1)
            self.assertIn("metric", str(caught[0].message))
