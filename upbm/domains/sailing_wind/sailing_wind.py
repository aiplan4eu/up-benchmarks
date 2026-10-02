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
from fractions import Fraction
from pathlib import Path
from typing import Any, List, Optional, Tuple

from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Categorical,
    Constant,
)
from unified_planning.io import PDDLReader
from unified_planning.model import Problem, Object, FNode
from unified_planning.shortcuts import Real

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# The boat polar table: how fast the boat can go at each angle to the wind.
# All variants use exactly these values.
# vmax_0 is 0 because a sail boat cannot sail straight into the wind.
POLAR_TABLE = {
    0: Fraction("0"),
    15: Fraction("0.17"),
    30: Fraction("0.3"),
    45: Fraction("0.45"),
    60: Fraction("0.65"),
    75: Fraction("1"),
    90: Fraction("1.49"),
    105: Fraction("1.44"),
    120: Fraction("1.37"),
    135: Fraction("1.26"),
    150: Fraction("1.12"),
    165: Fraction("0.96"),
    180: Fraction("0.8"),
}

MAX_INERTIA = 100
VARIANT_DEFAULT_INERTIA = {
    "line": 50,
    "circle": 90,
    "random": 50,
}

# save_person wants the boat within 15 of the person in x and in y, so a person
# this close to the origin is already in reach of the boat where it starts.
RESCUE_HALF_SIZE = 15


# --- "line" placement ------------------------------------------------------
# The 20 instances of the optimal track put a single person on a straight
# diagonal ramp: position k of the ramp is (5 + 0.4 k, 15.5 + 0.4 k), and
# problem_N has its person at position N, for N = 0..19. Both coordinates grow
# by the same amount, so the ramp leads away from the boat along a 45 degree
# line.
LINE_FIRST_X = Fraction("5")
LINE_FIRST_Y = Fraction("15.5")
LINE_STEP = Fraction("0.4")

# --- "circle" placement ----------------------------------------------------
# The satisficing track puts every person on a circle of radius 100 around the
# boat, at a multiple of 45 degrees, with the coordinates rounded to whole
# numbers (100 * cos(45 degrees) is 70.71, which the dataset writes as 71).
# These eight points are the only person positions that track ever uses.
#
# The points are listed clockwise starting from north, because that is the
# order the shipped set walks them in: its single person instances go north,
# 45, 0, 315, 270 degrees, and in every two person instance the second person
# is further clockwise from north than the first. People are placed by walking
# this list (see `_circle_positions`), so the order here is what makes p0 and
# p1 come out as they do in the dataset.
CIRCLE_POSITIONS = [
    (0, 100),  # 90 degrees, north
    (71, 71),  # 45
    (100, 0),  # 0, east
    (71, -71),  # 315
    (0, -100),  # 270, south
    (-71, -71),  # 225
    (-100, 0),  # 180, west
    (-71, 71),  # 135
]


class SailingWindGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        # The variant says where the people to rescue are put. All three share
        # one domain skeleton, because the IPC dataset ships sailing-wind twice
        # and the two domain files are byte-identical.
        #
        # "line" and "circle" are the two layouts of the shipped set, named
        # after their shape rather than after the track they came from: the
        # optimal track is a line and the satisficing one a circle. What used
        # to separate those tracks, the inertia, is now an ordinary instance
        # parameter, so either layout can be sailed by either boat.
        # "random" draws the people instead, and is the default.
        mapping["variant"] = Categorical(
            "variant",
            ["random", "line", "circle"],
            default="random",
        )
        return ConfigurationSpace(name=mapping)

    def __init__(self, domain_params: Configuration):
        domain_params.check_valid_configuration()
        if (
            domain_params.config_space
            != SailingWindGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Boat = self._domain.user_type("boat")
        self._Person = self._domain.user_type("person")
        self._x = self._domain.fluent("x")
        self._y = self._domain.fluent("y")
        self._v = self._domain.fluent("v")
        self._r = self._domain.fluent("r")
        self._sailing_angle = self._domain.fluent("sailing-angle")
        self._saved = self._domain.fluent("saved")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant not in VARIANT_DEFAULT_INERTIA:
            raise ValueError(f"invalid variant {self.variant}")
        mapping["inertia"] = Integer(
            "inertia",
            (0, MAX_INERTIA),
            default=VARIANT_DEFAULT_INERTIA[self.variant],
        )

        if self.variant == "line":
            # People are placed by walking the ramp outwards: skip `skip`
            # positions, put a person there, then leave `gap` empty positions
            mapping["n_people"] = Integer("n_people", (1, MAX_INT), default=1)
            mapping["skip"] = Integer("skip", (0, MAX_INT), default=0)
            mapping["gap"] = Integer("gap", (0, MAX_INT), default=0)
        elif self.variant == "circle":
            # People are placed by walking the points of the circle clockwise
            # from north: skip `skip` points, put a person there, then leave
            # `gap` empty points before each next person.
            mapping["n_people"] = Integer("n_people", (1, MAX_INT), default=1)
            mapping["skip"] = Integer("skip", (0, len(CIRCLE_POSITIONS) - 1), default=0)
            mapping["gap"] = Integer("gap", (0, len(CIRCLE_POSITIONS) - 2), default=0)
        else:
            mapping["n_people"] = Integer("n_people", (1, MAX_INT), default=2)
            mapping["max_distance"] = Integer(
                "max_distance", (RESCUE_HALF_SIZE + 1, MAX_INT), default=100
            )
            mapping["seed"] = Integer("seed", (0, MAX_INT), default=42)
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"SailingWind V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            return reader.parse_problem(
                str(RESOURCES_PATH / f"sailing_wind_v{self.version}.pddl")
            )
        raise ValueError(f"Unknown domain version {self.version}")

    def _get_object(self, name: str, type: Any):
        res = self._object_cache.get((name, type), None)
        if res is None:
            res = Object(name, type)
            self._object_cache[(name, type)] = res
        return res

    def _check_params(self, params: Configuration) -> None:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

    @staticmethod
    def _number(value: Fraction):
        """Write whole numbers as integers, like the shipped instances do.

        The fluents are all real, but the dataset writes `(= (x b0) 0)` rather
        than `0.0`, and UP keeps the distinction when it writes the PDDL back
        out. Values are equal either way, this only keeps the generated files
        looking like the originals.
        """
        return int(value) if value.denominator == 1 else Real(value)

    @staticmethod
    def _inertia(params) -> Fraction:
        """The `r` fluent, from the whole percentage the parameter holds."""
        return Fraction(params["inertia"], MAX_INERTIA)

    def _person_positions(self, params) -> List[Tuple[Fraction, Fraction]]:
        """Return the (x, y) position of every person of this instance."""
        if self.variant == "line":
            return [
                (LINE_FIRST_X + LINE_STEP * k, LINE_FIRST_Y + LINE_STEP * k)
                for k in self._walk(params)
            ]
        elif self.variant == "circle":
            return self._circle_positions(params)
        elif self.variant == "random":
            return self._drawn_positions(params)
        raise ValueError(f"invalid variant {self.variant}")

    @staticmethod
    def _walk(params) -> List[int]:
        """The position index of every person, for the line and the circle.

        The first person is `skip` positions in, and each next one `gap + 1`
        positions after the one before.
        """
        return [
            params["skip"] + i * (params["gap"] + 1) for i in range(params["n_people"])
        ]

    @staticmethod
    def _circle_positions(params) -> List[Tuple[Fraction, Fraction]]:
        """Place the people on the circle, walking it clockwise from north.

        For example `skip` 1 and `gap` 1 put two people at 45 and 315 degrees,
        which is problem_5 of the satisficing track; eight people with `gap` 0
        fill every point.

        The walk keeps going round the circle, so people end up sharing a point
        once there are more of them than the walk visits: eight with `gap` 0,
        four with `gap` 1 or 5, two with `gap` 3. Such an instance is still
        solvable, the boat simply saves everyone at that point from where it
        stops, just as when two drawn people land on the same spot in `random`.
        """
        res: List[Tuple[Fraction, Fraction]] = []
        for k in SailingWindGenerator._walk(params):
            x, y = CIRCLE_POSITIONS[k % len(CIRCLE_POSITIONS)]
            res.append((Fraction(x), Fraction(y)))
        return res

    @staticmethod
    def _drawn_positions(params) -> List[Tuple[Fraction, Fraction]]:
        """Draw the people inside a circle around the boat.

        Whole coordinates are drawn in the square around the boat and kept when
        they land inside the circle and outside the rescue box. Working in
        whole numbers keeps the positions exact: turning an angle into a
        coordinate would go through a float, and a float initial value is worth
        avoiding. Two draws are thrown away:

        - outside the circle, so `max_distance` really is the furthest anyone
          can be rather than the half width of a square;
        - inside the rescue box, where a person needs no sailing at all
          because the boat starts stopped within reach.

        The loop always terminates: `max_distance` is at least
        RESCUE_HALF_SIZE + 1, and (max_distance, 0) passes both tests.
        """
        rng = random.Random(params["seed"])
        reach = params["max_distance"]
        res: List[Tuple[Fraction, Fraction]] = []
        while len(res) < params["n_people"]:
            x, y = rng.randint(-reach, reach), rng.randint(-reach, reach)
            if x * x + y * y > reach * reach:
                continue
            if abs(x) <= RESCUE_HALF_SIZE and abs(y) <= RESCUE_HALF_SIZE:
                continue
            res.append((Fraction(x), Fraction(y)))
        return res

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        objs: List[Object] = [self._get_object("b0", self._Boat)]
        for i in range(len(self._person_positions(params))):
            objs.append(self._get_object(f"p{i}", self._Person))
        return objs

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        if self.variant not in VARIANT_DEFAULT_INERTIA:
            raise ValueError(f"invalid variant {self.variant}")
        _, n_persons = hyperparam_range(instance_parameters_space["n_people"])
        return [self._get_object("b0", self._Boat)] + [
            self._get_object(f"p{i}", self._Person) for i in range(n_persons)
        ]

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        return [
            self._saved(self._get_object(f"p{i}", self._Person))
            for i in range(len(self._person_positions(params)))
        ]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        boat = self._get_object("b0", self._Boat)
        res: dict[FNode, FNode] = {}
        for angle, vmax in POLAR_TABLE.items():
            res[self._domain.fluent(f"vmax_{angle}")(boat)] = self._number(vmax)
        res[self._x(boat)] = self._number(Fraction(0))
        res[self._y(boat)] = self._number(Fraction(0))
        res[self._r(boat)] = self._number(self._inertia(params))
        res[self._v(boat)] = self._number(Fraction(0))
        res[self._sailing_angle(boat)] = 0
        for i, (x, y) in enumerate(self._person_positions(params)):
            person = self._get_object(f"p{i}", self._Person)
            res[self._x(person)] = self._number(x)
            res[self._y(person)] = self._number(y)
        return res

    def check_instance_parameters(self, params: Configuration):
        # As long as the boat can move at all it can reach anyone: it turns by
        # 15 degrees per move and can always shed speed by heading into the
        # wind (vmax_0 is 0), so it reaches any point on the plane and stops
        # there, and the rescue box around a person is a generous 30 by 30.
        #
        # The one exception is a boat that keeps *all* of its speed. A move
        # sets v to `vmax_angle * (1 - r) + r * v`, which at r = 1 is just v,
        # and the boat starts stopped, so it never moves and never displaces.
        # Such an instance is solvable only if everybody is already in reach.
        #
        # None of the three layouts can in fact put anyone there - the ramp
        # starts at y = 15.5, the circle has radius 100, and the draw rejects
        # the box - so today this rejects every instance at MAX_INERTIA. The
        # position is still what is checked, because that is the real reason,
        # and a layout added later may well place someone in the box.
        if params["inertia"] == MAX_INERTIA:
            return all(
                abs(x) <= RESCUE_HALF_SIZE and abs(y) <= RESCUE_HALF_SIZE
                for x, y in self._person_positions(params)
            )
        return True
