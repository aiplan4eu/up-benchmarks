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

from ConfigSpace import Configuration, ConfigurationSpace, Constant, Integer
from unified_planning.engines.plan_validator import (
    SequentialPlanValidator,
    ValidationResultStatus,
)

from upbm.domains.factory_robot import FactoryRobotGenerator
from upbm.domains.factory_robot.factory_robot import draw, stations
from upbm.io import parse_plan_string
from upbm.tests.base_domain_test import BaseDomainTest


# Two shipped instances read straight off the dataset files, used to pin the
# reconstructed RNG. If the call sequence in `draw` ever drifts, these break.
IPC_PFILE1 = dict(
    args=(2, 5, 40, 20, 42),
    capacity=[80, 80],
    energy=[79, 80],
    work_cost=[12, 10],
    max_temp=[21, 21],
    efficiency=[4, 2],
    cooling_power=6,
    at=["assembly1", "cooling"],
    workload_goal=[38, 39],
)
IPC_PFILE10 = dict(
    args=(6, 9, 70, 30, 42),
    capacity=[80, 80, 120, 100, 100, 100],
    energy=[76, 74, 110, 97, 98, 88],
    work_cost=[8, 8, 15, 8, 8, 8],
    max_temp=[31, 31, 34, 34, 30, 34],
    efficiency=[2, 4, 4, 4, 4, 3],
    cooling_power=4,
    at=["assembly3", "assembly0", "assembly6", "assembly1", "cooling", "charging"],
    workload_goal=[68, 70, 70, 72, 70, 68],
)

# The 20 shipped (n_robots, n_stations, workload, max_temp) calls.
IPC_CALLS = [
    (2, 5, 40, 20),
    (2, 5, 40, 20),
    (3, 6, 40, 20),
    (3, 6, 45, 20),
    (4, 7, 45, 25),
    (4, 7, 50, 25),
    (5, 8, 50, 25),
    (5, 8, 60, 30),
    (6, 9, 60, 30),
    (6, 9, 70, 30),
    (7, 10, 70, 35),
    (7, 10, 80, 35),
    (8, 11, 80, 35),
    (8, 11, 90, 35),
    (9, 12, 90, 40),
    (9, 12, 100, 40),
    (10, 13, 100, 40),
    (10, 13, 120, 40),
    (12, 14, 120, 50),
    (12, 14, 130, 50),
]


