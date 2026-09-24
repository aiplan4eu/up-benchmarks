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
from upbm.io import parse_plan_string
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
