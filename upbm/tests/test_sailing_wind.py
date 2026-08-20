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
from upbm.domains.sailing_wind.sailing_wind import NO_PERSON, POLAR_TABLE
from upbm.io import parse_plan_string
from upbm.tests.base_domain_test import BaseDomainTest


def _domain_config(variant):
    space = SailingWindGenerator.get_domain_parameter_space()
    return Configuration(space, {"version": 1, "variant": variant})


class TestSailingWind(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "sailing-wind"

    @property
    def generator(self):
        return SailingWindGenerator

    def _get_configs(self):
        """The first instance of each shipped track, plus a two person one."""
        opt = _domain_config("opt")
        sat = _domain_config("sat")
        opt_space = SailingWindGenerator(opt).instance_parameter_space
        sat_space = SailingWindGenerator(sat).instance_parameter_space
        return [
            # sailing-wind-opt/problem_0: one person on the diagonal ramp
            (opt, Configuration(opt_space, {"step": 0})),
            # sailing-wind-sat/problem_0: one person due north
            (
                sat,
                Configuration(sat_space, {"direction_0": 2, "direction_1": NO_PERSON}),
            ),
            # sailing-wind-sat/problem_5: two people, north east and south east
            (sat, Configuration(sat_space, {"direction_0": 1, "direction_1": 7})),
        ]

    @property
    def plannable(self):
        # NOTE deliberately empty: sailing-wind is a numeric domain with a
        # continuous state space, and even the smallest shipped instance takes
        # a planner far longer than a unit test should. The domain is exercised
        # with hand written plans in test_sequential_validation instead.
        return []

    @property
    def object_data(self):
        opt_0, sat_0, sat_5 = self._get_configs()
        return [
            (*opt_0, [("boat", 1), ("person", 1)]),
            (*sat_0, [("boat", 1), ("person", 1)]),
            (*sat_5, [("boat", 1), ("person", 2)]),
        ]

    @property
    def problem_actions(self):
        # 24 move actions, one per 15 degree heading, plus save_person
        return [(*config, 25) for config in self._get_configs()]

    def test_variants_only_differ_in_inertia(self):
        """Both tracks share one domain file; r is what tells them apart."""
        opt_c, sat_c = _domain_config("opt"), _domain_config("sat")
        opt_gen, sat_gen = (
            SailingWindGenerator(opt_c),
            SailingWindGenerator(sat_c),
        )
        self.assertEqual(
            [a.name for a in opt_gen.domain.actions],
            [a.name for a in sat_gen.domain.actions],
        )
        opt_p = opt_gen.get_instance(
            Configuration(opt_gen.instance_parameter_space, {"step": 0})
        )
        sat_p = sat_gen.get_instance(
            Configuration(
                sat_gen.instance_parameter_space,
                {"direction_0": 2, "direction_1": NO_PERSON},
            )
        )
        for problem, expected in ((opt_p, Fraction(1, 2)), (sat_p, Fraction(9, 10))):
            r = problem.fluent("r")(problem.object("b0"))
            self.assertEqual(
                Fraction(problem.initial_value(r).constant_value()), expected
            )

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

    def test_opt_ramp_and_sat_circle(self):
        """The two tracks lay their people out in the two shipped patterns."""
        opt_gen = SailingWindGenerator(_domain_config("opt"))
        space = opt_gen.instance_parameter_space
        # problem_N of the opt track puts the person at (5 + 0.4 N, 15.5 + 0.4 N)
        for step, expected in ((0, ("5", "15.5")), (19, ("12.6", "23.1"))):
            problem = opt_gen.get_instance(Configuration(space, {"step": step}))
            person = problem.object("p0")
            for fluent, value in zip(("x", "y"), expected):
                self.assertEqual(
                    Fraction(
                        problem.initial_value(
                            problem.fluent(fluent)(person)
                        ).constant_value()
                    ),
                    Fraction(value),
                )

        sat_gen = SailingWindGenerator(_domain_config("sat"))
        space = sat_gen.instance_parameter_space
        # every sat person sits on the radius 100 circle, at a multiple of 45
        # degrees rounded to whole coordinates
        problem = sat_gen.get_instance(
            Configuration(space, {"direction_0": 1, "direction_1": 7})
        )
        positions = {
            (
                int(problem.initial_value(problem.fluent("x")(p)).constant_value()),
                int(problem.initial_value(problem.fluent("y")(p)).constant_value()),
            )
            for p in problem.objects(problem.user_type("person"))
        }
        self.assertEqual(positions, {(71, 71), (71, -71)})

    def test_goal_asks_for_every_person(self):
        for domain_config, instance_config in self._get_configs():
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
        for domain_config, instance_config in self._get_configs():
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
        sat_gen = SailingWindGenerator(_domain_config("sat"))
        universe = sat_gen.object_universe()
        self.assertEqual(sorted(o.name for o in universe), ["b0", "p0", "p1"])
        opt_gen = SailingWindGenerator(_domain_config("opt"))
        self.assertEqual(
            sorted(o.name for o in opt_gen.object_universe()), ["b0", "p0"]
        )
