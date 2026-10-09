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
from unified_planning.engines.plan_validator import ValidationResultStatus

from upbm.domains.factory_robot import FactoryRobotGenerator
from upbm.tests.base_domain_test import BaseDomainTest


def _config(index):
    """The domain configuration and the instance configuration of pfile<index>."""
    domain_space = FactoryRobotGenerator.get_domain_parameter_space()
    domain_config = domain_space.get_default_configuration()
    space = FactoryRobotGenerator(domain_config).instance_parameter_space
    return domain_config, Configuration(space, {"index": index})


class TestFactoryRobot(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "factory-robot"

    @property
    def generator(self):
        return FactoryRobotGenerator

    def _get_configs(self):
        """The two ends of the shipped set, pfile1 and pfile20."""
        return [_config(1), _config(20)]

    @property
    def plannable(self):
        # Even the smallest shipped instance is too slow for a unit test
        return []

    @property
    def object_data(self):
        smallest, largest = self._get_configs()
        return [
            (*smallest, [("robot", 2), ("station", 5)]),
            (*largest, [("robot", 12), ("station", 14)]),
        ]

    @property
    def problem_actions(self):
        return [(*config, 13) for config in self._get_configs()]

    @property
    def validation_cases(self):
        smallest, _ = self._get_configs()
        r0 = [
            "(set-turbo r0)",
            "(turbo-work r0 assembly1)",
            "(turbo-work r0 assembly1)",
            "(turbo-work r0 assembly1)",
            "(move r0 assembly1 charging)",
            "(recharge r0 charging)",
            "(turbo-work r0 charging)",
        ]
        r1 = ["(set-turbo r1)"] + ["(turbo-work r1 cooling)"] * 4

        cases = [
            (r0 + r1, ValidationResultStatus.VALID),
            # without the recharge, r0 has too little energy for its fourth
            (
                [a for a in r0 if "recharge" not in a] + r1,
                ValidationResultStatus.INVALID,
            ),
            # a fifth turbo-work leaves r0 at temperature 25
            (r0 + ["(turbo-work r0 charging)"] + r1, ValidationResultStatus.INVALID),
            # three turbo-works leave r1 at workload 30
            (r0 + r1[:-1], ValidationResultStatus.INVALID),
        ]
        return [(*smallest, "\n".join(plan), expected) for plan, expected in cases]
