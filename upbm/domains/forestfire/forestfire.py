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
from typing import Any, Dict, List, Optional, Tuple

from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Categorical,
    Constant,
)
from unified_planning.io import PDDLReader
from unified_planning.model import Problem, Object, FNode
from unified_planning.model.metrics import MinimizeExpressionOnFinalState
from unified_planning.shortcuts import TRUE, Equals, UserType

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range

from .resources.ipc_forestfire_data import IPC_INSTANCES


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# The row of bushes that separates the ponds from the fire. It is row 2 in all
# 20 shipped instances, and it is what makes the domain interesting: leaving a
# bushes cell needs has-water <= max-water, which is 1 everywhere, so a bot
# crossing it carries at most one unit of water at a time.
#
# It stays a constant rather than a parameter: it is 1 in all 20 shipped
# instances, so nothing in the set varies along this axis, and the generator's
# parameters are meant to cover what does. Raising it is a layout question -
# see FORESTFIRE-GENERIC-DISCUSSION.md - not a loosening of this one.
BUSHES_ROW = 2
MAX_WATER_ON_BUSHES = 1

# Bots and axes line up along the top row: bot i and axe i both start on
# column i of row 1, which is where the shipped set puts them.
START_ROW = 1

# Everything starts dry and unpaid for.
INITIAL_WATER = 0
INITIAL_COST = 0

# Which columns of a burning row are alight. Nested: the far corner, then both
# corners, then the middle as well, then the whole row.
FIRE_SPREADS = ("far_corner", "both_corners", "corners_and_middle", "whole_row")


def mid_column(width: int) -> int:
    """The one column of the bushes row that is grass instead.

    This is the "gate": the only way through the bushes row without the
    water limit, and the cell the tree sits on.
    """
    return (width + 1) // 2


def is_bushes(x: int, y: int, width: int) -> bool:
    return y == BUSHES_ROW and x != mid_column(width)


def cell_name(x: int, y: int, width: int) -> str:
    """The domain's name for the cell at 1-based (column, row)."""
    return f"{'bushes' if is_bushes(x, y, width) else 'grass'}{x}_{y}"


def fire_columns(width: int, spread: str) -> List[int]:
    """Which columns of a burning row are on fire."""
    if spread == "far_corner":
        columns = {width}
    elif spread == "both_corners":
        columns = {1, width}
    elif spread == "corners_and_middle":
        columns = {1, mid_column(width), width}
    elif spread == "whole_row":
        columns = set(range(1, width + 1))
    else:
        raise ValueError(f"Unknown fire spread {spread}")
    return sorted(columns)


def fire_region(
    width: int, height: int, rows: int, spread: str
) -> List[Tuple[int, int]]:
    """The cells that can burn: the bottom `rows` rows, top row first."""
    return [
        (x, y)
        for y in range(height - rows + 1, height + 1)
        for x in fire_columns(width, spread)
    ]


class ForestFireGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        # Two variants that differ in kind, not in degree. "random" generates
        # new benchmarks and is the default; "ipc" reproduces the 20 shipped
        # instances from a transcribed table and takes one parameter, the
        # index of the instance to rebuild.
        mapping["variant"] = Categorical(
            "variant",
            ["random", "ipc"],
            default="random",
        )
        return ConfigurationSpace(name=mapping)

    def __init__(self, domain_params: Configuration):
        domain_params.check_valid_configuration()
        if (
            domain_params.config_space
            != ForestFireGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Bot = self._domain.user_type("bot")
        self._Axe = self._domain.user_type("axe")
        self._Grass = self._domain.user_type("grass")
        self._Bushes = self._domain.user_type("bushes")
        self._at = self._domain.fluent("at")
        self._connected = self._domain.fluent("connected")
        self._has = self._domain.fluent("has")
        self._pond = self._domain.fluent("pond")
        self._durability = self._domain.fluent("durability")
        self._water_capacity = self._domain.fluent("water-capacity")
        self._has_water = self._domain.fluent("has-water")
        self._tree = self._domain.fluent("tree")
        self._max_water = self._domain.fluent("max-water")
        self._fire = self._domain.fluent("fire")
        self._cost = self._domain.fluent("cost")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant not in ("random", "ipc"):
            raise ValueError(f"invalid variant {self.variant}")

        if self.variant == "ipc":
            # One parameter: which shipped instance to rebuild. The keys are
            # the numbers in the file names and run 1..20 with no gaps, so
            # every value in the range is a valid instance.
            indices = sorted(IPC_INSTANCES)
            mapping["index"] = Integer(
                "index", (indices[0], indices[-1]), default=indices[0]
            )
            return ConfigurationSpace(name=mapping)

        # Two columns is the narrowest grid that still has a bushes cell in the
        # gate row, so the bot can always get past a tree it cannot chop.
        mapping["width"] = Integer("width", (2, MAX_INT), default=5)
        # Three rows: the ponds, the bushes row, and somewhere to burn.
        mapping["height"] = Integer("height", (3, MAX_INT), default=6)
        mapping["water_capacity"] = Integer("water_capacity", (1, MAX_INT), default=6)
        mapping["durability"] = Integer("durability", (0, MAX_INT), default=3)
        # How much chopping the axes differ by. 0 gives every axe the same
        # durability, which is what the shipped set does everywhere but
        # prob15; above that each axe is drawn from durability +/- spread.
        mapping["durability_spread"] = Integer(
            "durability_spread", (0, MAX_INT), default=0
        )
        # The tree on the gate cell. Whether it is choppable is the sharpest
        # difficulty dial in the domain: the shipped set uses 3 against a
        # durability of 3, so one chop opens the gate for good, or 6 against
        # the same 3, which cannot be chopped at all and forces every drop of
        # water through the bushes one unit at a time.
        mapping["tree_amount"] = Integer("tree_amount", (0, MAX_INT), default=6)
        # How many rows at the bottom of the grid burn. The shipped set only
        # ever uses 1 or 2, but nothing in the domain caps it: the real
        # constraint is that the fire stays below the bushes row, which
        # check_instance_parameters enforces.
        mapping["fire_rows"] = Integer("fire_rows", (1, MAX_INT), default=2)
        # Which columns of a burning row are alight. The shipped set uses all
        # four of these; the generic variant defaults to the widest.
        mapping["fire_spread"] = Categorical(
            "fire_spread", list(FIRE_SPREADS), default="whole_row"
        )
        # Bots share the work and axes the chopping; the shipped set uses one
        # to three of each. Bot i and axe i start on column i of the top row,
        # so neither can outnumber the columns.
        mapping["n_bots"] = Integer("n_bots", (1, MAX_INT), default=1)
        mapping["n_axes"] = Integer("n_axes", (1, MAX_INT), default=2)
        # Each burning cell gets an amount drawn from 1..max_fire.
        mapping["max_fire"] = Integer("max_fire", (1, MAX_INT), default=3)
        mapping["seed"] = Integer("seed", (0, MAX_INT), default=42)
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"ForestFire V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            domain = reader.parse_problem(
                str(RESOURCES_PATH / f"forestfire_v{self.version}.pddl")
            )
            # Every action costs 1 and all 20 shipped instances minimise
            # (cost), so the metric belongs to the domain. Problem.clone()
            # carries it into every instance. The fluent is called "cost" and
            # not "total-cost", so the reader does not fold it into
            # MinimizeActionCosts and it stays in the initial values.
            domain.add_quality_metric(
                MinimizeExpressionOnFinalState(domain.fluent("cost")())
            )
            return domain
        raise ValueError(f"Unknown domain version {self.version}")

    def _get_object(self, name: str, type: UserType) -> Object:
        res = self._object_cache.get((name, type), None)
        if res is None:
            res = Object(name, type)
            self._object_cache[(name, type)] = res
        return res

    def _cell(self, x: int, y: int, width: int) -> Object:
        name = cell_name(x, y, width)
        return self._get_object(
            name, self._Bushes if is_bushes(x, y, width) else self._Grass
        )

    def _bot(self, index: int = 1) -> Object:
        return self._get_object(f"bot{index}", self._Bot)

    def _axe(self, index: int = 1) -> Object:
        return self._get_object(f"axe{index}", self._Axe)

    # ── What each variant says an instance contains ───────────────────────────
    #
    # The "ipc" variant reads these off the transcribed table; the "random" one
    # takes them from its parameters. Everything else - the bushes row, the
    # gate, the two corner ponds, where the bots and axes stand, the grid
    # connectivity - is rebuilt the same way for both, because it is identical
    # in all 20 shipped instances (forestfire_extract.py checks that).

    def _entry(self, params: Configuration) -> Dict[str, Any]:
        return IPC_INSTANCES[params["index"]]

    def _width(self, params: Configuration) -> int:
        return (
            self._entry(params)["width"] if self.variant == "ipc" else params["width"]
        )

    def _height(self, params: Configuration) -> int:
        return (
            self._entry(params)["height"] if self.variant == "ipc" else params["height"]
        )

    def _n_bots(self, params: Configuration) -> int:
        return (
            self._entry(params)["n_bots"] if self.variant == "ipc" else params["n_bots"]
        )

    def _capacity(self, params: Configuration) -> int:
        if self.variant == "ipc":
            return self._entry(params)["water_capacity"]
        return params["water_capacity"]

    def _axes(self, params: Configuration) -> List[Tuple[int, bool]]:
        """(durability, whether it is placed on the map) for each axe.

        prob12 declares an axe it never places - a slip in the shipped file,
        and an axe with no location can never be picked up, so prob12 is a
        two-axe problem wearing three axes. The "random" variant places every
        axe it makes.
        """
        if self.variant == "ipc":
            return [(d, placed) for d, placed in self._entry(params)["axes"]]
        base, spread = params["durability"], params["durability_spread"]
        if spread == 0:
            return [(base, True)] * params["n_axes"]
        # Offset so the durabilities do not follow the same stream as the
        # fires; with spread 0 no draw happens at all, so the default
        # configuration is unaffected.
        rng = random.Random(params["seed"] + 1)
        return [
            (max(0, rng.randint(base - spread, base + spread)), True)
            for _ in range(params["n_axes"])
        ]

    def fires(self, params: Configuration) -> Dict[Tuple[int, int], int]:
        """How much fire sits on each burning cell."""
        if self.variant == "ipc":
            return dict(self._entry(params)["fires"])
        region = fire_region(
            params["width"],
            params["height"],
            params["fire_rows"],
            params["fire_spread"],
        )
        rng = random.Random(params["seed"])
        values = [rng.randint(1, params["max_fire"]) for _ in region]
        return {cell: v for cell, v in zip(region, values) if v > 0}

    def trees(self, params: Configuration) -> Dict[Tuple[int, int], int]:
        """How much tree sits on each cell that has one."""
        if self.variant == "ipc":
            return dict(self._entry(params)["trees"])
        amount = params["tree_amount"]
        if amount <= 0:
            return {}
        return {(mid_column(params["width"]), BUSHES_ROW): amount}

    def _check_params(self, params: Configuration) -> None:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        width, height = self._width(params), self._height(params)
        return (
            [self._bot(i) for i in range(1, self._n_bots(params) + 1)]
            + [self._axe(i) for i in range(1, len(self._axes(params)) + 1)]
            + [
                self._cell(x, y, width)
                for y in range(1, height + 1)
                for x in range(1, width + 1)
            ]
        )

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        if self.variant == "ipc":
            # The table is the whole space, so take the largest of each.
            width = max(e["width"] for e in IPC_INSTANCES.values())
            height = max(e["height"] for e in IPC_INSTANCES.values())
            n_bots = max(e["n_bots"] for e in IPC_INSTANCES.values())
            n_axes = max(len(e["axes"]) for e in IPC_INSTANCES.values())
        else:
            _, width = hyperparam_range(instance_parameters_space["width"])
            _, height = hyperparam_range(instance_parameters_space["height"])
            _, n_bots = hyperparam_range(instance_parameters_space["n_bots"])
            _, n_axes = hyperparam_range(instance_parameters_space["n_axes"])
        objs = [self._bot(i) for i in range(1, n_bots + 1)]
        objs += [self._axe(i) for i in range(1, n_axes + 1)]
        for y in range(1, height + 1):
            for x in range(1, width + 1):
                if y == BUSHES_ROW:
                    # Which column of the bushes row is the grass gate depends
                    # on the width, so over a range of widths a cell here can
                    # be either. Both names are included; any one instance
                    # uses exactly one of them.
                    objs.append(self._get_object(f"grass{x}_{y}", self._Grass))
                    objs.append(self._get_object(f"bushes{x}_{y}", self._Bushes))
                else:
                    objs.append(self._get_object(f"grass{x}_{y}", self._Grass))
        return objs

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        width = self._width(params)
        # The shipped goals name exactly the cells that are alight, and say
        # nothing about where the bot ends up.
        return [
            Equals(self._fire(self._cell(x, y, width)), 0)
            for (x, y) in sorted(self.fires(params), key=lambda c: (c[1], c[0]))
        ]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        width, height = self._width(params), self._height(params)
        fires, trees = self.fires(params), self.trees(params)
        res: dict[FNode, FNode] = {}

        for y in range(1, height + 1):
            for x in range(1, width + 1):
                cell = self._cell(x, y, width)
                # The grid is fully connected to its four neighbours, both
                # ways round, in all 20 shipped instances.
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 1 <= nx <= width and 1 <= ny <= height:
                        res[self._connected(cell, self._cell(nx, ny, width))] = TRUE()
                res[self._tree(cell)] = trees.get((x, y), 0)
                res[self._fire(cell)] = fires.get((x, y), 0)
                if is_bushes(x, y, width):
                    res[self._max_water(cell)] = MAX_WATER_ON_BUSHES

        # A pond in each of the two top corners.
        res[self._pond(self._cell(1, START_ROW, width))] = TRUE()
        res[self._pond(self._cell(width, START_ROW, width))] = TRUE()

        for i in range(1, self._n_bots(params) + 1):
            bot = self._bot(i)
            res[self._at(bot, self._cell(i, START_ROW, width))] = TRUE()
            res[self._water_capacity(bot)] = self._capacity(params)
            res[self._has_water(bot)] = INITIAL_WATER
        # No bot starts holding an axe; picking one up is an action.
        for i, (durability, placed) in enumerate(self._axes(params), start=1):
            axe = self._axe(i)
            if placed:
                # axe i waits on column i of the top row
                res[self._at(axe, self._cell(i, START_ROW, width))] = TRUE()
            res[self._durability(axe)] = durability
        res[self._cost()] = INITIAL_COST
        return res

    def check_instance_parameters(self, params: Configuration):
        if self.variant == "ipc":
            # The index range is dense over the table, so this only guards a
            # table that has been edited into having gaps.
            return params["index"] in IPC_INSTANCES
        # The burning rows have to sit below the bushes row. Otherwise the
        # fire would land on the gate itself, which is a different puzzle from
        # the one all 20 shipped instances pose.
        if params["height"] < params["fire_rows"] + BUSHES_ROW:
            return False
        # Bot i and axe i stand on column i of the top row, so there has to be
        # a column for each of them.
        if max(params["n_bots"], params["n_axes"]) > params["width"]:
            return False
        # Nothing else can go wrong, and that is a property of the layout
        # rather than luck. Ponds refill without limit; drop-water is always
        # available, so a bushes cell can always be left carrying one unit;
        # so at least one unit of water reaches any cell below the gate per
        # trip, and the fires are finite. The gate tree never blocks anything
        # either, because the bot can walk round it through the bushes.
        #
        # This argument needs max-water >= 1 on the bushes, which is why
        # MAX_WATER_ON_BUSHES is a constant. Any future parameter that moves
        # the ponds, the barrier or the gate breaks it too, and would need a
        # real reachability check instead.
        return True
