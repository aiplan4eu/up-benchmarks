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

from typing import Any, Dict, List, Tuple

from ConfigSpace import Configuration

from unified_planning.engines.plan_validator import (
    SequentialPlanValidator,
    ValidationResultStatus,
)

from upbm.domains.rainbowttles import RainbowttlesGenerator
from upbm.domains.rainbowttles.rainbowttles import (
    EMPTY_COLOUR,
    bottle_name,
    colour_name,
    filled,
    inverse_moves,
    scramble,
    solved_state,
)
from upbm.io import parse_plan_string
from upbm.tests.base_domain_test import BaseDomainTest


# A small puzzle, well under the smallest shipped one (3 colours, 5 bottles).
SMALL = {
    "capacity": 4,
    "n_colours": 2,
    "bottles_per_colour": 1,
    "n_spare_bottles": 2,
    "scramble_steps": 3,
    "seed": 42,
}

# The shapes the IPC set uses, as (colours, bottles per colour, spares, steps).
# Reproducing their instances is not the goal - their scramble was never
# published - but the shapes are what the domain is known to be interesting at.
IPC_SHAPES = [
    (3, 1, 2, 6),
    (6, 1, 3, 14),
    (8, 2, 3, 32),
    (10, 2, 4, 41),
]


class TestRainbowttles(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self) -> str:
        return "rainbowttles"

    @property
    def generator(self) -> Any:
        return RainbowttlesGenerator

    def _get_configs(self, **overrides) -> Tuple[Configuration, Configuration]:
        domain_space = RainbowttlesGenerator.get_domain_parameter_space()
        domain_config = Configuration(
            domain_space, values={"version": 1, "variant": "random"}
        )
        gen = RainbowttlesGenerator(domain_config)
        values: Dict[str, Any] = dict(SMALL)
        values.update(overrides)
        return domain_config, Configuration(gen.instance_parameter_space, values=values)

    def _gen_and_instance(self, **overrides):
        domain_config, instance_config = self._get_configs(**overrides)
        gen = RainbowttlesGenerator(domain_config)
        return gen, instance_config, gen.get_instance(instance_config)

    def _true_facts(self, problem, fluent_name: str) -> List[Tuple[str, ...]]:
        return [
            tuple(str(a) for a in k.args)
            for k, v in problem.explicit_initial_values.items()
            if k.fluent().name == fluent_name
            and v.is_bool_constant()
            and v.bool_constant_value()
        ]

    def _numbers(self, problem, fluent_name: str) -> Dict[Tuple[str, ...], int]:
        return {
            tuple(str(a) for a in k.args): int(v.constant_value())
            for k, v in problem.explicit_initial_values.items()
            if k.fluent().name == fluent_name and not v.is_bool_constant()
        }

    @property
    def plannable(self) -> List[Tuple[Configuration, Configuration]]:
        # Deliberately smaller than anything the IPC set ships.
        return [self._get_configs()]

    @property
    def object_data(self):
        domain_config, instance_config = self._get_configs()
        # 2 colours x 1 bottle + 2 spares = 4 bottles; colours are the 2
        # playable ones plus the empty marker
        return [(domain_config, instance_config, [("bottle", 4), ("colour", 3)])]

    @property
    def problem_actions(self) -> List[Tuple[Configuration, Configuration, int]]:
        domain_config, instance_config = self._get_configs()
        # pour, pour-to-empty-bottle, close-bottle, close-empty-bottle
        return [(domain_config, instance_config, 4)]

    def test_the_witness_plan_solves_the_instance(self):
        """The point of the whole port: solvability is built in, not checked.

        The scramble is a run of pours walked backwards, so playing them
        forwards and closing every bottle has to reach the goal. This stands
        in for the dataset diff the reproducing ports use - there is nothing
        to diff against here.
        """
        for n_colours, per_colour, spares, steps in IPC_SHAPES:
            for seed in (0, 1, 2):
                gen, params, problem = self._gen_and_instance(
                    n_colours=n_colours,
                    bottles_per_colour=per_colour,
                    n_spare_bottles=spares,
                    scramble_steps=steps,
                    seed=seed,
                )
                plan = parse_plan_string(problem, gen.get_witness_plan(params))
                with SequentialPlanValidator() as validator:
                    result = validator.validate(problem, plan)
                    self.assertEqual(
                        result.status,
                        ValidationResultStatus.VALID,
                        f"{n_colours} colours, seed {seed}: {result}",
                    )

    def test_witness_plan_closes_every_bottle_last(self):
        """The plan is the pours, then one close per bottle."""
        gen, params, problem = self._gen_and_instance()
        lines = gen.get_witness_plan(params).splitlines()
        n_bottles = gen.n_bottles(params)
        pours, closes = lines[:-n_bottles], lines[-n_bottles:]
        self.assertEqual(len(pours), SMALL["scramble_steps"])
        self.assertTrue(all(p.startswith("(pour") for p in pours), pours)
        self.assertTrue(all(c.startswith("(close") for c in closes), closes)
        # every bottle is closed exactly once
        closed = {c.split()[1].rstrip(")") for c in closes}
        self.assertEqual(closed, {bottle_name(i) for i in range(n_bottles)})

    def test_bottle_count_is_derived_from_the_colours(self):
        """n_bottles is not asked for, so it can never be too small."""
        gen, params, problem = self._gen_and_instance(
            n_colours=5, bottles_per_colour=2, n_spare_bottles=3
        )
        self.assertEqual(gen.n_bottles(params), 5 * 2 + 3)
        self.assertEqual(
            sum(1 for _ in problem.objects(problem.user_type("bottle"))), 13
        )

    def test_solved_state_is_full_bottles_plus_spares(self):
        state = solved_state(n_colours=3, bottles_per_colour=2, capacity=4)
        self.assertEqual(len(state), 6)
        self.assertTrue(all(len(s) == 1 and s[0][1] == 4 for s in state))
        # each colour gets exactly bottles_per_colour of them
        for colour in range(3):
            self.assertEqual(sum(1 for s in state if s[0][0] == colour), 2)

    def test_a_colour_never_occupies_two_runs_of_one_bottle(self):
        """The domain cannot represent it, so the scramble must never do it.

        `colour-segments` is one count per (bottle, colour) and `pour` zeroes
        it, so a colour can sit in at most one run per bottle. A scrambler
        that ignored this would emit states the domain cannot express.
        """
        for n_colours, per_colour, spares, steps in IPC_SHAPES:
            for seed in range(5):
                stacks, _ = scramble(
                    n_colours=n_colours,
                    bottles_per_colour=per_colour,
                    capacity=4,
                    n_spare_bottles=spares,
                    steps=steps,
                    seed=seed,
                )
                for stack in stacks:
                    colours = [c for c, _ in stack]
                    self.assertEqual(len(colours), len(set(colours)), stack)
                    self.assertTrue(all(n > 0 for _, n in stack), stack)
                    self.assertLessEqual(filled(stack), 4, stack)

    def test_every_colour_keeps_its_segments(self):
        """Pouring moves segments about but never creates or destroys them."""
        gen, params, problem = self._gen_and_instance(
            n_colours=4, bottles_per_colour=2, n_spare_bottles=3, scramble_steps=20
        )
        segments = self._numbers(problem, "colour-segments")
        for colour in range(4):
            total = sum(v for (_, c), v in segments.items() if c == colour_name(colour))
            self.assertEqual(total, 4 * 2, f"colour {colour_name(colour)}")
        # the empty marker is a colour object but never fills anything
        for (_, c), v in segments.items():
            if c == EMPTY_COLOUR:
                self.assertEqual(v, 0)
        # segments-filled agrees with the per-colour counts
        for bottle, total in self._numbers(problem, "segments-filled").items():
            self.assertEqual(
                total, sum(v for (b, _), v in segments.items() if (b,) == bottle)
            )

    def test_stacks_are_wired_bottom_to_top(self):
        """Each run records the colour it rests on; the bottom one rests on empty."""
        gen, params, problem = self._gen_and_instance(scramble_steps=6)
        below = {(b, c): c1 for b, c, c1 in self._true_facts(problem, "colour-below")}
        upper = {b: c for b, c in self._true_facts(problem, "upper-colour")}
        segments = self._numbers(problem, "colour-segments")
        for index in range(gen.n_bottles(params)):
            bottle = bottle_name(index)
            colour = upper[bottle]
            seen: set = set()
            while colour != EMPTY_COLOUR:
                self.assertNotIn(colour, seen)
                seen.add(colour)
                self.assertGreater(segments[(bottle, colour)], 0)
                colour = below[(bottle, colour)]
            # an empty bottle shows the empty marker and rests on nothing
            if upper[bottle] == EMPTY_COLOUR:
                self.assertNotIn((bottle, EMPTY_COLOUR), below)

    def test_goal_closes_every_bottle(self):
        gen, params, problem = self._gen_and_instance()
        goals = {str(g) for g in problem.goals}
        self.assertEqual(
            goals, {f"closed({bottle_name(i)})" for i in range(gen.n_bottles(params))}
        )

    def test_the_seed_is_a_real_parameter(self):
        """A different seed redraws the puzzle without changing its shape."""
        _, _, first = self._gen_and_instance(seed=1, scramble_steps=8)
        _, _, again = self._gen_and_instance(seed=1, scramble_steps=8)
        _, _, other = self._gen_and_instance(seed=2, scramble_steps=8)

        def state(problem):
            return sorted(
                (str(k), str(v)) for k, v in problem.explicit_initial_values.items()
            )

        self.assertEqual(state(first), state(again))
        self.assertNotEqual(state(first), state(other))
        self.assertEqual(len(list(first.all_objects)), len(list(other.all_objects)))

    def test_a_scramble_never_lands_back_on_a_solved_puzzle(self):
        """A random walk can wander home; those steps are skipped.

        Without the guard roughly one puzzle in two hundred came out already
        solved, which is not a puzzle at all.
        """
        for seed in range(150):
            stacks, undo = scramble(
                n_colours=3,
                bottles_per_colour=1,
                capacity=4,
                n_spare_bottles=2,
                steps=6,
                seed=seed,
            )
            self.assertGreater(len(undo), 0)
            unsorted = [s for s in stacks if s and not (len(s) == 1 and s[0][1] == 4)]
            self.assertTrue(unsorted, f"seed {seed} produced a solved puzzle")

    def test_inverse_moves_respect_the_pour_preconditions(self):
        """Only pours the domain can actually play are ever walked backwards.

        Taking a whole run is only undoable when it emptied the bottle:
        `pour` needs the colour still showing on the bottle it poured onto and
        `pour-to-empty-bottle` needs that bottle to have been empty. Anything
        between the two is not a legal pour at all.
        """
        stacks = [[(0, 2), (1, 1)], [(1, 1)], []]
        moves = inverse_moves(stacks, capacity=4)
        for move in moves:
            source = stacks[move.source]
            colour, run = source[-1]
            self.assertEqual(move.colour, colour)
            self.assertLessEqual(move.take, run)
            if move.take == run:
                # only the whole bottle can go, and then it is emptied
                self.assertEqual(len(source), 1)
                self.assertTrue(move.to_empty_bottle)
            target = stacks[move.target]
            self.assertNotIn(colour, [c for c, _ in target])
            self.assertLessEqual(filled(target) + move.take, 4)
        # Bottle 0's top run is all of colour 1, but the bottle holds another
        # run underneath, so no pour could have produced it: there is nothing
        # to walk back from there.
        self.assertEqual([m for m in moves if m.source == 0], [])
        # That leaves exactly one move in this state - bottle 1 is a single
        # run, so emptying it is a `pour-to-empty-bottle` read backwards, and
        # only the empty bottle can take it since bottle 0 already holds the
        # colour.
        self.assertEqual(len(moves), 1)
        only = moves[0]
        self.assertEqual(
            (only.source, only.target, only.colour, only.take, only.to_empty_bottle),
            (1, 2, 1, 1, True),
        )
        # it lands on an empty bottle, so there is no colour below it
        self.assertIsNone(only.below)

    def test_every_configuration_is_accepted(self):
        """There is nothing to reject: solvability is built in, not inherited.

        The bottle count is derived rather than asked for and the space starts
        at one spare bottle and a capacity of two, so no configuration can
        describe a puzzle that cannot be built or solved.
        """
        domain_config, _ = self._get_configs()
        gen = RainbowttlesGenerator(domain_config)
        for overrides in (
            {},
            {"capacity": 2, "n_colours": 1, "n_spare_bottles": 1, "scramble_steps": 0},
            {"n_colours": 10, "bottles_per_colour": 2, "n_spare_bottles": 4},
        ):
            _, params = self._get_configs(**overrides)
            self.assertTrue(gen.check_instance_parameters(params), overrides)
