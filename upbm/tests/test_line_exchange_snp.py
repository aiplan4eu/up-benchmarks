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

from fractions import Fraction

from ConfigSpace import Configuration
from unified_planning.engines.plan_validator import SequentialPlanValidator
from unified_planning.engines.results import ValidationResultStatus

from upbm.domains.line_exchange_snp import LineExchangeSnpGenerator
from upbm.domains.line_exchange_snp.line_exchange_snp import MAX_ROBOTS
from upbm.io import parse_plan_string
from upbm.tests.base_domain_test import BaseDomainTest
from upbm.utils import get_reduced_instance_space


def _domain_config():
    space = LineExchangeSnpGenerator.get_domain_parameter_space()
    return space.get_default_configuration()


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

    @property
    def plannable(self):
        # the two robot ones only; the IPC instances are much bigger
        return self._get_configs()[:2]

    @property
    def object_data(self):
        balanced, crossing, shipped = self._get_configs()
        return [
            (*balanced, [("robot", 2)]),
            (*crossing, [("robot", 2)]),
            (*shipped, [("robot", 3)]),
        ]

    @property
    def problem_actions(self):
        # lft, rgt, conn, disc, exch-lre, exch-rle
        return [(*config, 6) for config in self._get_configs()]

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
        for domain_config, instance_config in self._get_configs():
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
