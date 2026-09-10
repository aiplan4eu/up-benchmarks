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

import random
from pathlib import Path
from typing import Any, List, NamedTuple, Optional, Tuple

from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Categorical,
    Constant,
)
from unified_planning.io import PDDLReader
from unified_planning.model import Problem, Object, FNode
from unified_planning.shortcuts import TRUE, UserType

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# The colour names the IPC instances use, in the order they use them. Past the
# end of the list colours are simply numbered, so nothing caps how many there
# can be.
COLOUR_PALETTE = (
    "red",
    "green",
    "blue",
    "yellow",
    "purple",
    "orange",
    "cyan",
    "magenta",
    "lime",
    "teal",
)

# The domain is compiled to use no domain constants, so the "no colour" marker
# is an ordinary problem object carrying (empty-colour ?e).
EMPTY_COLOUR = "empty"


def colour_name(index: int) -> str:
    """The name of the index-th playable colour."""
    if index < len(COLOUR_PALETTE):
        return COLOUR_PALETTE[index]
    return f"colour{index + 1:02d}"


def bottle_name(index: int) -> str:
    """The name of the index-th bottle, numbered as the IPC instances are."""
    return f"bottle{index + 1:02d}"


class Pour(NamedTuple):
    """One pour of the witness plan, as the domain's actions spell it.

    ``source`` empties its top run of ``colour`` onto ``target``, whose top
    colour before the pour is ``below`` - the colour the run comes to rest on.
    ``take`` is how many segments the run is. ``to_empty_bottle`` says which
    of the domain's two pour actions applies: pouring onto a bottle that
    already shows the same colour, or onto an empty one.
    """

    source: int
    target: int
    colour: int
    below: Optional[int]
    take: int
    to_empty_bottle: bool


# A bottle is a stack of (colour, run length) pairs, bottom first. The domain
# holds one `colour-segments` count per (bottle, colour) and `pour` zeroes it,
# so a colour can occupy AT MOST ONE run per bottle - a state that repeats a
# colour in one bottle cannot be written down in this domain at all. Every
# state this module builds keeps to that.
Stack = List[Tuple[int, int]]


def filled(stack: Stack) -> int:
    """How many segments of the bottle are used."""
    return sum(length for _, length in stack)


def solved_state(n_colours: int, bottles_per_colour: int, capacity: int) -> List[Stack]:
    """The finished puzzle: every colour in full bottles, the spares empty.

    This is the state the scramble walks backwards from, and the state the
    witness plan walks back to.
    """
    return [
        [(colour, capacity)]
        for colour in range(n_colours)
        for _ in range(bottles_per_colour)
    ]


def inverse_moves(stacks: List[Stack], capacity: int) -> List[Pour]:
    """Every pour that could have produced the current state.

    Read a returned move backwards to scramble (take ``take`` segments off
    ``source`` and drop them on ``target``) and forwards to solve (``target``
    pours its top run back onto ``source``).
    """
    moves: List[Pour] = []
    for source, stack in enumerate(stacks):
        if not stack:
            continue
        colour, run = stack[-1]
        for take in range(1, run + 1):
            # Taking the whole run is only undoable if it left the bottle
            # empty: `pour` needs the colour still showing on the bottle it
            # poured onto, and `pour-to-empty-bottle` needs that bottle to
            # have been empty beforehand. Anything in between is unreachable.
            if take == run and len(stack) > 1:
                continue
            to_empty_bottle = take == run
            for target, other in enumerate(stacks):
                if target == source:
                    continue
                # The pour zeroes the colour on the bottle it leaves, so that
                # bottle cannot have held the colour anywhere else.
                if any(c == colour for c, _ in other):
                    continue
                if filled(other) + take > capacity:
                    continue
                moves.append(
                    Pour(
                        source=source,
                        target=target,
                        colour=colour,
                        below=other[-1][0] if other else None,
                        take=take,
                        to_empty_bottle=to_empty_bottle,
                    )
                )
    return moves


