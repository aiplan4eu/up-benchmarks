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

from ConfigSpace import Configuration
from unified_planning.engines.results import ValidationResultStatus

from upbm.domains.onlycraft import OnlyCraftGenerator
from upbm.tests.base_domain_test import BaseDomainTest


def _config(**params):
    """The default domain configuration and an instance configuration of it."""
    domain_config = (
        OnlyCraftGenerator.get_domain_parameter_space().get_default_configuration()
    )
    space = OnlyCraftGenerator(domain_config).instance_parameter_space
    return domain_config, Configuration(space, params)


def _plan(*actions):
    return "\n".join(f"({a})" for a in actions)


class TestOnlyCraft(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "onlycraft"

    @property
    def generator(self):
        return OnlyCraftGenerator

    def _get_configs(self):
        tight = dict(extra_trees=0, n_low_trees=0, n_air_cells=0)
        return [
            # the tightest instances there are, with exactly as many trees as
            # the goal needs: 1 for one pogo stick, 8 for four
            _config(n_pogo_sticks=1, **tight),
            _config(n_pogo_sticks=4, **tight),
            # one of each kind of cell, laid out in order: trees on cell0 and
            # cell1, low trees on cell2 and cell3, air on cell4-cell6
            _config(n_pogo_sticks=1, extra_trees=1, n_low_trees=2, n_air_cells=3),
        ]

    @property
    def plannable(self):
        # only the one-tree instance, the IPC ones ask for up to 200 pogo sticks
        return self._get_configs()[:1]

    @property
    def object_data(self):
        cells = [1, 8, 7]
        return [
            (*config, [("cell", n)]) for config, n in zip(self._get_configs(), cells)
        ]

    @property
    def problem_actions(self):
        # the ten crafting and breaking actions of the domain
        return [(*config, 10) for config in self._get_configs()]

    @property
    def validation_cases(self):
        one_tree, four_sticks, mixed = self._get_configs()

        # One tree gives 2 logs: one becomes the planks and the sticks, one the
        # pellet, and the pogo stick is crafted at the table on cell0.
        one_tree_plan = [
            "break_brutal cell0",
            "craft_plank",
            "craft_stick",
            "craft_synthetic_pellets",
            "craft_wooden_pogo cell0",
        ]
        # Four pogo sticks from the minimum of 8 trees: six are broken for 12
        # logs, two are tapped for 2 pellets, and the other 2 pellets come from
        # smelting (2 logs per half pellet) and the one synthetic pellet.
        four_sticks_plan = (
            [f"break_brutal cell{i}" for i in range(6)]
            + ["craft_plank"] * 7
            + ["craft_stick"] * 5
            + ["craft_tree_tap cell0"] * 2
            + ["place_tree_tap cell6", "place_tree_tap cell7"]
            + ["smelt_pellets_raw"] * 2
            + ["craft_synthetic_pellets"]
            + ["craft_wooden_pogo cell0"] * 4
        )
        # The planks and the sticks from two low trees, half a log each, and
        # the pellet from a tree.
        low_trees_plan = [
            "break_low cell2",
            "break_low cell3",
            "craft_plank",
            "craft_stick",
            "break_brutal cell0",
            "craft_synthetic_pellets",
            "craft_wooden_pogo cell0",
        ]
        return [
            (*one_tree, _plan(*one_tree_plan), ValidationResultStatus.VALID),
            # without the pellet CRAFT_WOODEN_POGO is not applicable
            (
                *one_tree,
                _plan(*[a for a in one_tree_plan if a != "craft_synthetic_pellets"]),
                ValidationResultStatus.INVALID,
            ),
            (*four_sticks, _plan(*four_sticks_plan), ValidationResultStatus.VALID),
            (*mixed, _plan(*low_trees_plan), ValidationResultStatus.VALID),
            # cell0 is an ordinary tree, which BREAK_LOW cannot touch
            (
                *mixed,
                _plan("break_low cell0", *low_trees_plan[1:]),
                ValidationResultStatus.INVALID,
            ),
        ]
