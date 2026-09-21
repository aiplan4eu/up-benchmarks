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


# The car of the IPC set, gear by gear: (v_min, v_max, min_acc, max_acc,
# fuel_aligned, fuel_under, fuel_over) read off the shipped instances. Only
# the four gear counts the dataset actually uses are listed, which is exactly
# what the generator claims to cover.
IPC_GEAR_TABLES = {
    2: [
        (0, 2, -1, 2, 11, 18, 17),
        (2, 4, -1, 0, 9, 17, 14),
    ],
    3: [
        (0, 2, -1, 2, 11, 18, 18),
        (2, 4, -1, 1, 9, 17, 15),
        (4, 6, -1, 0, 8, 17, 13),
    ],
    4: [
        (0, 2, -1, 2, 11, 18, 19),
        (2, 4, -1, 1, 9, 17, 16),
        (4, 6, -1, 1, 8, 17, 14),
        (6, 8, -1, 0, 7, 17, 12),
    ],
    5: [
        (0, 2, -1, 2, 11, 18, 20),
        (2, 4, -1, 1, 9, 17, 17),
        (4, 6, -1, 1, 8, 17, 15),
        (6, 8, -1, 1, 7, 17, 13),
        (8, 10, -1, 0, 6, 17, 11),
    ],
}


class TestGearCar(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "gear-car"

    @property
    def generator(self):
        return GearCarGenerator

    def _domain_config(self):
        return GearCarGenerator.get_domain_parameter_space().get_default_configuration()

    def _params(self, **overrides) -> Configuration:
        """A full instance configuration, IPC car unless told otherwise.

        Everything the IPC set fixes is a parameter now, so the defaults are
        the shipped car and an override is a different one.
        """
        gen = GearCarGenerator(self._domain_config())
        space = gen.instance_parameter_space
        values = dict(space.get_default_configuration())
        # Deliberately NOT an IPC instance: the shipped ones ask for hundreds
        # of units of distance and are far too slow for a unit test. This car
        # only has to creep two units forward and stop again.
        values.update({"target_distance": 2, "fuel": 100, "alpha": 1, "beta": 1})
        values.update(overrides)
        return Configuration(space, values)

    def _get_configs(self):
        return [(self._domain_config(), self._params())]

    @property
    def plannable(self):
        # the shipped car, and one the IPC set could not describe: wider gears,
        # a stronger engine and the tightest goal window there is. Against an
        # even target a window of 1 pins the distance exactly, since only even
        # distances are reachable at all.
        return self._get_configs() + [
            (
                self._domain_config(),
                self._params(
                    speed_per_gear=3,
                    max_acceleration=3,
                    min_acceleration=-2,
                    goal_distance_tolerance=1,
                ),
            )
        ]

    @property
    def object_data(self):
        domain_config = self._domain_config()
        return [
            (domain_config, self._params(), [("gear", 2)]),
            # n_gears is no longer capped at the dataset's 5
            (domain_config, self._params(n_gears=8), [("gear", 8)]),
        ]

    @property
    def validation_cases(self):
        # Creep one unit forward, then bleed the speed back off so the car
        # ends stopped, in first gear, with the acceleration back at zero.
        plan = """
        (accelerate g1)
        (drive_aligned_gear g1)
        (decelerate g1)
        (decelerate g1)
        (drive_aligned_gear g1)
        (accelerate g1)
        """
        return [
            (
                self._domain_config(),
                self._params(),
                plan,
                ValidationResultStatus.VALID,
            )
        ]

    @property
    def problem_actions(self):
        domain_config, instance_config = self._get_configs()[0]
        # accelerate, decelerate, gear_up, gear_down and the three drive
        # actions; they are lifted, so the count does not depend on the gears
        return [(domain_config, instance_config, 7)]

    def test_gear_tables_match_the_ipc_set(self):
        """The per-gear tables are computed, so pin them to the shipped values.

        gear_fuel_over depends on how many gears the car has, so every gear
        count the dataset uses is checked, not just one.
        """
        gen = GearCarGenerator(self._domain_config())
        fluents = [
            "gear_v_min",
            "gear_v_max",
            "gear_min_acceleration",
            "gear_max_acceleration",
            "gear_fuel_aligned",
            "gear_fuel_under",
            "gear_fuel_over",
        ]
        for n_gears, expected in IPC_GEAR_TABLES.items():
            problem = gen.get_instance(self._params(n_gears=n_gears))
            init = problem.explicit_initial_values
            for i, row in enumerate(expected):
                gear = problem.object(f"g{i + 1}")
                for name, want in zip(fluents, row):
                    got = init[problem.fluent(name)(gear)]
                    self.assertEqual(
                        got.constant_value(),
                        want,
                        f"{name}(g{i + 1}) with {n_gears} gears",
                    )
            # the top speed the gears add up to, the only global fluent that is
            # computed rather than copied from a parameter
            self.assertEqual(
                init[problem.fluent("max_speed")()].constant_value(), 2 * n_gears
            )

    # NOTE that ANML drops the metric is a property of upbm.io rather than of
    # this domain, so it is tested once in test_io.py instead of here.
    def test_metric_is_kept_in_every_instance(self):
        for domain_config, instance_config in self._get_configs():
            gen = GearCarGenerator(domain_config)
            problem = gen.get_instance(instance_config)
            self.assertEqual(len(problem.quality_metrics), 1)
            self.assertIn("cost", str(problem.quality_metrics[0]))
