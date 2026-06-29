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
from upbm.domains.replenish import ReplenishGenerator
from unified_planning.engines.results import ValidationResultStatus
from unified_planning.plans import TimeTriggeredPlan
from fractions import Fraction
from ConfigSpace import Configuration


class TestReplenish(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "replenish"

    @property
    def generator(self):
        return ReplenishGenerator

    def _get_configs(self):
        default_config = (
            ReplenishGenerator.get_domain_parameter_space().get_default_configuration()
        )
        gen = ReplenishGenerator(default_config)
        instance_space = gen.instance_parameter_space
        instance_1 = Configuration(
            instance_space,
            {
                "goal_sequence_length": 3,
                "n_cardboard_types": 2,
                "n_drawers": 2,
                "sequence_seed": 1,
            },
        )
        return [(default_config, instance_1)]

    @property
    def plannable(self):
        return self._get_configs()

    @property
    def object_data(self):
        instances = self._get_configs()
        object_data = []
        object_data.append((*instances[0], [("CardboardType", 3), ("Drawer", 2)]))
        return object_data

    @property
    def problem_actions(self):
        instances = self._get_configs()
        problem_actions = []
        problem_actions.append((*instances[0], 5))
        return problem_actions

    @property
    def validation_cases(self):
        instances = self._get_configs()
        validation_cases = []
        plan_string = """
        0: (initializeDrawer drawer_1 cardboard_type_1 4) [1]
        0: (initializeDrawer drawer_0 cardboard_type_2 5) [1]
        1.01: (build_box drawer_1 cardboard_type_1 0) [3]
        4.02: (build_box drawer_0 cardboard_type_2 1) [4]
        8.03: (build_box drawer_0 cardboard_type_2 2) [4]
        """
        validation_cases.append(
            (*instances[0], plan_string, ValidationResultStatus.VALID)
        )
        return validation_cases
