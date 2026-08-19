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

from pathlib import Path
from typing import Any, Optional, List

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
from unified_planning.shortcuts import TRUE, Equals

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# The denominations used by every IPC instance.
IPC_DENOMINATIONS = [1, 2, 3, 5, 7]


class CoinsGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        # only the IPC variant exists for now, more can be added here later
        mapping["variant"] = Categorical(
            "variant",
            ["ipc"],
            default="ipc",
        )
        return ConfigurationSpace(name=mapping)

    def __init__(self, domain_params: Configuration):
        domain_params.check_valid_configuration()
        if domain_params.config_space != CoinsGenerator.get_domain_parameter_space():
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Coin = self._domain.user_type("coin")
        self._current_value = self._domain.fluent("current-value")
        self._coin_count = self._domain.fluent("coin-count")
        self._penalty = self._domain.fluent("penalty")
        self._denomination = self._domain.fluent("denomination")
        self._denomination_penalty = self._domain.fluent("denomination-penalty")
        self._no_coin_update = self._domain.fluent("no-coin-update")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant != "ipc":
            raise ValueError(f"invalid variant {self.variant}")
        # every IPC instance uses the same five denominations
        mapping["n_coins"] = Constant("n_coins", len(IPC_DENOMINATIONS))
        mapping["target"] = Integer("target", (1, MAX_INT), default=100)
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"Coins V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            domain = reader.parse_problem(
                str(RESOURCES_PATH / f"coins_v{self.version}.pddl")
            )
            # The point of this domain is reaching the target as cheaply as
            # possible, so the metric belongs to the domain rather than to a
            # single instance. Problem.clone() copies it into every instance.
            domain.add_quality_metric(
                MinimizeExpressionOnFinalState(domain.fluent("coin-count")())
            )
            return domain
        raise ValueError(f"Unknown domain version {self.version}")

    def _get_object(self, name: str, type: Any):
        res = self._object_cache.get((name, type), None)
        if res is None:
            res = Object(name, type)
            self._object_cache[(name, type)] = res
        return res

    def get_objects(self, params) -> List[Object]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        return [
            self._get_object(f"c{i + 1}", self._Coin) for i in range(params["n_coins"])
        ]

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        _, coins_upper = hyperparam_range(instance_parameters_space["n_coins"])
        return [self._get_object(f"c{i + 1}", self._Coin) for i in range(coins_upper)]

    def get_goal(self, params) -> List[FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")
        # The pending penalty must be paid off before the plan ends, otherwise
        # the last coins used would not be counted by coin-count.
        return [
            Equals(self._current_value(), params["target"]),
            Equals(self._penalty(), 0),
        ]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")
        res: dict[FNode, FNode] = {
            self._current_value(): 0,
            self._coin_count(): 0,
            self._penalty(): 0,
        }
        for coin, value in zip(self.get_objects(params), IPC_DENOMINATIONS):
            res[self._denomination(coin)] = value
            # Every coin starts with a penalty of one. Re-using the same coin
            # costs one more each time, see update-penalty in the domain file.
            res[self._denomination_penalty(coin)] = 1
            res[self._no_coin_update(coin)] = TRUE()
        return res

    def check_instance_parameters(self, params: Configuration):
        # The denomination set always starts at 1, so every positive target can
        # be reached and every instance in this space is solvable.
        return True
