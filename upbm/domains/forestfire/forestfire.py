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


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# The row of bushes that separates the ponds from the fire. It is row 2 in all
# 20 shipped instances, and it is what makes the domain interesting: leaving a
# bushes cell needs has-water <= max-water, which is 1 everywhere, so a bot
# crossing it carries at most one unit of water at a time.
BUSHES_ROW = 2
MAX_WATER_ON_BUSHES = 1

# Bots and axes line up along the top row: bot i and axe i both start on
# column i of row 1, which is where the shipped set puts them.
START_ROW = 1

# Everything starts dry and unpaid for.
INITIAL_WATER = 0
INITIAL_COST = 0

# How many fire values an "ipc" instance can state. The largest burning region
# in the shipped set is two rows of nine cells (prob18, prob19, prob20).
NUM_FIRE_SLOTS = 18

# The four sets of burning columns the shipped set uses, as `fire_spread`
# indexes them. They are nested: the far corner, then both corners, then the
# middle as well, then the whole row.
FIRE_SPREADS = ("far corner", "both corners", "corners and middle", "whole row")

# prob12 adds a second tree directly below the first one, and prob15 replaces
# a whole row with trees. Both are one-off deviations rather than a dimension
# of the set, so they are stated as data here instead of costing ten more
# parameters that exactly one instance each would use.
QUIRK_NONE, QUIRK_PROB12, QUIRK_PROB15 = 0, 1, 2
# prob12: an extra tree one row below the gate, the same size as the gate
# tree, and a third axe that is declared and given a durability but is never
# put anywhere.
#
# That last part is a slip in the shipped file - it writes "(at axe2 grass2_1)"
# twice instead of placing axe3 - and it is reproduced on purpose, because an
# axe with no location can never be picked up, which makes prob12 a two-axe
# problem wearing three axes. The "random" variant places every axe it makes.
SECOND_TREE_ROW = 3
PROB12_UNPLACED_AXES = (3,)
# prob15: trees across row 5, sized as the shipped file has them, and three
# axes of different durabilities rather than the usual matching set.
TREE_ROW_ROW = 5
TREE_ROW_AMOUNTS = (2, 3, 3, 3, 3)
PROB15_DURABILITIES = (3, 4, 2)
# Both quirks are bundles of one-off deviations belonging to a single shipped
# instance each, so they are stated here as data. Making them parameters would
# cost a per-axe durability slot and a per-axe column slot that exactly one
# instance apiece would ever set.
QUIRK_AXES = 3


def mid_column(width: int) -> int:
    """The one column of the bushes row that is grass instead.

    This is the "gate": the only way through the bushes row without the
    one-unit water limit, and the cell the tree sits on.
    """
    return (width + 1) // 2


def is_bushes(x: int, y: int, width: int) -> bool:
    return y == BUSHES_ROW and x != mid_column(width)


def cell_name(x: int, y: int, width: int) -> str:
    """The domain's name for the cell at 1-based (column, row)."""
    return f"{'bushes' if is_bushes(x, y, width) else 'grass'}{x}_{y}"


def fire_columns(width: int, spread: int) -> List[int]:
    """Which columns of a burning row are on fire."""
    if spread == 0:
        columns = {width}
    elif spread == 1:
        columns = {1, width}
    elif spread == 2:
        columns = {1, mid_column(width), width}
    elif spread == 3:
        columns = set(range(1, width + 1))
    else:
        raise ValueError(f"Unknown fire spread {spread}")
    return sorted(columns)


