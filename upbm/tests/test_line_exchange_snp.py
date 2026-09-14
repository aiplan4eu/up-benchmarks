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

import statistics
from fractions import Fraction

from ConfigSpace import Configuration
from unified_planning.engines.plan_validator import SequentialPlanValidator
from unified_planning.engines.results import ValidationResultStatus

from upbm.domains.line_exchange_snp import LineExchangeSnpGenerator
from upbm.domains.line_exchange_snp.line_exchange_snp import MAX_ROBOTS
from upbm.io import parse_plan_string
from upbm.tests.base_domain_test import BaseDomainTest
from upbm.utils import get_reduced_instance_space, hyperparam_range


def _domain_config(variant="ipc"):
    space = LineExchangeSnpGenerator.get_domain_parameter_space()
    return Configuration(space, {"version": 1, "variant": variant})


def _instance(gen, **params):
    full = {
        "n_robots": 3,
        "segment_length": 50,
        "q_0": 3,
        "q_1": 6,
        "q_2": 6,
        "q_3": 0,
        "q_4": 0,
    }
    full.update(params)
    return Configuration(gen.instance_parameter_space, full)


def _random_instance(gen, **params):
    full = {
        "n_robots": 3,
        "segment_length": 50,
        "mean_load": 10,
        "imbalance": 50,
        "seed": 42,
    }
    full.update(params)
    return Configuration(gen.instance_parameter_space, full)


def _loads_of(problem, n_robots):
    q = problem.fluent("q")
    return [
        int(problem.initial_value(q(problem.object(f"r{i}"))).constant_value())
        for i in range(n_robots)
    ]


