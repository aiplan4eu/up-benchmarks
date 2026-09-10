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

import tempfile
import warnings
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ConfigSpace import Configuration

from unified_planning.engines.plan_validator import (
    SequentialPlanValidator,
    ValidationResultStatus,
)
from unified_planning.engines.results import FailedValidationReason

from upbm.domains.forestfire import ForestFireGenerator
from upbm.domains.forestfire.forestfire import (
    BUSHES_ROW,
    MAX_WATER_ON_BUSHES,
    PROB15_DURABILITIES,
    TREE_ROW_AMOUNTS,
    TREE_ROW_ROW,
    cell_name,
    fire_columns,
    fire_region,
    is_bushes,
    mid_column,
)
from upbm.io import Format, dump_instance, parse_plan_string
from upbm.tests.base_domain_test import BaseDomainTest


# prob01, the smallest shipped instance: a 3x3 grid with one fire in the far
# corner, and a gate tree the single axe can just about chop through.
PROB01 = dict(
    width=3,
    height=3,
    water_capacity=3,
    durability=3,
    tree_amount=3,
    fire_rows=1,
    n_bots=1,
    n_axes=1,
    fire_spread=0,
    layout_quirk=0,
    fire_00=5,
)

# prob17, one of the irregular ones: two whole rows of a 7-wide grid alight
# with fourteen different amounts.
PROB17_FIRES = [1, 6, 3, 1, 2, 3, 3, 2, 1, 1, 3, 5, 6, 1]
PROB17 = dict(
    width=7,
    height=5,
    water_capacity=12,
    durability=3,
    tree_amount=3,
    fire_rows=2,
    n_bots=1,
    n_axes=2,
    fire_spread=3,
    layout_quirk=0,
    **{f"fire_{i:02d}": v for i, v in enumerate(PROB17_FIRES)},
)

# A puzzle far smaller than anything shipped: one fire, one unit of water.
TINY = dict(PROB01, water_capacity=1, fire_00=1)

RANDOM_DEFAULTS = dict(
    width=5,
    height=6,
    water_capacity=6,
    durability=3,
    tree_amount=6,
    fire_rows=2,
    n_bots=1,
    n_axes=2,
    max_fire=3,
    seed=42,
)


