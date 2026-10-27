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

from upbm.domains.gear_car import GearCarGenerator
from upbm.tests.base_domain_test import BaseDomainTest


def _config(variant="ipc", **params):
    """The domain configuration of `variant` and an instance configuration of
    it, with the parameters left out at their defaults."""
    domain_space = GearCarGenerator.get_domain_parameter_space()
    domain_config = Configuration(domain_space, {"version": 1, "variant": variant})
    space = GearCarGenerator(domain_config).instance_parameter_space
    values = dict(space.get_default_configuration())
    values.update(params)
    return domain_config, Configuration(space, values)


class TestGearCar(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "gear-car"

    @property
    def generator(self):
        return GearCarGenerator

    def _get_configs(self):
        return [
            _config(n_gears=2, target_distance=2, fuel=30, beta=1),
            _config(n_gears=8, target_distance=2, fuel=30, beta=1),
            # the two ends of the shipped set: p000 (2 gears, explicit alpha)
            # and p19 (5 gears)
            _config(n_gears=2, target_distance=50, fuel=200, beta=48, alpha=19536),
            _config(n_gears=5, target_distance=2160, fuel=902, beta=159),
        ]

    @property
    def plannable(self):
        return self._get_configs()[:1]

    @property
    def object_data(self):
        gears = [2, 8, 2, 5]
        return [
            (*config, [("gear", n)]) for config, n in zip(self._get_configs(), gears)
        ]

    @property
    def validation_cases(self):
        plan = """
        (accelerate g1)
        (drive_aligned_gear g1)
        (decelerate g1)
        (decelerate g1)
        (drive_aligned_gear g1)
        (accelerate g1)
        """
        return [(*self._get_configs()[0], plan, ValidationResultStatus.VALID)]

    @property
    def problem_actions(self):
        return [(*config, 7) for config in self._get_configs()]
