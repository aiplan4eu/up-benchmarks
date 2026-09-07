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
from unified_planning.engines.plan_validator import SequentialPlanValidator
from unified_planning.engines.results import ValidationResultStatus

from upbm.domains.onlycraft import OnlyCraftGenerator
from upbm.domains.onlycraft.onlycraft import n_trees_for
from upbm.io import parse_plan_string
from upbm.tests.base_domain_test import BaseDomainTest


class TestOnlyCraft(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "onlycraft"

    @property
    def generator(self):
        return OnlyCraftGenerator

    def _get_configs(self):
        default_config = (
            OnlyCraftGenerator.get_domain_parameter_space().get_default_configuration()
        )
        gen = OnlyCraftGenerator(default_config)
        instance_space = gen.instance_parameter_space
        # the smallest instance the domain allows, smaller than any IPC one
        instance_1 = Configuration(instance_space, {"n_cells": 4, "n_pogo_sticks": 1})
        instance_2 = Configuration(instance_space, {"n_cells": 9, "n_pogo_sticks": 2})
        return [(default_config, instance_1), (default_config, instance_2)]

    @property
    def plannable(self):
        # only the tiny one, the IPC instances ask for up to 200 pogo sticks
        return self._get_configs()[:1]

    @property
    def object_data(self):
        instances = self._get_configs()
        return [
            (*instances[0], [("cell", 4)]),
            (*instances[1], [("cell", 9)]),
        ]

    @property
    def problem_actions(self):
        instances = self._get_configs()
        # the ten crafting and breaking actions of the domain
        return [(*instances[0], 10), (*instances[1], 10)]

    def test_n_trees_follows_the_goal(self):
        # every shipped instance has ceil(3.5 * goal) trees
        self.assertEqual([n_trees_for(k) for k in range(1, 7)], [4, 7, 11, 14, 18, 21])
        # the biggest sat instance
        self.assertEqual(n_trees_for(200), 700)

    def test_initial_state_splits_cells_in_trees_and_air(self):
        domain_config, instance_config = self._get_configs()[1]
        gen = OnlyCraftGenerator(domain_config)
        problem = gen.get_instance(instance_config)

        def count(fluent_name):
            return sum(
                1
                for f in problem.explicit_initial_values
                if f.fluent().name == fluent_name
            )

        # 9 cells, 7 of them trees because the goal is 2 pogo sticks
        self.assertEqual(count("tree_cell"), 7)
        self.assertEqual(count("air_cell"), 2)
        # the crafting table is needed by CRAFT_TREE_TAP and CRAFT_WOODEN_POGO
        self.assertEqual(count("crafting_table_cell"), 1)
        self.assertEqual(count("position"), 1)
        for counter in [
            "toxicity",
            "count_pogo_stick",
            "count_log_in_inventory",
            "count_planks_in_inventory",
            "count_stick_in_inventory",
            "count_sack_polyisoprene_pellets_in_inventory",
            "count_tree_tap_in_inventory",
        ]:
            fluent = problem.fluent(counter)
            self.assertEqual(problem.initial_value(fluent()).constant_value(), 0)

    def test_too_few_cells_is_rejected(self):
        domain_config, _ = self._get_configs()[0]
        gen = OnlyCraftGenerator(domain_config)
        # 4 trees are needed for one pogo stick, so 3 cells cannot hold them
        too_small = Configuration(
            gen.instance_parameter_space, {"n_cells": 3, "n_pogo_sticks": 1}
        )
        self.assertFalse(gen.check_instance_parameters(too_small))
        with self.assertRaises(ValueError):
            gen.get_instance(too_small)

    # NOTE the validation cases of the base class use the temporal plan
    # validator, while onlycraft is an instantaneous domain, so the sequential
    # plans are validated here instead.
    def test_sequential_validation(self):
        domain_config, instance_config = self._get_configs()[0]
        gen = OnlyCraftGenerator(domain_config)
        problem = gen.get_instance(instance_config)

        # two trees give 4 logs: one becomes the planks and the sticks, one
        # becomes the pellet, and cell0 carries the crafting table
        valid_plan = """(break_brutal cell0)
(break_brutal cell1)
(craft_plank)
(craft_stick)
(craft_synthetic_pellets)
(craft_wooden_pogo cell0)"""
        # without the pellet CRAFT_WOODEN_POGO is not applicable
        invalid_plan = """(break_brutal cell0)
(break_brutal cell1)
(craft_plank)
(craft_stick)
(craft_wooden_pogo cell0)"""

        for plan_str, expected in [
            (valid_plan, ValidationResultStatus.VALID),
            (invalid_plan, ValidationResultStatus.INVALID),
        ]:
            plan = parse_plan_string(problem, plan_str)
            with SequentialPlanValidator() as validator:
                v_res = validator.validate(problem, plan)
                self.assertEqual(v_res.status, expected, f"bad res:\n{v_res}")