class TestFactoryRobot(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "factory-robot"

    @property
    def generator(self):
        return FactoryRobotGenerator

    def _gen(self):
        domain_config = (
            FactoryRobotGenerator.get_domain_parameter_space().get_default_configuration()
        )
        return domain_config, FactoryRobotGenerator(domain_config)

    def _config(self, gen, n_robots, n_stations, workload, max_temp, seed=42):
        return Configuration(
            gen.instance_parameter_space,
            {
                "n_robots": n_robots,
                "n_stations": n_stations,
                "workload": workload,
                "max_temp": max_temp,
                "seed": seed,
            },
        )

    def _get_configs(self):
        domain_config, gen = self._gen()
        # Deliberately NOT an IPC instance: the shipped ones run 2 to 12
        # robots against workload targets in the dozens. This is one robot
        # that has to complete five tasks.
        tiny = self._config(gen, n_robots=1, n_stations=3, workload=3, max_temp=20)
        return [(domain_config, tiny)]

    @property
    def plannable(self):
        return self._get_configs()

    @property
    def object_data(self):
        domain_config, instance_config = self._get_configs()[0]
        return [(domain_config, instance_config, [("robot", 1), ("station", 3)])]

    @property
    def problem_actions(self):
        domain_config, instance_config = self._get_configs()[0]
        # recharge, work, cool-down, the four set-*-power actions, overdrive,
        # overcharge, precision-work, move, turbo-work, calibrate; they are
        # lifted, so the count does not depend on the factory size
        return [(domain_config, instance_config, 13)]

    def test_sequential_plan_validation(self):
        """Run one robot through the whole cycle by hand.

        The base class validates with TimeTriggeredPlanValidator, which only
        suits temporal domains; factory-robot is instantaneous, so it is
        checked here with the sequential validator instead.

        The plan works, cools off, moves, works again, recharges and finishes
        the last task, which touches every mechanic the goal depends on. The
        robot starts on the cooling station with 77 energy and work-cost 8,
        and each work adds 1 workload and 3 temperature.
        """
        domain_config, gen = self._gen()
        config = self._config(gen, n_robots=1, n_stations=3, workload=3, max_temp=20)
        problem = gen.get_instance(config)
        plan = parse_plan_string(
            problem,
            """
            (work r0 cooling)
            (work r0 cooling)
            (cool-down r0 cooling)
            (move r0 cooling assembly0)
            (work r0 assembly0)
            (work r0 assembly0)
            (move r0 assembly0 charging)
            (recharge r0 charging)
            (work r0 charging)
            """,
        )
        with SequentialPlanValidator(problem_kind=problem.kind) as validator:
            res = validator.validate(problem, plan)
            self.assertEqual(res.status, ValidationResultStatus.VALID, f"{res}")

    def test_reconstructed_generator_matches_the_ipc_set(self):
        """The random data is reconstructed, so pin it to the shipped files.

        The original generate.py was never published; `draw` is a
        reconstruction of it. These are the values read off two of the shipped
        instances, one small and one large, so any drift in the call sequence
        shows up here rather than in a silently different benchmark.
        """
        for shipped in (IPC_PFILE1, IPC_PFILE10):
            data = draw(*shipped["args"])
            for field in (
                "capacity",
                "energy",
                "work_cost",
                "max_temp",
                "efficiency",
                "cooling_power",
                "at",
                "workload_goal",
            ):
                self.assertEqual(
                    getattr(data, field),
                    shipped[field],
                    f"{field} for robots={shipped['args'][0]}",
                )

    def test_stations_form_a_clique(self):
        """Connectivity is a full clique, both ways, with no self loops."""
        _, gen = self._gen()
        problem = gen.get_instance(self._config(gen, 3, 6, 40, 20))
        connected = {
            (str(k.args[0]), str(k.args[1]))
            for k, v in problem.explicit_initial_values.items()
            if k.fluent().name == "connected" and v.bool_constant_value()
        }
        places = stations(6)
        self.assertEqual(connected, {(a, b) for a in places for b in places if a != b})

    def test_free_is_every_unoccupied_station(self):
        """Free stations are the ones nobody stands on, charging included."""
        _, gen = self._gen()
        for n_robots, n_stations in ((2, 5), (6, 9)):
            problem = gen.get_instance(self._config(gen, n_robots, n_stations, 40, 20))
            init = problem.explicit_initial_values
            occupied = {
                str(k.args[1])
                for k, v in init.items()
                if k.fluent().name == "at" and v.bool_constant_value()
            }
            free = {
                str(k.args[0])
                for k, v in init.items()
                if k.fluent().name == "free" and v.bool_constant_value()
            }
            self.assertEqual(len(occupied), n_robots)
            self.assertEqual(free, set(stations(n_stations)) - occupied)

    def test_only_the_cooling_station_cools(self):
        """cooling-power is on every station but nonzero only on `cooling`."""
        _, gen = self._gen()
        problem = gen.get_instance(self._config(gen, 2, 5, 40, 20))
        power = {
            str(k.args[0]): v.constant_value()
            for k, v in problem.explicit_initial_values.items()
            if k.fluent().name == "cooling-power"
        }
        self.assertEqual(set(power), set(stations(5)))
        self.assertEqual(power["cooling"], IPC_PFILE1["cooling_power"])
        for place, value in power.items():
            if place != "cooling":
                self.assertEqual(value, 0, place)

    def test_robots_start_calibrated_and_idle(self):
        """Every robot starts calibrated with the three counters at zero."""
        _, gen = self._gen()
        problem = gen.get_instance(self._config(gen, 4, 7, 45, 25))
        init = problem.explicit_initial_values
        for i in range(4):
            robot = problem.object(f"r{i}")
            self.assertTrue(
                init[problem.fluent("calibrated")(robot)].bool_constant_value()
            )
            for fluent in ("workload", "temperature", "production"):
                self.assertEqual(
                    init[problem.fluent(fluent)(robot)].constant_value(), 0, fluent
                )
        # the charger and the calibrator sit on their own stations
        self.assertTrue(
            init[
                problem.fluent("has-charger")(problem.object("charging"))
            ].bool_constant_value()
        )
        self.assertTrue(
            init[
                problem.fluent("has-calibrator")(problem.object("cooling"))
            ].bool_constant_value()
        )

    def test_goal_is_a_target_per_robot_plus_one_temperature_bound(self):
        """Every shipped goal has this shape: n targets and a single bound."""
        _, gen = self._gen()
        goals = gen.get_goal(self._config(gen, *IPC_PFILE1["args"][:4]))
        expected = [
            f"({target} <= workload(r{i}))"
            for i, target in enumerate(IPC_PFILE1["workload_goal"])
        ]
        # the temperature bound is on r0 only, and uses the max_temp argument
        # rather than r0's own drawn max-temp (21 here, not 20)
        expected.append("(temperature(r0) <= 20)")
        self.assertEqual([str(g) for g in goals], expected)

    def test_stations_must_outnumber_robots(self):
        """With no spare station nobody can ever move, so it is refused."""
        _, gen = self._gen()
        self.assertTrue(gen.check_instance_parameters(self._config(gen, 3, 4, 40, 20)))
        crowded = self._config(gen, 3, 3, 40, 20)
        self.assertFalse(gen.check_instance_parameters(crowded))
        with self.assertRaises(ValueError):
            gen.get_instance(crowded)
        # one robot with a charging and a cooling station is the smallest
        # legal factory: the robot always has somewhere to move to
        self.assertTrue(gen.check_instance_parameters(self._config(gen, 1, 2, 40, 20)))

    def test_shipped_instances_are_accepted(self):
        """Every call of the IPC set has to pass the solvability check."""
        _, gen = self._gen()
        for n_robots, n_stations, workload, max_temp in IPC_CALLS:
            self.assertTrue(
                gen.check_instance_parameters(
                    self._config(gen, n_robots, n_stations, workload, max_temp)
                ),
                f"shipped call rejected: {n_robots} robots, {n_stations} stations",
            )

    def test_the_seed_is_a_real_parameter(self):
        """A different seed redraws the factory but keeps its shape."""
        _, gen = self._gen()
        ipc = gen.get_instance(self._config(gen, 6, 9, 70, 30, seed=42))
        other = gen.get_instance(self._config(gen, 6, 9, 70, 30, seed=7))
        self.assertEqual(len(list(ipc.all_objects)), len(list(other.all_objects)))
        capacities = lambda p: [
            v.constant_value()
            for k, v in p.explicit_initial_values.items()
            if k.fluent().name == "capacity"
        ]
        self.assertNotEqual(sorted(capacities(ipc)), sorted(capacities(other)))

    def test_object_universe_is_bounded_by_the_space(self):
        """The universe follows the upper bounds of the given space."""
        _, gen = self._gen()
        space = ConfigurationSpace(
            {
                "n_robots": Integer("n_robots", (1, 4)),
                "n_stations": Integer("n_stations", (2, 7)),
                "workload": Constant("workload", 40),
                "max_temp": Constant("max_temp", 20),
                "seed": Constant("seed", 42),
            }
        )
        names = [o.name for o in gen.object_universe(space)]
        self.assertEqual(names[:4], ["r0", "r1", "r2", "r3"])
        self.assertEqual(names[4:], stations(7))