class TestLineExchangeSnp(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "line-exchange-snp"

    @property
    def generator(self):
        return LineExchangeSnpGenerator

    def _get_configs(self):
        config = _domain_config()
        gen = LineExchangeSnpGenerator(config)
        return [
            # already balanced, so the empty plan solves it
            (config, _instance(gen, n_robots=2, segment_length=10, q_0=2, q_1=2)),
            # one unit has to cross, which needs a meeting and an exchange
            (config, _instance(gen, n_robots=2, segment_length=10, q_0=3, q_1=1)),
            # the shipped instance named 3_5_50_50
            (config, _instance(gen)),
        ]

    def _random_config(self):
        """A drawn instance small enough to plan on.

        With these parameters the scramble hands out [3, 1], so one unit still
        has to cross, and the segments are short enough that the walk is too.
        """
        config = _domain_config("random")
        gen = LineExchangeSnpGenerator(config)
        return (
            config,
            _random_instance(
                gen, n_robots=2, segment_length=2, mean_load=2, imbalance=50, seed=2
            ),
        )

    @property
    def plannable(self):
        # the two robot ones only; the IPC instances are much bigger
        return self._get_configs()[:2] + [self._random_config()]

    @property
    def object_data(self):
        balanced, crossing, shipped = self._get_configs()
        return [
            (*balanced, [("robot", 2)]),
            (*crossing, [("robot", 2)]),
            (*shipped, [("robot", 3)]),
            (*self._random_config(), [("robot", 2)]),
        ]

    @property
    def problem_actions(self):
        # lft, rgt, conn, disc, exch-lre, exch-rle
        return [
            (*config, 6) for config in self._get_configs() + [self._random_config()]
        ]

    def test_robots_start_in_the_middle_of_their_segment(self):
        """Every shipped instance puts robot i at D/2 + i*D."""
        gen = LineExchangeSnpGenerator(_domain_config())
        problem = gen.get_instance(_instance(gen, n_robots=3, segment_length=50))
        x, index = problem.fluent("x"), problem.fluent("i")
        for i, expected in enumerate((25, 75, 125)):
            robot = problem.object(f"r{i}")
            self.assertEqual(
                Fraction(problem.initial_value(x(robot)).constant_value()), expected
            )
            self.assertEqual(
                Fraction(problem.initial_value(index(robot)).constant_value()), i
            )
        self.assertEqual(
            Fraction(problem.initial_value(problem.fluent("d")()).constant_value()), 50
        )

    def test_an_odd_segment_length_gives_a_half_way_start(self):
        """D/2 is kept exact rather than rounded."""
        gen = LineExchangeSnpGenerator(_domain_config())
        problem = gen.get_instance(
            _instance(gen, n_robots=2, segment_length=5, q_0=1, q_1=1)
        )
        x = problem.fluent("x")
        self.assertEqual(
            Fraction(problem.initial_value(x(problem.object("r0"))).constant_value()),
            Fraction(5, 2),
        )

    def test_next_is_a_chain(self):
        gen = LineExchangeSnpGenerator(_domain_config())
        problem = gen.get_instance(_instance(gen, n_robots=3))
        nxt = problem.fluent("next")
        links = {
            (f.args[0].object().name, f.args[1].object().name)
            for f, v in problem.explicit_initial_values.items()
            if f.fluent() == nxt and v.bool_constant_value()
        }
        self.assertEqual(links, {("r0", "r1"), ("r1", "r2")})

    def test_robots_start_free_and_unpaired(self):
        """ps and pd default to false and are not stated, as in the dataset."""
        gen = LineExchangeSnpGenerator(_domain_config())
        problem = gen.get_instance(_instance(gen, n_robots=3))
        ps, pd = problem.fluent("ps"), problem.fluent("pd")
        stated = {f.fluent() for f in problem.explicit_initial_values}
        self.assertNotIn(ps, stated)
        self.assertNotIn(pd, stated)
        self.assertFalse(
            problem.initial_value(ps(problem.object("r0"))).bool_constant_value()
        )

    def test_goal_restores_positions_and_levels_the_loads(self):
        gen = LineExchangeSnpGenerator(_domain_config())
        problem = gen.get_instance(_instance(gen, n_robots=3, segment_length=50))
        goals = {str(g) for g in problem.goals}
        self.assertEqual(
            goals,
            {
                "(x(r0) == 25)",
                "(x(r1) == 75)",
                "(x(r2) == 125)",
                "(q(r0) == q(r1))",
                "(q(r1) == q(r2))",
            },
        )

    def test_unequal_split_is_rejected(self):
        """An exchange conserves the total, so it has to divide evenly."""
        gen = LineExchangeSnpGenerator(_domain_config())
        # 3 + 1 + 1 = 5 cannot be split three ways
        bad = _instance(gen, n_robots=3, q_0=3, q_1=1, q_2=1)
        self.assertFalse(gen.check_instance_parameters(bad))
        with self.assertRaises(ValueError):
            gen.get_instance(bad)
        # 3 + 6 + 6 = 15 can
        self.assertTrue(gen.check_instance_parameters(_instance(gen)))

    def test_unused_load_slots_are_ignored(self):
        """q slots at or above n_robots do not change the instance."""
        gen = LineExchangeSnpGenerator(_domain_config())
        a = gen.get_instance(_instance(gen, n_robots=2, q_0=2, q_1=2, q_4=999))
        b = gen.get_instance(_instance(gen, n_robots=2, q_0=2, q_1=2, q_4=0))
        self.assertEqual(
            {str(f): str(v) for f, v in a.explicit_initial_values.items()},
            {str(f): str(v) for f, v in b.explicit_initial_values.items()},
        )

    def test_no_quality_metric(self):
        for domain_config, instance_config in self._get_configs() + [
            self._random_config()
        ]:
            gen = LineExchangeSnpGenerator(domain_config)
            self.assertEqual(
                list(gen.get_instance(instance_config).quality_metrics), []
            )

    def test_object_universe_is_bounded_by_the_space(self):
        gen = LineExchangeSnpGenerator(_domain_config())
        reduced = get_reduced_instance_space(
            gen.instance_parameter_space, {"n_robots": 3}
        )
        self.assertEqual(
            sorted(o.name for o in gen.object_universe(reduced)), ["r0", "r1", "r2"]
        )
        self.assertEqual(len(list(gen.object_universe())), MAX_ROBOTS)

    # NOTE the validation cases of the base class use the temporal plan
    # validator, while line-exchange is an instantaneous domain, so the
    # sequential plans are validated here instead.
    def test_sequential_validation(self):
        gen = LineExchangeSnpGenerator(_domain_config())
        problem = gen.get_instance(
            _instance(gen, n_robots=2, segment_length=10, q_0=3, q_1=1)
        )

        # r0 owns [0, 10] and starts at 5, r1 owns [10, 20] and starts at 15.
        # The only place they can meet is the boundary at 10, so both walk
        # there, connect, pass one unit across, split up and walk home again.
        meet = ["(rgt r0)"] * 5 + ["(lft r1)"] * 5
        home = ["(lft r0)"] * 5 + ["(rgt r1)"] * 5
        full = meet + ["(conn r0 r1)", "(exch-lre r0 r1)", "(disc r0 r1)"] + home

        for plan_str, expected in [
            ("\n".join(full), ValidationResultStatus.VALID),
            # exchanging without connecting first is not allowed
            (
                "\n".join(meet + ["(exch-lre r0 r1)"] + home),
                ValidationResultStatus.INVALID,
            ),
            # meeting and exchanging but never walking home misses the goal
            (
                "\n".join(meet + ["(conn r0 r1)", "(exch-lre r0 r1)", "(disc r0 r1)"]),
                ValidationResultStatus.INVALID,
            ),
            # the loads start uneven, so doing nothing cannot work
            ("", ValidationResultStatus.INVALID),
        ]:
            plan = parse_plan_string(problem, plan_str)
            with SequentialPlanValidator() as validator:
                v_res = validator.validate(problem, plan)
                self.assertEqual(v_res.status, expected, f"bad res:\n{v_res}")

    def test_already_balanced_needs_no_plan(self):
        gen = LineExchangeSnpGenerator(_domain_config())
        problem = gen.get_instance(
            _instance(gen, n_robots=2, segment_length=10, q_0=2, q_1=2)
        )
        with SequentialPlanValidator() as validator:
            v_res = validator.validate(problem, parse_plan_string(problem, ""))
            self.assertEqual(v_res.status, ValidationResultStatus.VALID, f"{v_res}")

    # ---- the "random" variant ----

    def test_the_variants_ask_for_different_parameters(self):
        """The load slots belong to "ipc" and the draw knobs to "random"."""
        ipc = LineExchangeSnpGenerator(_domain_config()).instance_parameter_space
        rnd = LineExchangeSnpGenerator(
            _domain_config("random")
        ).instance_parameter_space
        self.assertEqual(
            sorted(ipc.keys()),
            ["n_robots", "q_0", "q_1", "q_2", "q_3", "q_4", "segment_length"],
        )
        self.assertEqual(
            sorted(rnd.keys()),
            ["imbalance", "mean_load", "n_robots", "seed", "segment_length"],
        )

    def test_drawn_loads_always_average_the_mean(self):
        """The scramble conserves the total, so the split is always even.

        This is the whole point of asking for a mean rather than for totals:
        the one solvability condition of the domain holds by construction, so
        check_instance_parameters can never reject a drawn instance.
        """
        gen = LineExchangeSnpGenerator(_domain_config("random"))
        for n_robots in (2, 3, 5, 9):
            for mean_load in (0, 1, 7, 20):
                for imbalance in (0, 25, 90, 250):
                    for seed in range(10):
                        params = _random_instance(
                            gen,
                            n_robots=n_robots,
                            mean_load=mean_load,
                            imbalance=imbalance,
                            seed=seed,
                        )
                        loads = gen._loads(params)
                        self.assertEqual(len(loads), n_robots)
                        self.assertEqual(sum(loads), n_robots * mean_load)
                        # a robot can never hand over more than it holds
                        self.assertGreaterEqual(min(loads), 0)
                        self.assertTrue(gen.check_instance_parameters(params))

    def test_the_same_seed_draws_the_same_loads(self):
        gen = LineExchangeSnpGenerator(_domain_config("random"))

        def loads(seed):
            return _loads_of(
                gen.get_instance(_random_instance(gen, n_robots=5, seed=seed)), 5
            )

        self.assertEqual(loads(7), loads(7))
        # and different seeds are actually different draws
        self.assertGreater(len({tuple(loads(s)) for s in range(10)}), 1)

    def test_more_imbalance_spreads_the_loads_further(self):
        """imbalance is a difficulty dial, not a label.

        It caps how much one transfer may move, so it does not pin the spread
        of any single draw - the shipped set has an imbalance=90 instance
        holding [10, 9, 11] - but it does drive it on average.
        """
        gen = LineExchangeSnpGenerator(_domain_config("random"))

        def average_spread(imbalance):
            spreads = []
            for seed in range(50):
                loads = gen._loads(
                    _random_instance(gen, n_robots=5, imbalance=imbalance, seed=seed)
                )
                spreads.append(max(loads) - min(loads))
            return statistics.mean(spreads)

        spreads = [average_spread(i) for i in (0, 25, 50, 90)]
        self.assertEqual(spreads[0], 0)
        self.assertEqual(spreads, sorted(spreads))

    def test_no_imbalance_starts_at_the_goal(self):
        """imbalance 0 gives every robot the mean, which is already the goal."""
        gen = LineExchangeSnpGenerator(_domain_config("random"))
        problem = gen.get_instance(
            _random_instance(gen, n_robots=4, mean_load=7, imbalance=0)
        )
        self.assertEqual(_loads_of(problem, 4), [7, 7, 7, 7])
        with SequentialPlanValidator() as validator:
            v_res = validator.validate(problem, parse_plan_string(problem, ""))
            self.assertEqual(v_res.status, ValidationResultStatus.VALID, f"{v_res}")

    def test_random_lifts_the_robot_cap(self):
        """Without a slot per robot there is no reason to stop at MAX_ROBOTS."""
        gen = LineExchangeSnpGenerator(_domain_config("random"))
        n_robots = MAX_ROBOTS + 7
        problem = gen.get_instance(_random_instance(gen, n_robots=n_robots))
        self.assertEqual(
            sum(1 for _ in problem.objects(problem.user_type("robot"))), n_robots
        )
        # the ipc variant cannot describe that many
        ipc = LineExchangeSnpGenerator(_domain_config())
        self.assertEqual(
            hyperparam_range(ipc.instance_parameter_space["n_robots"])[1], MAX_ROBOTS
        )

    def test_the_scramble_is_a_witness_plan(self):
        """Undoing the scramble solves the instance.

        The draw moves units between neighbours, which is what `exch` does, so
        putting them back is a plan. This is the smallest case: the scramble
        hands r0 one of r1's units, and the plan hands it back.
        """
        domain_config, instance_config = self._random_config()
        gen = LineExchangeSnpGenerator(domain_config)
        problem = gen.get_instance(instance_config)
        self.assertEqual(_loads_of(problem, 2), [3, 1])

        # r0 owns [0, 2] and starts at 1, r1 owns [2, 4] and starts at 3, so
        # they meet at 2, hand the extra unit back, and walk home again.
        plan = [
            "(rgt r0)",
            "(lft r1)",
            "(conn r0 r1)",
            "(exch-lre r0 r1)",
            "(disc r0 r1)",
            "(lft r0)",
            "(rgt r1)",
        ]
        with SequentialPlanValidator() as validator:
            v_res = validator.validate(
                problem, parse_plan_string(problem, "\n".join(plan))
            )
            self.assertEqual(v_res.status, ValidationResultStatus.VALID, f"{v_res}")