class TestForestFire(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self) -> str:
        return "forestfire"

    @property
    def generator(self) -> Any:
        return ForestFireGenerator

    def _get_configs(
        self, variant: str = "ipc", **overrides
    ) -> Tuple[Configuration, Configuration]:
        domain_space = ForestFireGenerator.get_domain_parameter_space()
        domain_config = Configuration(
            domain_space, values={"version": 1, "variant": variant}
        )
        gen = ForestFireGenerator(domain_config)
        space = gen.instance_parameter_space
        base = dict(PROB01) if variant == "ipc" else dict(RANDOM_DEFAULTS)
        base.update(overrides)
        values: Dict[str, Any] = {
            name: base.get(name, space[name].default_value) for name in space.keys()
        }
        return domain_config, Configuration(space, values=values)

    def _gen_and_instance(self, variant: str = "ipc", **overrides):
        domain_config, instance_config = self._get_configs(variant, **overrides)
        gen = ForestFireGenerator(domain_config)
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
        # Far smaller than any shipped instance: one fire, one trip.
        return [self._get_configs("ipc", **TINY)]

    @property
    def object_data(self):
        domain_config, instance_config = self._get_configs("ipc", **PROB01)
        # a 3x3 grid: row 2 is bushes except its middle column, so 7 grass
        # cells and 2 bushes ones, plus one bot and one axe
        return [
            (
                domain_config,
                instance_config,
                [("bot", 1), ("axe", 1), ("grass", 7), ("bushes", 2)],
            )
        ]

    @property
    def problem_actions(self) -> List[Tuple[Configuration, Configuration, int]]:
        domain_config, instance_config = self._get_configs("ipc", **PROB01)
        # move-grass, move-bushes, drop-water, chop-tree, fill-water, pick-ax,
        # put-out-fire
        return [(domain_config, instance_config, 7)]

    # ---- the layout rule, which both variants share -------------------

    def test_layout_rule_matches_the_ipc_set(self):
        """The whole skeleton, pinned against prob01 read off the dataset.

        Nothing here is a parameter: the shipped set follows one rule for the
        terrain, the ponds and the starting positions, verified across all 20.
        """
        gen, params, problem = self._gen_and_instance("ipc", **PROB01)
        cells = {o.name for o in problem.all_objects} - {"bot1", "axe1"}
        self.assertEqual(
            cells,
            {
                "grass1_1",
                "grass2_1",
                "grass3_1",
                "bushes1_2",
                "grass2_2",
                "bushes3_2",
                "grass1_3",
                "grass2_3",
                "grass3_3",
            },
        )
        # ponds in both top corners, and nowhere else
        self.assertEqual(
            sorted(self._true_facts(problem, "pond")), [("grass1_1",), ("grass3_1",)]
        )
        # max-water 1 on exactly the bushes cells
        self.assertEqual(
            self._numbers(problem, "max-water"),
            {("bushes1_2",): MAX_WATER_ON_BUSHES, ("bushes3_2",): MAX_WATER_ON_BUSHES},
        )
        # the gate tree, and nothing else growing
        self.assertEqual(
            {c: v for c, v in self._numbers(problem, "tree").items() if v},
            {("grass2_2",): 3},
        )
        # one fire, in the far corner of the last row
        self.assertEqual(
            {c: v for c, v in self._numbers(problem, "fire").items() if v},
            {("grass3_3",): 5},
        )
        self.assertEqual([str(g) for g in problem.goals], ["(fire(grass3_3) == 0)"])

    def test_grid_is_connected_to_four_neighbours_both_ways(self):
        gen, params, problem = self._gen_and_instance("ipc", width=5, height=4)
        edges = set(self._true_facts(problem, "connected"))
        expected = set()
        for x in range(1, 6):
            for y in range(1, 5):
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 1 <= nx <= 5 and 1 <= ny <= 4:
                        expected.add((cell_name(x, y, 5), cell_name(nx, ny, 5)))
        self.assertEqual(edges, expected)

    def test_bushes_row_has_one_grass_gate(self):
        """Row 2 is bushes apart from its middle column, which carries the tree."""
        for width, gate in ((3, 2), (5, 3), (7, 4), (9, 5)):
            self.assertEqual(mid_column(width), gate)
            row = [is_bushes(x, BUSHES_ROW, width) for x in range(1, width + 1)]
            self.assertEqual(row.count(False), 1)
            self.assertFalse(row[gate - 1])
        # no other row has bushes in it
        self.assertFalse(any(is_bushes(x, 3, 5) for x in range(1, 6)))

    def test_bots_and_axes_line_up_along_the_top_row(self):
        gen, params, problem = self._gen_and_instance(
            "ipc", width=5, height=4, n_bots=3, n_axes=2
        )
        at = {o: l for o, l in self._true_facts(problem, "at")}
        self.assertEqual(
            at,
            {
                "bot1": "grass1_1",
                "bot2": "grass2_1",
                "bot3": "grass3_1",
                "axe1": "grass1_1",
                "axe2": "grass2_1",
            },
        )
        # every bot starts dry, and none of them is holding an axe yet
        self.assertEqual(set(self._numbers(problem, "has-water").values()), {0})
        self.assertEqual(self._true_facts(problem, "has"), [])

    # ---- the ipc variant ---------------------------------------------

    def test_fire_spreads_are_nested(self):
        """The four spreads the shipped set uses grow one into the next."""
        previous: List[int] = []
        for spread in range(4):
            columns = fire_columns(9, spread)
            self.assertTrue(set(previous).issubset(columns), (spread, columns))
            previous = columns
        self.assertEqual(fire_columns(9, 0), [9])
        self.assertEqual(fire_columns(9, 1), [1, 9])
        self.assertEqual(fire_columns(9, 2), [1, 5, 9])
        self.assertEqual(fire_columns(9, 3), list(range(1, 10)))
        # the region is read top row first, then left to right
        self.assertEqual(
            fire_region(3, 4, 2, 3),
            [(1, 3), (2, 3), (3, 3), (1, 4), (2, 4), (3, 4)],
        )

    def test_a_shipped_irregular_instance_is_reproduced(self):
        """prob17: two full rows of a 7-wide grid, fourteen different amounts."""
        gen, params, problem = self._gen_and_instance("ipc", **PROB17)
        fires = {c: v for c, v in self._numbers(problem, "fire").items() if v}
        expected = {
            (cell_name(x, y, 7),): PROB17_FIRES[i]
            for i, (x, y) in enumerate(fire_region(7, 5, 2, 3))
        }
        self.assertEqual(fires, expected)
        self.assertEqual(len(problem.goals), 14)
        self.assertEqual(self._numbers(problem, "water-capacity"), {("bot1",): 12})

    def test_prob12_declares_an_axe_it_never_places(self):
        """A slip in the shipped file, reproduced on purpose.

        prob12 writes "(at axe2 grass2_1)" twice instead of placing axe3, so
        axe3 has a durability but no location and can never be picked up.
        """
        gen, params, problem = self._gen_and_instance(
            "ipc",
            width=5,
            height=6,
            n_axes=3,
            layout_quirk=1,
            tree_amount=6,
            durability=4,
            fire_rows=2,
            fire_spread=2,
        )
        at = {o: l for o, l in self._true_facts(problem, "at")}
        self.assertNotIn("axe3", at)
        self.assertEqual(at["axe1"], "grass1_1")
        self.assertEqual(at["axe2"], "grass2_1")
        # it still exists and still has a durability
        self.assertIn("axe3", {o.name for o in problem.all_objects})
        self.assertEqual(self._numbers(problem, "durability")[("axe3",)], 4)
        # and the quirk's other half: a second tree below the gate
        self.assertEqual(
            {c: v for c, v in self._numbers(problem, "tree").items() if v},
            {("grass3_2",): 6, ("grass3_3",): 6},
        )

    def test_prob15_has_a_tree_row_and_mismatched_axes(self):
        gen, params, problem = self._gen_and_instance(
            "ipc",
            width=5,
            height=6,
            n_axes=3,
            layout_quirk=2,
            tree_amount=3,
            fire_rows=1,
            fire_spread=3,
        )
        durabilities = self._numbers(problem, "durability")
        self.assertEqual(
            [durabilities[(f"axe{i}",)] for i in (1, 2, 3)],
            list(PROB15_DURABILITIES),
        )
        trees = {c: v for c, v in self._numbers(problem, "tree").items() if v}
        for x, amount in enumerate(TREE_ROW_AMOUNTS, start=1):
            self.assertEqual(trees[(cell_name(x, TREE_ROW_ROW, 5),)], amount)
        # the gate tree is still there on top of the row
        self.assertEqual(trees[("grass3_2",)], 3)

    # ---- the random variant ------------------------------------------

    def test_random_variant_lights_every_burning_cell(self):
        """Each cell of the burning rows gets an amount drawn from 1..max_fire."""
        gen, params, problem = self._gen_and_instance(
            "random", width=5, height=6, fire_rows=2, max_fire=3, seed=1
        )
        fires = gen.fires(params)
        self.assertEqual(set(fires), set(fire_region(5, 6, 2, 3)))
        self.assertTrue(all(1 <= v <= 3 for v in fires.values()), fires)
        self.assertEqual(len(problem.goals), 10)
        # the random variant has no fire slots or quirks to set
        self.assertNotIn("fire_00", params.config_space.keys())
        self.assertNotIn("layout_quirk", params.config_space.keys())
        self.assertIn("seed", params.config_space.keys())

    def test_the_seed_is_a_real_parameter(self):
        """A different seed redraws the fires without changing the layout."""

        def state(problem):
            return sorted(
                (str(k), str(v)) for k, v in problem.explicit_initial_values.items()
            )

        _, _, first = self._gen_and_instance("random", seed=1)
        _, _, again = self._gen_and_instance("random", seed=1)
        _, _, other = self._gen_and_instance("random", seed=2)
        self.assertEqual(state(first), state(again))
        self.assertNotEqual(state(first), state(other))
        self.assertEqual(len(list(first.all_objects)), len(list(other.all_objects)))

    # ---- what is refused ---------------------------------------------

    def test_fires_must_fit_below_the_bushes_row(self):
        """Otherwise the fire lands on the gate itself, a different puzzle."""
        domain_config, _ = self._get_configs("random")
        gen = ForestFireGenerator(domain_config)
        _, ok = self._get_configs("random", height=4, fire_rows=2)
        self.assertTrue(gen.check_instance_parameters(ok))
        _, bad = self._get_configs("random", height=3, fire_rows=2)
        self.assertFalse(gen.check_instance_parameters(bad))
        with self.assertRaises(ValueError):
            gen.get_instance(bad)

    def test_bots_and_axes_cannot_outnumber_the_columns(self):
        """They line up along the top row, so there has to be room for them."""
        domain_config, _ = self._get_configs("random")
        gen = ForestFireGenerator(domain_config)
        _, ok = self._get_configs("random", width=3, n_bots=3, n_axes=2)
        self.assertTrue(gen.check_instance_parameters(ok))
        for overrides in ({"n_bots": 4}, {"n_axes": 4}):
            _, bad = self._get_configs("random", width=3, **overrides)
            self.assertFalse(gen.check_instance_parameters(bad), overrides)

    # ---- the domain's own mechanics -----------------------------------

    def test_sequential_plan_validation(self):
        """Cross the bushes with the one unit of water it will allow through."""
        gen, params, problem = self._gen_and_instance("ipc", **TINY)
        plan = parse_plan_string(
            problem,
            "\n".join(
                [
                    "(fill-water bot1 grass1_1)",
                    "(move-grass bot1 grass1_1 bushes1_2)",
                    "(move-bushes bot1 bushes1_2 grass1_3)",
                    "(move-grass bot1 grass1_3 grass2_3)",
                    "(move-grass bot1 grass2_3 grass3_3)",
                    "(put-out-fire bot1 grass3_3)",
                ]
            ),
        )
        with SequentialPlanValidator() as validator:
            result = validator.validate(problem, plan)
            self.assertEqual(result.status, ValidationResultStatus.VALID, f"{result}")

    def test_the_gate_tree_can_be_chopped_open(self):
        """The other way through: spend the whole axe on the gate.

        The tree is worth exactly as much as the axe, so this opens the middle
        column permanently and leaves nothing to chop with afterwards.
        """
        gen, params, problem = self._gen_and_instance("ipc", **TINY)
        plan = parse_plan_string(
            problem,
            "\n".join(
                [
                    "(fill-water bot1 grass1_1)",
                    "(pick-ax bot1 axe1 grass1_1)",
                    "(move-grass bot1 grass1_1 grass2_1)",
                    "(move-grass bot1 grass2_1 grass2_2)",
                    "(chop-tree bot1 axe1 grass2_2)",
                    "(chop-tree bot1 axe1 grass2_2)",
                    "(chop-tree bot1 axe1 grass2_2)",
                    "(move-grass bot1 grass2_2 grass2_3)",
                    "(move-grass bot1 grass2_3 grass3_3)",
                    "(put-out-fire bot1 grass3_3)",
                ]
            ),
        )
        with SequentialPlanValidator() as validator:
            result = validator.validate(problem, plan)
            self.assertEqual(result.status, ValidationResultStatus.VALID, f"{result}")

    def test_a_loaded_bot_cannot_leave_a_bushes_cell(self):
        """The mechanic the whole domain turns on.

        max-water is 1 on every bushes cell, so a bot carrying more than that
        is stuck there. It is why an unchoppable gate tree forces the water
        across one unit per trip.
        """
        gen, params, problem = self._gen_and_instance(
            "ipc", **dict(TINY, water_capacity=2)
        )
        plan = parse_plan_string(
            problem,
            "\n".join(
                [
                    "(fill-water bot1 grass1_1)",
                    "(fill-water bot1 grass1_1)",
                    "(move-grass bot1 grass1_1 bushes1_2)",
                    "(move-bushes bot1 bushes1_2 grass1_3)",
                ]
            ),
        )
        with SequentialPlanValidator() as validator:
            result = validator.validate(problem, plan)
            self.assertEqual(result.status, ValidationResultStatus.INVALID)
            self.assertEqual(result.reason, FailedValidationReason.INAPPLICABLE_ACTION)

    # ---- the metric ---------------------------------------------------

    def test_metric_is_kept_in_every_instance(self):
        for variant, overrides in (("ipc", PROB01), ("random", RANDOM_DEFAULTS)):
            domain_config, instance_config = self._get_configs(variant, **overrides)
            gen = ForestFireGenerator(domain_config)
            problem = gen.get_instance(instance_config)
            self.assertEqual(len(problem.quality_metrics), 1)
            self.assertIn("cost", str(problem.quality_metrics[0]))

    def test_anml_warns_about_lost_metric(self):
        domain_config, instance_config = self._get_configs("ipc", **PROB01)
        gen = ForestFireGenerator(domain_config)
        problem = gen.get_instance(instance_config)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "problem.anml"
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                dump_instance(problem, Format.ANML, out)
            # the warning must not stop the file from being written
            self.assertTrue(out.exists())
            self.assertEqual(len(caught), 1)
            self.assertIn("metric", str(caught[0].message))