def lands_on_solved(stacks: List[Stack], move: "Pour", capacity: int) -> bool:
    """Would walking this pour backwards give a puzzle that is already solved?

    The walk starts from the solved puzzle, so it can wander back onto it.
    That would produce an instance which is not a puzzle at all - only the
    closes would be left to do - so those steps are skipped.
    """
    for index, stack in enumerate(stacks):
        if index == move.source:
            colour, run = stack[-1]
            stack = (
                stack[:-1]
                if move.take == run
                else stack[:-1] + [(colour, run - move.take)]
            )
        elif index == move.target:
            stack = stack + [(move.colour, move.take)]
        # solved means every bottle is empty or holds one full colour
        if stack and not (len(stack) == 1 and stack[0][1] == capacity):
            return False
    return True


def apply_inverse(stacks: List[Stack], move: "Pour") -> None:
    """Walk one pour backwards, scrambling the state a little further."""
    colour, run = stacks[move.source][-1]
    if move.take == run:
        stacks[move.source].pop()
    else:
        stacks[move.source][-1] = (colour, run - move.take)
    stacks[move.target].append((colour, move.take))


def scramble(
    n_colours: int,
    bottles_per_colour: int,
    capacity: int,
    n_spare_bottles: int,
    steps: int,
    seed: int,
) -> Tuple[List[Stack], List["Pour"]]:
    """Build a puzzle by walking backwards from the finished one.

    Returns the scrambled bottles and the pours that undo the scramble, in
    the order a plan has to play them. Because every step is a pour read
    backwards, that list is a **witness plan**: the instance is solvable by
    construction rather than by anyone checking afterwards.

    ``steps`` is how many pours the walk takes, and it is an upper bound on
    two counts. A small puzzle runs out of room and the walk stops early
    rather than pretending otherwise; and a random walk may partly retrace
    itself, so the puzzle can end up fewer than ``steps`` pours from solved.
    It never ends up *on* the solved puzzle - those steps are skipped.
    """
    stacks = solved_state(n_colours, bottles_per_colour, capacity)
    stacks += [[] for _ in range(n_spare_bottles)]
    rng = random.Random(seed)
    undo: List[Pour] = []
    for _ in range(steps):
        options = [
            move
            for move in inverse_moves(stacks, capacity)
            if not lands_on_solved(stacks, move, capacity)
        ]
        if not options:
            break
        move = rng.choice(options)
        apply_inverse(stacks, move)
        undo.append(move)
    # The scramble was built from the solved state outwards, so the plan that
    # solves it plays the same pours in the opposite order.
    undo.reverse()
    return stacks, undo


class RainbowttlesGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        # "random" rather than "ipc": this generator draws its own puzzles
        # instead of reproducing the shipped ones, whose scramble was never
        # published. An "ipc" variant can be added beside it if that script
        # ever turns up.
        mapping["variant"] = Categorical(
            "variant",
            ["random"],
            default="random",
        )
        return ConfigurationSpace(name=mapping)

    def __init__(self, domain_params: Configuration):
        domain_params.check_valid_configuration()
        if (
            domain_params.config_space
            != RainbowttlesGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Bottle = self._domain.user_type("bottle")
        self._Colour = self._domain.user_type("colour")
        self._upper_colour = self._domain.fluent("upper-colour")
        self._colour_below = self._domain.fluent("colour-below")
        self._closed = self._domain.fluent("closed")
        self._empty_colour = self._domain.fluent("empty-colour")
        self._real_colour = self._domain.fluent("real-colour")
        self._bottle_capacity = self._domain.fluent("bottle-capacity")
        self._segments_filled = self._domain.fluent("segments-filled")
        self._colour_segments = self._domain.fluent("colour-segments")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant != "random":
            raise ValueError(f"invalid variant {self.variant}")
        # How many segments a bottle holds. 4 in every shipped instance.
        # Two is the smallest that makes a puzzle: with room for one segment
        # every bottle is always either empty or full, so every state already
        # satisfies the goal and there is nothing to sort.
        mapping["capacity"] = Integer("capacity", (2, MAX_INT), default=4)
        # How many playable colours there are, not counting the empty marker.
        mapping["n_colours"] = Integer("n_colours", (1, MAX_INT), default=3)
        # How many bottles each colour fills once the puzzle is solved. The
        # IPC set uses 1 for p11-p40 and 2 for p41-p50.
        mapping["bottles_per_colour"] = Integer(
            "bottles_per_colour", (1, MAX_INT), default=1
        )
        # The bottles left empty in the solved puzzle. This is the room there
        # is to manoeuvre, so it is the real difficulty dial: the IPC set
        # always uses 2 to 4. At least one is needed or nothing can be poured
        # anywhere and the puzzle would be born solved.
        mapping["n_spare_bottles"] = Integer("n_spare_bottles", (1, MAX_INT), default=2)
        # How many pours to walk backwards from the solved puzzle. An upper
        # bound: a state with nowhere left to pour stops the walk early.
        mapping["scramble_steps"] = Integer("scramble_steps", (0, MAX_INT), default=6)
        # Which puzzle to draw. Changing it redraws the bottles without
        # changing the shape of the instance.
        #
        # NOTE this is OUR scramble's seed, not the one in the shipped
        # headers. Their seeds follow seed(k) = 9973 * k + 2026, but their
        # scramble algorithm was never published, so feeding one of their
        # seeds in here does not reproduce their instance.
        mapping["seed"] = Integer("seed", (0, MAX_INT), default=42)
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"Rainbowttles V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            # No metric: none of the 40 shipped instances defines one, and the
            # domain declares :action-costs without ever using it.
            return reader.parse_problem(
                str(RESOURCES_PATH / f"rainbowttles_v{self.version}.pddl")
            )
        raise ValueError(f"Unknown domain version {self.version}")

    def _get_object(self, name: str, type: UserType) -> Object:
        res = self._object_cache.get((name, type), None)
        if res is None:
            res = Object(name, type)
            self._object_cache[(name, type)] = res
        return res

    def _bottle(self, index: int) -> Object:
        return self._get_object(bottle_name(index), self._Bottle)

    def _colour(self, index: Optional[int]) -> Object:
        """The colour object, or the empty marker when index is None."""
        if index is None:
            return self._get_object(EMPTY_COLOUR, self._Colour)
        return self._get_object(colour_name(index), self._Colour)

    def _check_params(self, params: Configuration) -> None:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

    def n_bottles(self, params: Configuration) -> int:
        """How many bottles the puzzle has.

        Derived rather than asked for: the colours need a whole number of
        bottles to end up in, and the spares are what is left over. Asking for
        a bottle count instead would let someone request fewer bottles than
        the colours can possibly fit in.
        """
        return (
            params["n_colours"] * params["bottles_per_colour"]
            + params["n_spare_bottles"]
        )

    def _scramble(self, params: Configuration) -> Tuple[List[Stack], List[Pour]]:
        return scramble(
            n_colours=params["n_colours"],
            bottles_per_colour=params["bottles_per_colour"],
            capacity=params["capacity"],
            n_spare_bottles=params["n_spare_bottles"],
            steps=params["scramble_steps"],
            seed=params["seed"],
        )

    def get_witness_plan(self, params: Configuration) -> str:
        """A plan that solves the instance, in `upbm.io.parse_plan_string` form.

        The scramble is a sequence of pours walked backwards, so playing them
        forwards empties the puzzle back into the solved state; closing every
        bottle then reaches the goal. This is what replaces a diff against the
        IPC dataset for this port - there is nothing to diff against, so the
        instance carries its own proof that it can be solved.
        """
        self._check_params(params)
        _, undo = self._scramble(params)
        solved = solved_state(
            params["n_colours"], params["bottles_per_colour"], params["capacity"]
        ) + [[] for _ in range(params["n_spare_bottles"])]
        lines = []
        for move in undo:
            # The pour runs the opposite way round to the scramble step: the
            # bottle the scramble dropped segments on gives them back.
            bottle = bottle_name(move.target)
            other = bottle_name(move.source)
            colour = colour_name(move.colour)
            below = EMPTY_COLOUR if move.below is None else colour_name(move.below)
            if move.to_empty_bottle:
                lines.append(
                    f"(pour-to-empty-bottle {bottle} {colour} {below} "
                    f"{EMPTY_COLOUR} {other})"
                )
            else:
                lines.append(f"(pour {bottle} {colour} {below} {other})")
        for index, stack in enumerate(solved):
            # Back in the solved state every bottle is either full of one
            # colour or empty, so exactly one of the two closes applies.
            if stack:
                lines.append(
                    f"(close-bottle {bottle_name(index)} {colour_name(stack[0][0])})"
                )
            else:
                lines.append(f"(close-empty-bottle {bottle_name(index)})")
        return "\n".join(lines)

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        objs = [self._bottle(i) for i in range(self.n_bottles(params))]
        objs += [self._colour(i) for i in range(params["n_colours"])]
        objs.append(self._colour(None))
        return objs

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        _, colours_upper = hyperparam_range(instance_parameters_space["n_colours"])
        _, per_colour_upper = hyperparam_range(
            instance_parameters_space["bottles_per_colour"]
        )
        _, spare_upper = hyperparam_range(instance_parameters_space["n_spare_bottles"])
        bottles_upper = colours_upper * per_colour_upper + spare_upper
        return (
            [self._bottle(i) for i in range(bottles_upper)]
            + [self._colour(i) for i in range(colours_upper)]
            + [self._colour(None)]
        )

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        # Every shipped instance asks for exactly this: every bottle closed,
        # which means each one is either full of a single colour or empty.
        return [self._closed(self._bottle(i)) for i in range(self.n_bottles(params))]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        stacks, _ = self._scramble(params)
        capacity = params["capacity"]
        res: dict[FNode, FNode] = {}

        for colour in range(params["n_colours"]):
            res[self._real_colour(self._colour(colour))] = TRUE()
        res[self._empty_colour(self._colour(None))] = TRUE()

        for index, stack in enumerate(stacks):
            bottle = self._bottle(index)
            res[self._bottle_capacity(bottle)] = capacity
            counts = dict(stack)
            for colour in range(params["n_colours"]):
                res[self._colour_segments(bottle, self._colour(colour))] = counts.get(
                    colour, 0
                )
            # The empty marker is a colour object like any other, and the
            # shipped instances state its count too.
            res[self._colour_segments(bottle, self._colour(None))] = 0
            res[self._segments_filled(bottle)] = filled(stack)
            if stack:
                res[self._upper_colour(bottle, self._colour(stack[-1][0]))] = TRUE()
                # Each run records what it is sitting on; the bottom one sits
                # on the empty marker.
                below: Optional[int] = None
                for colour, _ in stack:
                    res[
                        self._colour_below(
                            bottle, self._colour(colour), self._colour(below)
                        )
                    ] = TRUE()
                    below = colour
            else:
                res[self._upper_colour(bottle, self._colour(None))] = TRUE()
        return res

    def check_instance_parameters(self, params: Configuration):
        # Nothing to reject. Unlike the ports that reproduce the IPC set, this
        # one does not inherit solvability from known-good instances - it
        # builds it: every instance starts from a solved puzzle and is walked
        # backwards along legal pours, so the scramble reversed is always a
        # plan. The parameter space carries the two conditions that could
        # otherwise go wrong, rather than checking them here: the bottle count
        # is derived from the colours instead of being asked for, and
        # n_spare_bottles starts at 1 so there is always somewhere to pour.
        return True
