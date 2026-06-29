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

from upbm.tests.base_domain_test import BaseDomainTest
from upbm.domains.kitting import KittingGenerator
from unified_planning.engines.results import ValidationResultStatus
from unified_planning.plans import TimeTriggeredPlan
from fractions import Fraction
from ConfigSpace import Configuration


class TestKitting(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "kitting"

    @property
    def generator(self):
        return KittingGenerator

    def _get_configs(self):
        default_config = (
            KittingGenerator.get_domain_parameter_space().get_default_configuration()
        )
        gen = KittingGenerator(default_config)
        instance_space = gen.instance_parameter_space
        instance_1 = Configuration(
            instance_space,
            {
                "n_components": 3,
                "kit_size": 2,
                "n_kit": 2,
                "n_robots": 1,
                "combination_idx": 1,
            },
        )
        instance_2 = Configuration(
            instance_space,
            {
                "n_components": 1,
                "kit_size": 1,
                "n_kit": 1,
                "n_robots": 1,
                "combination_idx": 1,
            },
        )

        return [(default_config, instance_1), (default_config, instance_2)]

    @property
    def plannable(self):
        return self._get_configs()

    @property
    def object_data(self):
        instances = self._get_configs()
        object_data = []
        object_data.append(
            (
                *instances[0],
                [
                    ("Location", 4),
                    ("Robot", 1),
                    ("Component", 4),
                    ("Kit", 1),
                ],
            )
        )
        object_data.append(
            (
                *instances[1],
                [
                    ("Location", 2),
                    ("Robot", 1),
                    ("Component", 2),
                    ("Kit", 1),
                ],
            )
        )
        return object_data

    @property
    def problem_actions(self):
        instances = self._get_configs()
        problem_actions = []
        problem_actions.append((*instances[0], 4))
        problem_actions.append((*instances[1], 4))
        return problem_actions

    @property
    def validation_cases(self):
        instances = self._get_configs()
        validation_cases = []
        plan_string = """
        0: (prepare_unload 0) [30]
        0.01: (move r0 l0 l1) [1]
        1.02: (load r0 l1 c1 k1 0) [5]
        6.03: (move r0 l1 l0) [1]
        10.02: (unload r0 k1 0) [5]
        """
        validation_cases.append(
            (*instances[1], plan_string, ValidationResultStatus.VALID)
        )
        return validation_cases
