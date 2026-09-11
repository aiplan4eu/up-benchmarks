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

from upbm.domains.sailing_wind import SailingWindGenerator
from upbm.domains.sailing_wind.sailing_wind import (
    MAX_INERTIA,
    NO_PERSON,
    POLAR_TABLE,
    RESCUE_HALF_SIZE,
)
from upbm.io import parse_plan_string
from upbm.tests.base_domain_test import BaseDomainTest
from upbm.utils import get_reduced_instance_space


def _domain_config(variant):
    space = SailingWindGenerator.get_domain_parameter_space()
    return Configuration(space, {"version": 1, "variant": variant})


def _value(problem, fluent, object_name):
    """The initial value of a one argument numeric fluent, as a Fraction."""
    target = problem.fluent(fluent)(problem.object(object_name))
    return Fraction(problem.initial_value(target).constant_value())


def _people(problem):
    """Every person's (x, y), as Fractions."""
    return [
        (_value(problem, "x", p.name), _value(problem, "y", p.name))
        for p in problem.objects(problem.user_type("person"))
    ]


class TestSailingWind(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "sailing-wind"

    @property
    def generator(self):
        return SailingWindGenerator

    def _get_configs(self):
        """The first instance of each shipped track, plus a two person one.

        The shipped tracks are reproduced by the `line` and `circle` layouts
        with the inertia each track uses, which is what their defaults hold.
        """
        line = _domain_config("line")
        circle = _domain_config("circle")
        line_space = SailingWindGenerator(line).instance_parameter_space
        circle_space = SailingWindGenerator(circle).instance_parameter_space
        return [
            # sailing-wind-opt/problem_0: one person on the diagonal ramp
            (line, Configuration(line_space, {"step": 0, "inertia": 50})),
            # sailing-wind-sat/problem_0: one person due north
            (
                circle,
                Configuration(
                    circle_space,
                    {"direction_0": 2, "direction_1": NO_PERSON, "inertia": 90},
                ),
            ),
            # sailing-wind-sat/problem_5: two people, north east and south east
            (
                circle,
                Configuration(
                    circle_space,
                    {"direction_0": 1, "direction_1": 7, "inertia": 90},
                ),
            ),
        ]

    def _random_config(self, **overrides):
        """A drawn instance: three people inside a small circle."""
        config = _domain_config("random")
        space = SailingWindGenerator(config).instance_parameter_space
        params = {
            "n_people": 3,
            "max_distance": 40,
            "seed": 1,
            "inertia": 50,
        }
        params.update(overrides)
        return config, Configuration(space, params)

    @property
    def plannable(self):
        # NOTE deliberately empty: sailing-wind is a numeric domain with a
        # continuous state space, and even the smallest shipped instance takes
        # a planner far longer than a unit test should. The domain is exercised
        # with hand written plans in test_sequential_validation instead.
        return []

    @property
    def object_data(self):
        line_0, circle_0, circle_5 = self._get_configs()
        return [
            (*line_0, [("boat", 1), ("person", 1)]),
            (*circle_0, [("boat", 1), ("person", 1)]),
            (*circle_5, [("boat", 1), ("person", 2)]),
            (*self._random_config(), [("boat", 1), ("person", 3)]),
        ]

    @property
    def problem_actions(self):
        # 24 move actions, one per 15 degree heading, plus save_person
        return [
            (*config, 25) for config in self._get_configs() + [self._random_config()]
        ]

    def test_every_variant_shares_one_domain(self):
        """The layout picks where people go, never what the boat can do."""
        generators = [
            SailingWindGenerator(_domain_config(v))
            for v in ("random", "line", "circle")
        ]
        action_names = {tuple(a.name for a in gen.domain.actions) for gen in generators}
        self.assertEqual(len(action_names), 1)

    def test_inertia_is_an_instance_parameter(self):
        """r used to be fixed per track; now any layout can use any boat."""
        for variant in ("random", "line", "circle"):
            gen = SailingWindGenerator(_domain_config(variant))
            self.assertIn("inertia", gen.instance_parameter_space.keys())

        # the defaults still hold what each shipped track used
        for variant, expected in (
            ("line", Fraction(1, 2)),
            ("circle", Fraction(9, 10)),
        ):
            gen = SailingWindGenerator(_domain_config(variant))
            problem = gen.get_instance(
                gen.instance_parameter_space.get_default_configuration()
            )
            self.assertEqual(_value(problem, "r", "b0"), expected)

        # ... and the ramp can now be sailed by the satisficing boat
        gen = SailingWindGenerator(_domain_config("line"))
        problem = gen.get_instance(
            Configuration(gen.instance_parameter_space, {"step": 0, "inertia": 90})
        )
        self.assertEqual(_value(problem, "r", "b0"), Fraction(9, 10))

    def test_inertia_is_written_as_a_plain_number_when_whole(self):
        """0 and 100 per cent are whole numbers, like the dataset writes them."""
        gen = SailingWindGenerator(_domain_config("line"))
        problem = gen.get_instance(
            Configuration(gen.instance_parameter_space, {"step": 0, "inertia": 0})
        )
        self.assertEqual(_value(problem, "r", "b0"), 0)

    def test_initial_state_matches_the_ipc_instances(self):
        """Spot check the values the shipped instances all agree on."""
        domain_config, instance_config = self._get_configs()[0]
        gen = SailingWindGenerator(domain_config)
        problem = gen.get_instance(instance_config)
        boat = problem.object("b0")

        for name, expected in (("x", 0), ("y", 0), ("v", 0), ("sailing-angle", 0)):
            value = problem.initial_value(problem.fluent(name)(boat))
            self.assertEqual(Fraction(value.constant_value()), expected)
        for angle, expected_vmax in POLAR_TABLE.items():
            value = problem.initial_value(problem.fluent(f"vmax_{angle}")(boat))
            self.assertEqual(Fraction(value.constant_value()), expected_vmax)
        # a boat cannot sail straight into the wind
        self.assertEqual(POLAR_TABLE[0], 0)

        # sailing-wind-opt/problem_0 waits for its person at (5, 15.5)
        person = problem.object("p0")
        self.assertEqual(
            Fraction(
                problem.initial_value(problem.fluent("x")(person)).constant_value()
            ),
            Fraction("5"),
        )
        self.assertEqual(
            Fraction(
                problem.initial_value(problem.fluent("y")(person)).constant_value()
            ),
            Fraction("15.5"),
        )
        # `saved` is false by default and is not stated explicitly, exactly as
        # in the shipped files
        saved = problem.fluent("saved")(person)
        self.assertFalse(problem.initial_value(saved).bool_constant_value())
        self.assertNotIn(saved, problem.explicit_initial_values)

    def test_the_line_ramp_and_the_circle(self):
        """The two shipped layouts put their people where the dataset does."""
        line_gen = SailingWindGenerator(_domain_config("line"))
        space = line_gen.instance_parameter_space
        # problem_N of the optimal track puts the person at
        # (5 + 0.4 N, 15.5 + 0.4 N)
        for step, expected in ((0, ("5", "15.5")), (19, ("12.6", "23.1"))):
            problem = line_gen.get_instance(
                Configuration(space, {"step": step, "inertia": 50})
            )
            self.assertEqual(
                _people(problem),
                [(Fraction(expected[0]), Fraction(expected[1]))],
            )

        circle_gen = SailingWindGenerator(_domain_config("circle"))
        space = circle_gen.instance_parameter_space
        # every person of the circle sits on the radius 100 circle, at a
        # multiple of 45 degrees rounded to whole coordinates
        problem = circle_gen.get_instance(
            Configuration(space, {"direction_0": 1, "direction_1": 7, "inertia": 90})
        )
        self.assertEqual(set(_people(problem)), {(71, 71), (71, -71)})

    def test_goal_asks_for_every_person(self):
        for domain_config, instance_config in self._get_configs() + [
            self._random_config()
        ]:
            gen = SailingWindGenerator(domain_config)
            problem = gen.get_instance(instance_config)
            people = list(problem.objects(problem.user_type("person")))
            self.assertEqual(len(problem.goals), len(people))
            self.assertEqual(
                {str(g) for g in problem.goals},
                {f"saved({p.name})" for p in people},
            )

    def test_no_quality_metric(self):
        # the :metric line is commented out in every shipped instance
        for domain_config, instance_config in self._get_configs() + [
            self._random_config()
        ]:
            gen = SailingWindGenerator(domain_config)
            problem = gen.get_instance(instance_config)
            self.assertEqual(list(problem.quality_metrics), [])

    # NOTE the validation cases of the base class use the temporal plan
    # validator, while sailing-wind is an instantaneous domain, so the
    # sequential plans are validated here instead.
    def test_sequential_validation(self):
        domain_config, instance_config = self._get_configs()[0]
        gen = SailingWindGenerator(domain_config)
        problem = gen.get_instance(instance_config)

        # Sail at 15 degrees to pick up speed, then head straight into the wind
        # to bleed it off again: vmax_0 is 0, so move_0 halves the speed while
        # the boat coasts north into the rescue box.
        rescue = ["(move_15 b0)"] * 5 + ["(move_0 b0)", "(save_person b0 p0)"]
        for plan_str, expected in [
            ("\n".join(rescue), ValidationResultStatus.VALID),
            # the boat starts too far south of the person to rescue anybody
            ("(save_person b0 p0)", ValidationResultStatus.INVALID),
            # sailing at 15 degrees without slowing down leaves the boat over
            # the 0.1 speed limit that save_person requires
            (
                "\n".join(["(move_15 b0)"] * 5 + ["(save_person b0 p0)"]),
                ValidationResultStatus.INVALID,
            ),
            # doing nothing never saves anyone
            ("", ValidationResultStatus.INVALID),
        ]:
            plan = parse_plan_string(problem, plan_str)
            with SequentialPlanValidator() as validator:
                v_res = validator.validate(problem, plan)
                self.assertEqual(v_res.status, expected, f"bad res:\n{v_res}")

    def test_effects_use_the_speed_before_the_move(self):
        """A move sets the new speed, but travels at the old one.

        The domain assigns `v` and increases `x` / `y` in the same effect, and
        PDDL evaluates both against the state before the action, so the very
        first move only spins the boat up without displacing it.
        """
        domain_config, instance_config = self._get_configs()[0]
        gen = SailingWindGenerator(domain_config)
        problem = gen.get_instance(instance_config)

        from unified_planning.shortcuts import SequentialSimulator

        boat = problem.object("b0")
        with SequentialSimulator(problem) as sim:
            state = sim.apply(
                sim.get_initial_state(), problem.action("move_15"), (boat,)
            )
            # v = vmax_15 * (1 - r) + r * v = 0.17 * 0.5 = 0.085
            self.assertEqual(
                Fraction(state.get_value(problem.fluent("v")(boat)).constant_value()),
                Fraction("0.085"),
            )
            for coord in ("x", "y"):
                self.assertEqual(
                    Fraction(
                        state.get_value(problem.fluent(coord)(boat)).constant_value()
                    ),
                    0,
                )

    def test_object_universe_covers_both_people(self):
        circle_gen = SailingWindGenerator(_domain_config("circle"))
        universe = circle_gen.object_universe()
        self.assertEqual(sorted(o.name for o in universe), ["b0", "p0", "p1"])
        line_gen = SailingWindGenerator(_domain_config("line"))
        self.assertEqual(
            sorted(o.name for o in line_gen.object_universe()), ["b0", "p0"]
        )
        # the drawn layout is bounded by the space it is given, not by two
        gen = SailingWindGenerator(_domain_config("random"))
        reduced = get_reduced_instance_space(
            gen.instance_parameter_space, {"n_people": 4}
        )
        self.assertEqual(
            sorted(o.name for o in gen.object_universe(reduced)),
            ["b0", "p0", "p1", "p2", "p3"],
        )

    # ---- the "random" layout ----

    def test_drawn_people_land_in_the_circle_and_outside_the_rescue_box(self):
        """Both rejections of the draw, over a sweep of parameters.

        Landing in the circle is what makes `max_distance` mean a distance;
        landing outside the box is what stops a person being rescued where the
        boat already sits, which would need no sailing at all.
        """
        gen = SailingWindGenerator(_domain_config("random"))
        space = gen.instance_parameter_space
        for max_distance in (RESCUE_HALF_SIZE + 1, 30, 100, 1000):
            for seed in range(15):
                params = Configuration(
                    space,
                    {
                        "n_people": 6,
                        "max_distance": max_distance,
                        "seed": seed,
                        "inertia": 50,
                    },
                )
                people = _people(gen.get_instance(params))
                self.assertEqual(len(people), 6)
                for x, y in people:
                    self.assertLessEqual(x * x + y * y, max_distance * max_distance)
                    self.assertTrue(
                        abs(x) > RESCUE_HALF_SIZE or abs(y) > RESCUE_HALF_SIZE
                    )

    def test_the_same_seed_draws_the_same_people(self):
        gen = SailingWindGenerator(_domain_config("random"))

        def drawn(seed):
            return _people(gen.get_instance(self._random_config(seed=seed)[1]))

        self.assertEqual(drawn(3), drawn(3))
        self.assertGreater(len({tuple(drawn(s)) for s in range(10)}), 1)

    def test_the_drawn_layout_is_not_capped_at_two_people(self):
        """The two direction slots of the circle are what set that cap."""
        gen = SailingWindGenerator(_domain_config("random"))
        problem = gen.get_instance(self._random_config(n_people=25)[1])
        self.assertEqual(
            sum(1 for _ in problem.objects(problem.user_type("person"))), 25
        )

    def test_a_boat_that_never_slows_down_is_rejected(self):
        """At r = 1 a move leaves v alone, and the boat starts stopped.

        It therefore never moves, and cannot reach anyone who is not already
        in the rescue box - which no layout puts them in.
        """
        for domain_config, instance_config in self._get_configs() + [
            self._random_config()
        ]:
            gen = SailingWindGenerator(domain_config)
            stuck = Configuration(
                gen.instance_parameter_space,
                dict(instance_config, inertia=MAX_INERTIA),
            )
            self.assertFalse(gen.check_instance_parameters(stuck))
            with self.assertRaises(ValueError):
                gen.get_instance(stuck)
            # one per cent short of it is still fine
            nearly = Configuration(
                gen.instance_parameter_space,
                dict(instance_config, inertia=MAX_INERTIA - 1),
            )
            self.assertTrue(gen.check_instance_parameters(nearly))

    def test_a_drawn_instance_can_be_rescued(self):
        """A drawn person is reached by the same sail as a shipped one.

        At the smallest `max_distance` the only spots left are the four points
        one step outside the rescue box, and this seed picks the northern one,
        so the boat sails north exactly as it does for the shipped ramp.
        """
        gen = SailingWindGenerator(_domain_config("random"))
        problem = gen.get_instance(
            Configuration(
                gen.instance_parameter_space,
                {
                    "n_people": 1,
                    "max_distance": RESCUE_HALF_SIZE + 1,
                    "seed": 3,
                    "inertia": 50,
                },
            )
        )
        self.assertEqual(_people(problem), [(0, RESCUE_HALF_SIZE + 1)])

        # Ten moves at 15 degrees creep the boat to y = 1.32, which is inside
        # the person's box, and one move straight into the wind halves the
        # speed to 0.085 so save_person's 0.1 limit is met.
        climb = ["(move_15 b0)"] * 10
        for plan_str, expected in [
            (
                "\n".join(climb + ["(move_0 b0)", "(save_person b0 p0)"]),
                ValidationResultStatus.VALID,
            ),
            # without shedding the speed first the boat is still too fast
            (
                "\n".join(climb + ["(save_person b0 p0)"]),
                ValidationResultStatus.INVALID,
            ),
            # and stopping short of the box does not reach the person
            (
                "\n".join(
                    ["(move_15 b0)"] * 3 + ["(move_0 b0)"] * 4 + ["(save_person b0 p0)"]
                ),
                ValidationResultStatus.INVALID,
            ),
        ]:
            with SequentialPlanValidator() as validator:
                v_res = validator.validate(
                    problem, parse_plan_string(problem, plan_str)
                )
                self.assertEqual(v_res.status, expected, f"bad res:\n{v_res}")
