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
from unified_planning.engines.plan_validator import (
    SequentialPlanValidator,
    ValidationResultStatus,
)

from upbm.domains.gear_car import GearCarGenerator
from upbm.io import parse_plan_string
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

    def _get_configs(self):
        default_config = (
            GearCarGenerator.get_domain_parameter_space().get_default_configuration()
        )
        gen = GearCarGenerator(default_config)
        space = gen.instance_parameter_space
        # Deliberately NOT an IPC instance: the shipped ones ask for hundreds
        # of units of distance and are far too slow for a unit test. This car
        # only has to creep two units forward and stop again.
        tiny = Configuration(
            space,
            {
                "n_gears": 2,
                "target_distance": 2,
                "fuel": 100,
                "alpha": 1,
                "beta": 1,
            },
        )
        return [(default_config, tiny)]

    @property
    def plannable(self):
        return self._get_configs()

    @property
    def object_data(self):
        domain_config, instance_config = self._get_configs()[0]
        return [(domain_config, instance_config, [("gear", 2)])]

    @property
    def problem_actions(self):
        domain_config, instance_config = self._get_configs()[0]
        # accelerate, decelerate, gear_up, gear_down and the three drive
        # actions; they are lifted, so the count does not depend on the gears
        return [(domain_config, instance_config, 7)]

    def test_sequential_plan_validation(self):
        """Validate a plan by hand.

        The base class validates with TimeTriggeredPlanValidator, which only
        suits temporal domains; gear-car is instantaneous, so it is checked
        here with the sequential validator instead.
        """
        domain_config, instance_config = self._get_configs()[0]
        gen = GearCarGenerator(domain_config)
        problem = gen.get_instance(instance_config)
        # Creep one unit forward, then bleed the speed back off so the car
        # ends stopped, in first gear, with the acceleration back at zero.
        plan = parse_plan_string(
            problem,
            """
            (accelerate g1)
            (drive_aligned_gear g1)
            (decelerate g1)
            (decelerate g1)
            (drive_aligned_gear g1)
            (accelerate g1)
            """,
        )
        with SequentialPlanValidator(problem_kind=problem.kind) as validator:
            res = validator.validate(problem, plan)
            self.assertEqual(res.status, ValidationResultStatus.VALID, f"{res}")

    def test_gear_tables_match_the_ipc_set(self):
        """The per-gear tables are computed, so pin them to the shipped values.

        gear_fuel_over depends on how many gears the car has, so every gear
        count the dataset uses is checked, not just one.
        """
        domain_config = (
            GearCarGenerator.get_domain_parameter_space().get_default_configuration()
        )
        gen = GearCarGenerator(domain_config)
        space = gen.instance_parameter_space
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
            problem = gen.get_instance(
                Configuration(
                    space,
                    {
                        "n_gears": n_gears,
                        "target_distance": 2,
                        "fuel": 100,
                        "alpha": 1,
                        "beta": 1,
                    },
                )
            )
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
            # the top speed the gears add up to
            self.assertEqual(
                init[problem.fluent("max_speed")()].constant_value(), 2 * n_gears
            )

    def test_check_instance_parameters_rejects_too_little_fuel(self):
        """A car that cannot possibly carry enough fuel is refused."""
        domain_config = (
            GearCarGenerator.get_domain_parameter_space().get_default_configuration()
        )
        gen = GearCarGenerator(domain_config)
        space = gen.instance_parameter_space
        base = {"n_gears": 2, "fuel": 100, "alpha": 1, "beta": 1}
        # 100 fuel buys 11 drive steps in first gear, each covering at most
        # 2 * max_speed = 8, so 88 is reachable and 89 is not.
        self.assertTrue(
            gen.check_instance_parameters(
                Configuration(space, {**base, "target_distance": 88})
            )
        )
        self.assertFalse(
            gen.check_instance_parameters(
                Configuration(space, {**base, "target_distance": 89})
            )
        )

    def test_shipped_instances_are_accepted(self):
        """Every instance of the IPC set has to pass the solvability check."""
        domain_config = (
            GearCarGenerator.get_domain_parameter_space().get_default_configuration()
        )
        gen = GearCarGenerator(domain_config)
        space = gen.instance_parameter_space
        # (n_gears, target_distance, fuel) of the 20 shipped instances
        shipped = [
            (2, 50, 200),
            (2, 260, 406),
            (2, 290, 450),
            (2, 320, 482),
            (2, 360, 536),
            (2, 410, 612),
            (3, 470, 456),
            (3, 540, 513),
            (3, 620, 579),
            (3, 710, 648),
            (3, 810, 727),
            (4, 920, 582),
            (4, 1040, 649),
            (4, 1170, 716),
            (4, 1310, 792),
            (4, 1460, 867),
            (5, 1620, 708),
            (5, 1790, 765),
            (5, 1970, 830),
            (5, 2160, 902),
        ]
        for n_gears, target, fuel in shipped:
            config = Configuration(
                space,
                {
                    "n_gears": n_gears,
                    "target_distance": target,
                    "fuel": fuel,
                    "alpha": 1,
                    "beta": 1,
                },
            )
            self.assertTrue(
                gen.check_instance_parameters(config),
                f"shipped instance rejected: {n_gears} gears, d={target}, fuel={fuel}",
            )
