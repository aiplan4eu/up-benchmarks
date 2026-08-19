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

from upbm.domains.coins import CoinsGenerator
from upbm.domains.coins.coins import IPC_DENOMINATIONS
from upbm.io import Format, dump_instance, parse_plan_string
from upbm.tests.base_domain_test import BaseDomainTest


class TestCoins(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "coins"

    @property
    def generator(self):
        return CoinsGenerator

    def _get_configs(self):
        default_config = (
            CoinsGenerator.get_domain_parameter_space().get_default_configuration()
        )
        gen = CoinsGenerator(default_config)
        instance_space = gen.instance_parameter_space
        instance_1 = Configuration(instance_space, {"n_coins": 5, "target": 5})
        instance_2 = Configuration(instance_space, {"n_coins": 5, "target": 29})
        return [(default_config, instance_1), (default_config, instance_2)]

    @property
    def plannable(self):
        # only the small target, solving the bigger ones optimally is hard
        return self._get_configs()[:1]

    @property
    def object_data(self):
        instances = self._get_configs()
        return [
            (*instances[0], [("coin", 5)]),
            (*instances[1], [("coin", 5)]),
        ]

    @property
    def problem_actions(self):
        instances = self._get_configs()
        # addCoin, update-penalty and the five apply-penalty actions
        return [(*instances[0], 7), (*instances[1], 7)]

    # NOTE the validation cases of the base class use the temporal plan
    # validator, while coins is an instantaneous domain, so the sequential
    # plans are validated here instead.
    def test_sequential_validation(self):
        domain_config, instance_config = self._get_configs()[0]
        gen = CoinsGenerator(domain_config)
        problem = gen.get_instance(instance_config)

        # c4 is the coin of denomination 5, so one coin reaches the target
        valid_plan = "(addcoin c4)\n(apply-penalty-one)"
        # the same plan without paying the penalty leaves the goal unsatisfied
        invalid_plan = "(addcoin c4)"

        for plan_str, expected in [
            (valid_plan, ValidationResultStatus.VALID),
            (invalid_plan, ValidationResultStatus.INVALID),
        ]:
            plan = parse_plan_string(problem, plan_str)
            with SequentialPlanValidator() as validator:
                v_res = validator.validate(problem, plan)
                self.assertEqual(v_res.status, expected, f"bad res:\n{v_res}")

    def test_denominations(self):
        domain_config, instance_config = self._get_configs()[0]
        gen = CoinsGenerator(domain_config)
        problem = gen.get_instance(instance_config)
        denomination = problem.fluent("denomination")
        values = [
            int(problem.initial_value(denomination(coin)).constant_value())
            for coin in problem.objects(problem.user_type("coin"))
        ]
        self.assertEqual(values, IPC_DENOMINATIONS)

    def test_metric_is_kept_in_every_instance(self):
        for domain_config, instance_config in self._get_configs():
            gen = CoinsGenerator(domain_config)
            problem = gen.get_instance(instance_config)
            self.assertEqual(len(problem.quality_metrics), 1)
            self.assertIn("coin-count", str(problem.quality_metrics[0]))

    def test_anml_warns_about_lost_metric(self):
        domain_config, instance_config = self._get_configs()[0]
        gen = CoinsGenerator(domain_config)
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
