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
        # the bottle count is derived from the colours rather than asked for,
        # so it can never be too small: colours x bottles_per_colour + spares.
        # Colours are the playable ones plus the empty marker.
        bigger_domain, bigger = self._get_configs(
            n_colours=5, bottles_per_colour=2, n_spare_bottles=3
        )
        return [
            # 2 x 1 + 2 = 4 bottles
            (domain_config, instance_config, [("bottle", 4), ("colour", 3)]),
            # 5 x 2 + 3 = 13 bottles
            (bigger_domain, bigger, [("bottle", 13), ("colour", 6)]),
        ]

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

    def test_the_drawn_puzzle_is_well_formed(self):
        """The invariants every scrambled puzzle has to satisfy.

        They live at two levels. On the stacks the scramble builds: a colour
        occupies at most one run per bottle, because `colour-segments` is a
        single count per (bottle, colour) and `pour` zeroes it, so anything
        else is a state the domain cannot express. On the instance that comes
        out: pouring moves segments without creating or destroying them, every
        stack is wired bottom to top through `colour-below`, and the goal asks
        for every bottle to be closed.
        """
        capacity = SMALL["capacity"]
        for n_colours, per_colour, spares, steps in IPC_SHAPES:
            for seed in range(3):
                stacks, _ = scramble(
                    n_colours=n_colours,
                    bottles_per_colour=per_colour,
                    capacity=capacity,
                    n_spare_bottles=spares,
                    steps=steps,
                    seed=seed,
                )
                for stack in stacks:
                    colours = [c for c, _ in stack]
                    self.assertEqual(len(colours), len(set(colours)), stack)
                    self.assertTrue(all(n > 0 for _, n in stack), stack)
                    self.assertLessEqual(filled(stack), capacity, stack)

                gen, params, problem = self._gen_and_instance(
                    n_colours=n_colours,
                    bottles_per_colour=per_colour,
                    n_spare_bottles=spares,
                    scramble_steps=steps,
                    seed=seed,
                )
                segments = self._numbers(problem, "colour-segments")
                for colour_index in range(n_colours):
                    name = colour_name(colour_index)
                    total = sum(v for (_, c), v in segments.items() if c == name)
                    self.assertEqual(total, capacity * per_colour, name)
                # the empty marker is a colour object but never fills anything
                for (_, c), v in segments.items():
                    if c == EMPTY_COLOUR:
                        self.assertEqual(v, 0)
                # segments-filled agrees with the per-colour counts
                for key, count in self._numbers(problem, "segments-filled").items():
                    self.assertEqual(
                        count,
                        sum(v for (b, _), v in segments.items() if (b,) == key),
                    )

                below = {
                    (b, c): c1 for b, c, c1 in self._true_facts(problem, "colour-below")
                }
                upper = {b: c for b, c in self._true_facts(problem, "upper-colour")}
                for index in range(gen.n_bottles(params)):
                    bottle = bottle_name(index)
                    colour = upper[bottle]
                    seen: set = set()
                    while colour != EMPTY_COLOUR:
                        self.assertNotIn(colour, seen)
                        seen.add(colour)
                        self.assertGreater(segments[(bottle, colour)], 0)
                        colour = below[(bottle, colour)]
                    # an empty bottle shows the marker and rests on nothing
                    if upper[bottle] == EMPTY_COLOUR:
                        self.assertNotIn((bottle, EMPTY_COLOUR), below)

                self.assertEqual(
                    {str(g) for g in problem.goals},
                    {f"closed({bottle_name(i)})" for i in range(gen.n_bottles(params))},
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