def fire_region(
    width: int, height: int, rows: int, spread: int
) -> List[Tuple[int, int]]:
    """The cells that can burn, in the order the fire slots are read.

    Top row first, then left to right within a row - the order the shipped
    files list them in.
    """
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
        # Two real variants. "random" draws its own fires and is the default,
        # because it is the one that makes new benchmarks; "ipc" exists to
        # reproduce the 20 shipped instances and needs a parameter per fire to
        # do it.
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

        # --- shared by both variants ---
        #
        # Two columns is the narrowest grid that still has a bushes cell in the
        # gate row, so the bot can always get past a tree it cannot chop.
        mapping["width"] = Integer("width", (2, MAX_INT), default=5)
        # Three rows: the ponds, the bushes row, and somewhere to burn.
        mapping["height"] = Integer("height", (3, MAX_INT), default=6)
        mapping["water_capacity"] = Integer("water_capacity", (1, MAX_INT), default=6)
        mapping["durability"] = Integer("durability", (0, MAX_INT), default=3)
        # The tree on the gate cell. Whether it is choppable is the sharpest
        # difficulty dial in the domain: the shipped set uses 3 against a
        # durability of 3, so one chop opens the gate for good, or 6 against
        # the same 3, which cannot be chopped at all and forces every drop of
        # water through the bushes one unit at a time.
        mapping["tree_amount"] = Integer("tree_amount", (0, MAX_INT), default=6)
        # How many rows at the bottom of the grid are on fire. Always 1 or 2.
        mapping["fire_rows"] = Integer("fire_rows", (1, 2), default=2)
        # Bots share the work and axes the chopping; the shipped set uses one
        # to three of each. Bot i and axe i start on column i of the top row,
        # so neither can outnumber the columns.
        mapping["n_bots"] = Integer("n_bots", (1, MAX_INT), default=1)
        mapping["n_axes"] = Integer("n_axes", (1, MAX_INT), default=2)

        if self.variant == "ipc":
            # Which columns of a burning row are alight, see FIRE_SPREADS.
            mapping["fire_spread"] = Integer("fire_spread", (0, 3), default=0)
            # The two one-off layout deviations of the shipped set.
            mapping["layout_quirk"] = Integer("layout_quirk", (0, 2), default=0)
            # One slot per burning cell, read in the order of fire_region.
            # prob01-prob13 repeat a single value; prob14-prob20 are irregular
            # draws with no recorded seed, which is why the slots exist at all.
            # Slots past the end of the region are ignored.
            for slot in range(NUM_FIRE_SLOTS):
                mapping[f"fire_{slot:02d}"] = Integer(
                    f"fire_{slot:02d}", (0, MAX_INT), default=5 if slot == 0 else 0
                )
        else:
            # Every cell of every burning row is alight, as it is in the
            # irregular half of the shipped set, with an amount drawn from
            # 1..max_fire.
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

    def _unplaced_axes(self, params: Configuration) -> Tuple[int, ...]:
        """Axes that exist and have a durability but sit nowhere on the map.

        Only prob12 has any, and only because the shipped file forgot to place
        one. Such an axe can never be picked up.
        """
        quirk = params["layout_quirk"] if self.variant == "ipc" else QUIRK_NONE
        return PROB12_UNPLACED_AXES if quirk == QUIRK_PROB12 else ()

    def _durabilities(self, params: Configuration) -> List[int]:
        """How much chopping each axe has left in it.

        They match everywhere except prob15, which ships three different ones.
        """
        quirk = params["layout_quirk"] if self.variant == "ipc" else QUIRK_NONE
        if quirk == QUIRK_PROB15:
            return list(PROB15_DURABILITIES)
        return [params["durability"]] * params["n_axes"]

    def _check_params(self, params: Configuration) -> None:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

    def _region(self, params: Configuration) -> List[Tuple[int, int]]:
        spread = params["fire_spread"] if self.variant == "ipc" else 3
        return fire_region(
            params["width"], params["height"], params["fire_rows"], spread
        )

    def fires(self, params: Configuration) -> Dict[Tuple[int, int], int]:
        """How much fire sits on each burning cell.

        The "ipc" variant reads the values off the fire slots; the "random"
        one draws them, one per cell of the burning rows.
        """
        region = self._region(params)
        if self.variant == "ipc":
            values = [params[f"fire_{slot:02d}"] for slot in range(len(region))]
        else:
            rng = random.Random(params["seed"])
            values = [rng.randint(1, params["max_fire"]) for _ in region]
        return {cell: v for cell, v in zip(region, values) if v > 0}

    def trees(self, params: Configuration) -> Dict[Tuple[int, int], int]:
        """How much tree sits on each cell that has one."""
        width = params["width"]
        res = {(mid_column(width), BUSHES_ROW): params["tree_amount"]}
        quirk = params["layout_quirk"] if self.variant == "ipc" else QUIRK_NONE
        if quirk == QUIRK_PROB12:
            res[(mid_column(width), SECOND_TREE_ROW)] = params["tree_amount"]
        elif quirk == QUIRK_PROB15:
            for x, amount in enumerate(TREE_ROW_AMOUNTS, start=1):
                res[(x, TREE_ROW_ROW)] = amount
        return {cell: v for cell, v in res.items() if v > 0}

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        width, height = params["width"], params["height"]
        return (
            [self._bot(i) for i in range(1, params["n_bots"] + 1)]
            + [self._axe(i) for i in range(1, params["n_axes"] + 1)]
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
        width = params["width"]
        # The shipped goals name exactly the cells that are alight, and say
        # nothing about where the bot ends up.
        return [
            Equals(self._fire(self._cell(x, y, width)), 0)
            for (x, y) in sorted(self.fires(params), key=lambda c: (c[1], c[0]))
        ]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        width, height = params["width"], params["height"]
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

        for i in range(1, params["n_bots"] + 1):
            bot = self._bot(i)
            res[self._at(bot, self._cell(i, START_ROW, width))] = TRUE()
            res[self._water_capacity(bot)] = params["water_capacity"]
            res[self._has_water(bot)] = INITIAL_WATER
        # No bot starts holding an axe; picking one up is an action.
        unplaced = self._unplaced_axes(params)
        for i, durability in enumerate(self._durabilities(params), start=1):
            axe = self._axe(i)
            if i not in unplaced:
                # axe i waits on column i of the top row
                res[self._at(axe, self._cell(i, START_ROW, width))] = TRUE()
            res[self._durability(axe)] = durability
        res[self._cost()] = INITIAL_COST
        return res

    def check_instance_parameters(self, params: Configuration):
        # The burning rows have to sit below the bushes row. Otherwise the
        # fire would land on the gate itself, which is a different puzzle from
        # the one all 20 shipped instances pose.
        if params["height"] < params["fire_rows"] + BUSHES_ROW:
            return False
        # Bot i and axe i stand on column i of the top row, so there has to be
        # a column for each of them.
        if max(params["n_bots"], params["n_axes"]) > params["width"]:
            return False
        if self.variant == "ipc":
            # There has to be a slot for every burning cell.
            if len(self._region(params)) > NUM_FIRE_SLOTS:
                return False
            quirk = params["layout_quirk"]
            if quirk != QUIRK_NONE:
                # Both quirks carry per-axe data for exactly three axes.
                if params["n_axes"] != QUIRK_AXES:
                    return False
            if quirk == QUIRK_PROB12 and params["height"] <= SECOND_TREE_ROW:
                return False
            if quirk == QUIRK_PROB15:
                # The hardcoded row is prob15's, so it only fits prob15's grid.
                if params["width"] != len(TREE_ROW_AMOUNTS):
                    return False
                if params["height"] <= TREE_ROW_ROW:
                    return False
                # It spans the whole width, so a bot has to be able to chop all
                # the way through its cheapest cell to reach anything below it.
                # Chops can be spread over several axes, so what matters is the
                # total left in them.
                if min(TREE_ROW_AMOUNTS) > sum(self._durabilities(params)):
                    return False
        # Nothing else can go wrong, and that is a property of the layout
        # rather than luck. Ponds refill without limit; drop-water is always
        # available, so a bushes cell can always be left carrying one unit;
        # so at least one unit of water reaches any cell below the gate per
        # trip, and the fires are finite. The gate tree never blocks anything
        # either, because the bot can walk round it through the bushes.
        return True
