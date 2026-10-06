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


def _config(variant="generic", **params):
    """The domain configuration of `variant` and an instance configuration of it."""
    domain_space = OnlyCraftGenerator.get_domain_parameter_space()
    domain_config = Configuration(domain_space, {"version": 1, "variant": variant})
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
            _config(n_pogo_sticks=1, **tight),
            _config(n_pogo_sticks=4, **tight),
            _config(n_pogo_sticks=1, extra_trees=1, n_low_trees=2, n_air_cells=3),
            _config("ipc", index=1),
            _config("ipc", index=40),
        ]

    @property
    def plannable(self):
        return self._get_configs()[:1]

    @property
    def object_data(self):
        cells = [1, 8, 7, 9, 729]
        return [
            (*config, [("cell", n)]) for config, n in zip(self._get_configs(), cells)
        ]

    @property
    def problem_actions(self):
        return [(*config, 10) for config in self._get_configs()]

    @property
    def validation_cases(self):
        one_tree, four_sticks, mixed, first, _ = self._get_configs()
        one_tree_plan = [
            "break_brutal cell0",
            "craft_plank",
            "craft_stick",
            "craft_synthetic_pellets",
            "craft_wooden_pogo cell0",
        ]
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
        low_trees_plan = [
            "break_low cell2",
            "break_low cell3",
            "craft_plank",
            "craft_stick",
            "break_brutal cell0",
            "craft_synthetic_pellets",
            "craft_wooden_pogo cell0",
        ]
        ipc_plan = [
            "break_brutal cell4",
            "break_brutal cell5",
            "craft_plank",
            "craft_stick",
            "craft_synthetic_pellets",
            "craft_wooden_pogo cell6",
        ]
        p01_sat = _config("ipc", index=21)
        return [
            (*one_tree, _plan(*one_tree_plan), ValidationResultStatus.VALID),
            (
                *one_tree,
                _plan(*[a for a in one_tree_plan if a != "craft_synthetic_pellets"]),
                ValidationResultStatus.INVALID,
            ),
            (*four_sticks, _plan(*four_sticks_plan), ValidationResultStatus.VALID),
            (*mixed, _plan(*low_trees_plan), ValidationResultStatus.VALID),
            (
                *mixed,
                _plan("break_low cell0", *low_trees_plan[1:]),
                ValidationResultStatus.INVALID,
            ),
            (*first, _plan(*ipc_plan), ValidationResultStatus.VALID),
            (*p01_sat, _plan(*ipc_plan), ValidationResultStatus.INVALID),
        ]
