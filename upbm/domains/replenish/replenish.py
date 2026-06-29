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
from typing import Iterator, Optional, Tuple, Dict, List, Union, Iterable, Any
import unified_planning as up
from unified_planning.shortcuts import (
    Problem,
    UserType,
    Object,
    Fluent,
    IntType,
    BoolType,
    Int,
    Not,
    StartTiming,
    EndTiming,
    Equals,
    DurativeAction,
    Plus,
    Minus,
    GT,
)
from unified_planning.model.walkers import AnyChecker
from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Constant,
)
from typing import Any

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


class ReplenishGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space() -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        mapping["max_goal_sequence_length"] = Integer(
            "max_goal_sequence_length", (1, MAX_INT), default=20
        )
        return ConfigurationSpace(name=mapping)

    def __init__(self, domain_params: Configuration) -> None:
        super().__init__(domain_params)
        domain_params.check_valid_configuration()
        if domain_params.config_space != self.get_domain_parameter_space():
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self._max_goal_sequence_length = domain_params["max_goal_sequence_length"]

        self._build_box_time = [3, 4, 5, 3, 5]
        self._type_capacity = [4, 5, 6, 4, 6]
        self._global_max_capacities = max(self._type_capacity)
        self._time_replenish_same_type = [6, 7, 8, 6, 8]
        self._time_replenish_new_type = [8, 9, 10, 8, 10]
        self._time_empty = [5, 6, 7, 5, 7]

        self._values_lists_len = min(
            [
                len(self._build_box_time),
                len(self._type_capacity),
                len(self._time_replenish_same_type),
                len(self._time_replenish_new_type),
                len(self._time_empty),
            ]
        )

        self._domain = self._build_domain()

        self._CardboardType = self._domain.user_type("CardboardType")
        self._Drawer = self._domain.user_type("Drawer")

        self._object_cache: Dict[Tuple[str, UserType], Object] = {}

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        return ConfigurationSpace(
            {
                "n_cardboard_types": Integer(
                    "n_cardboard_types", (1, MAX_INT), default=5
                ),
                "n_drawers": Integer("n_drawers", (1, MAX_INT), default=20),
                "goal_sequence_length": Integer(
                    "goal_sequence_length", (1, self._max_goal_sequence_length)
                ),
                "sequence_seed": (0, MAX_INT),
            }
        )

    @property
    def name(self) -> str:
        return f"Replenish V{self.domain_params['version']}"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _get_object(self, name: str, type: UserType) -> Object:
        res = self._object_cache.get((name, type))
        if res is None:
            res = Object(name, type)
            self._object_cache[(name, type)] = res
        return res

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ) -> Iterable[Object]:
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        objs = [self._domain.object("no_type")]

        _, cardboard_upper = hyperparam_range(
            instance_parameters_space["n_cardboard_types"]
        )
        _, drawers_upper = hyperparam_range(instance_parameters_space["n_drawers"])

        for i in range(1, cardboard_upper + 1):
            objs.append(self._get_object(f"cardboard_type_{i}", self._CardboardType))
        for i in range(drawers_upper):
            objs.append(self._get_object(f"drawer_{i}", self._Drawer))
        return objs

    def get_objects(self, params: Configuration) -> Iterable[Object]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

        objs = []
        for i in range(1, params["n_cardboard_types"] + 1):
            objs.append(self._get_object(f"cardboard_type_{i}", self._CardboardType))
        for i in range(params["n_drawers"]):
            objs.append(self._get_object(f"drawer_{i}", self._Drawer))
        return objs

    def _build_domain(self) -> up.model.Problem:
        domain = Problem("Replenish")

        CardboardType = UserType("CardboardType")
        Drawer = UserType("Drawer")

        no_type = Object("no_type", CardboardType)
        domain.add_object(no_type)

        # Constants
        max_type_capacity = Fluent(
            "max_type_capacity",
            IntType(0, self._global_max_capacities),
            t=CardboardType,
        )
        build_box_time = Fluent("build_box_time", IntType(0, 10), t=CardboardType)
        time_replenish_same_type = Fluent(
            "time_replenish_same_type", IntType(0, 10), t=CardboardType
        )
        time_replenish_new_type = Fluent(
            "time_replenish_new_type", IntType(0, 10), t=CardboardType
        )
        time_empty = Fluent("time_empty", IntType(0, 10), t=CardboardType)

        domain.add_fluent(max_type_capacity, default_initial_value=Int(0))
        domain.add_fluent(build_box_time, default_initial_value=Int(0))
        domain.add_fluent(time_replenish_same_type, default_initial_value=Int(0))
        domain.add_fluent(time_replenish_new_type, default_initial_value=Int(0))
        domain.add_fluent(time_empty, default_initial_value=Int(0))

        # Setting up Objects and Fluents
        drawer_type = Fluent("drawer_type", CardboardType, d=Drawer)
        drawer_occupancy = Fluent(
            "drawer_occupancy", IntType(0, self._global_max_capacities), d=Drawer
        )
        drawer_busy = Fluent("drawer_busy", BoolType(), d=Drawer)
        drawer_initialized = Fluent("drawer_initialized", BoolType(), d=Drawer)
        domain.add_fluent(drawer_type, default_initial_value=no_type)
        domain.add_fluent(drawer_occupancy, default_initial_value=Int(0))
        domain.add_fluent(drawer_busy, default_initial_value=False)
        domain.add_fluent(drawer_initialized, default_initial_value=False)

        # to define goals
        # create a fluent that keeps track of the progress in the goal sequence
        goal_progress = Fluent(
            "goal_progress", IntType(0, self._max_goal_sequence_length)
        )  # counts how many goals have been completed
        target_sequence_fluent = Fluent(
            "target_sequence_fluent",
            CardboardType,
            idx=IntType(0, self._max_goal_sequence_length - 1),
        )  # fluent to access the goal sequence
        goal_busy = Fluent(
            "goal_busy", BoolType()
        )  # to ensure only one goal is being worked on at a time
        domain.add_fluent(goal_progress, default_initial_value=Int(0))
        domain.add_fluent(target_sequence_fluent, default_initial_value=no_type)
        domain.add_fluent(goal_busy, default_initial_value=False)

        # Setting up Actions
        initializeDrawer = DurativeAction(
            "initializeDrawer",
            d=Drawer,
            c=CardboardType,
            load=IntType(0, self._global_max_capacities),
        )
        d = initializeDrawer.parameter("d")
        c = initializeDrawer.parameter("c")
        load = initializeDrawer.parameter("load")
        initializeDrawer.set_fixed_duration(Int(1))
        initializeDrawer.add_condition(StartTiming(), Not(drawer_initialized(d)))
        initializeDrawer.add_condition(
            StartTiming(), Equals(load, max_type_capacity(c))
        )
        initializeDrawer.add_condition(
            StartTiming(), Not(Equals(c, no_type))
        )  # cannot initialize to no_type
        initializeDrawer.add_effect(StartTiming(), drawer_initialized(d), True)
        initializeDrawer.add_effect(EndTiming(), drawer_type(d), c)
        initializeDrawer.add_effect(
            EndTiming(), drawer_occupancy(d), max_type_capacity(c)
        )
        domain.add_action(initializeDrawer)

        build_box = DurativeAction(
            "build_box",
            d=Drawer,
            c=CardboardType,
            idx=IntType(0, self._max_goal_sequence_length - 1),
        )
        c = build_box.parameter("c")
        d = build_box.parameter("d")
        idx = build_box.parameter("idx")
        build_box.set_fixed_duration(build_box_time(c))
        build_box.add_condition(StartTiming(), drawer_initialized(d))
        build_box.add_condition(StartTiming(), Equals(drawer_type(d), c))
        build_box.add_condition(StartTiming(), Not(drawer_busy(d)))
        build_box.add_condition(StartTiming(), GT(drawer_occupancy(d), 0))
        build_box.add_condition(
            StartTiming(), Equals(idx, goal_progress)
        )  # ensure we are building the current goal in the sequence
        build_box.add_condition(
            StartTiming(), Equals(c, target_sequence_fluent(idx))
        )  # ensure we are building the current goal
        build_box.add_condition(
            StartTiming(), Not(goal_busy)
        )  # only one goal at a time
        build_box.add_effect(StartTiming(), drawer_busy(d), True)
        build_box.add_effect(StartTiming(), goal_busy, True)
        build_box.add_effect(EndTiming(), goal_busy, False)
        build_box.add_effect(EndTiming(), drawer_busy(d), False)
        build_box.add_effect(
            EndTiming(), drawer_occupancy(d), Minus(drawer_occupancy(d), Int(1))
        )
        build_box.add_effect(EndTiming(), goal_progress, Plus(goal_progress, Int(1)))
        domain.add_action(build_box)

        replenish_drawer_same_type = DurativeAction(
            "replenish_drawer_same_type", d=Drawer, c=CardboardType
        )
        c = replenish_drawer_same_type.parameter("c")
        d = replenish_drawer_same_type.parameter("d")
        replenish_drawer_same_type.set_fixed_duration(time_replenish_same_type(c))
        replenish_drawer_same_type.add_condition(StartTiming(), drawer_initialized(d))
        replenish_drawer_same_type.add_condition(
            StartTiming(), Equals(drawer_type(d), c)
        )
        replenish_drawer_same_type.add_condition(StartTiming(), Not(drawer_busy(d)))
        replenish_drawer_same_type.add_effect(StartTiming(), drawer_busy(d), True)
        replenish_drawer_same_type.add_effect(
            EndTiming(), drawer_occupancy(d), max_type_capacity(c)
        )
        replenish_drawer_same_type.add_effect(EndTiming(), drawer_busy(d), False)
        domain.add_action(replenish_drawer_same_type)

        replenish_drawer_new_type = DurativeAction(
            "replenish_drawer_new_type", d=Drawer, c=CardboardType
        )
        c = replenish_drawer_new_type.parameter("c")
        d = replenish_drawer_new_type.parameter("d")
        replenish_drawer_new_type.set_fixed_duration(time_replenish_new_type(c))
        replenish_drawer_new_type.add_condition(StartTiming(), drawer_initialized(d))
        replenish_drawer_new_type.add_condition(
            StartTiming(), Not(Equals(drawer_type(d), c))
        )
        replenish_drawer_new_type.add_condition(
            StartTiming(), Equals(drawer_occupancy(d), Int(0))
        )
        replenish_drawer_new_type.add_condition(StartTiming(), Not(drawer_busy(d)))
        replenish_drawer_new_type.add_effect(StartTiming(), drawer_busy(d), True)
        replenish_drawer_new_type.add_effect(
            EndTiming(), drawer_occupancy(d), max_type_capacity(c)
        )
        replenish_drawer_new_type.add_effect(EndTiming(), drawer_type(d), c)
        replenish_drawer_new_type.add_effect(EndTiming(), drawer_busy(d), False)
        domain.add_action(replenish_drawer_new_type)

        empty_drawer = DurativeAction("empty_drawer", d=Drawer, c=CardboardType)
        c = empty_drawer.parameter("c")
        d = empty_drawer.parameter("d")
        empty_drawer.set_fixed_duration(time_empty(c))
        empty_drawer.add_condition(StartTiming(), Equals(drawer_type(d), c))
        empty_drawer.add_condition(StartTiming(), drawer_initialized(d))
        empty_drawer.add_condition(StartTiming(), Not(drawer_busy(d)))
        empty_drawer.add_effect(StartTiming(), drawer_busy(d), True)
        empty_drawer.add_effect(EndTiming(), drawer_occupancy(d), Int(0))
        empty_drawer.add_effect(EndTiming(), drawer_busy(d), False)
        domain.add_action(empty_drawer)

        return domain

    def get_initial_state(
        self, params: Configuration
    ) -> Dict[up.model.FNode, up.model.FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

        rng = random.Random(params["sequence_seed"])
        goal_sequence = rng.choices(
            range(1, params["n_cardboard_types"] + 1), k=params["goal_sequence_length"]
        )

        # initial values
        initial_values = {}
        objects = list(self.get_objects(params))
        objects.append(self._domain.object("no_type"))

        c = AnyChecker(lambda x: x.is_object_exp() and x.object() not in objects)
        for k, v in self._domain.initial_values.items():
            if c.any(k):
                continue
            initial_values[k] = v

        max_type_capacity = self._domain.fluent("max_type_capacity")
        build_box_time = self._domain.fluent("build_box_time")
        time_replenish_same_type = self._domain.fluent("time_replenish_same_type")
        time_replenish_new_type = self._domain.fluent("time_replenish_new_type")
        time_empty = self._domain.fluent("time_empty")

        for i in range(1, params["n_cardboard_types"] + 1):
            ct = self._get_object(f"cardboard_type_{i}", self._CardboardType)
            initial_values[max_type_capacity(ct)] = Int(
                self._type_capacity[(i - 1) % self._values_lists_len]
            )
            initial_values[build_box_time(ct)] = Int(
                self._build_box_time[(i - 1) % self._values_lists_len]
            )
            initial_values[time_replenish_same_type(ct)] = Int(
                self._time_replenish_same_type[(i - 1) % self._values_lists_len]
            )
            initial_values[time_replenish_new_type(ct)] = Int(
                self._time_replenish_new_type[(i - 1) % self._values_lists_len]
            )
            initial_values[time_empty(ct)] = Int(
                self._time_empty[(i - 1) % self._values_lists_len]
            )

        target_sequence_fluent = self._domain.fluent("target_sequence_fluent")
        for i, g in enumerate(goal_sequence):
            ct = self._get_object(f"cardboard_type_{g}", self._CardboardType)
            initial_values[
                target_sequence_fluent(Int(i))
            ] = self._domain.environment.expression_manager.ObjectExp(ct)

        return initial_values

    @property
    def pddl_expressible(self) -> bool:
        return False

    def get_goal(self, params: Configuration) -> List[up.model.FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

        goal_progress = self._domain.fluent("goal_progress")
        return [Equals(goal_progress, Int(params["goal_sequence_length"]))]
