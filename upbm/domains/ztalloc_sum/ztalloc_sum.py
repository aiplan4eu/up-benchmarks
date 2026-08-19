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

from functools import reduce
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
from unified_planning.shortcuts import TRUE, Equals, Plus

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# Every register of every IPC instance starts holding this value.
INITIAL_REGISTER_VALUE = 1


class ZtallocSumGenerator(Generator):
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
        if (
            domain_params.config_space
            != ZtallocSumGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Register = self._domain.user_type("register")
        self._free = self._domain.fluent("free")
        self._normal = self._domain.fluent("normal")
        self._value = self._domain.fluent("value")
        self._work_value = self._domain.fluent("work-value")
        self._total_cost = self._domain.fluent("total-cost")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant != "ipc":
            raise ValueError(f"invalid variant {self.variant}")
        # the IPC instances use 3 to 6 registers and targets from 187 to 12347,
        # the defaults here reproduce the smallest one
        mapping["n_registers"] = Integer("n_registers", (1, MAX_INT), default=3)
        mapping["target"] = Integer("target", (1, MAX_INT), default=187)
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"ZtallocSum V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            domain = reader.parse_problem(
                str(RESOURCES_PATH / f"ztalloc_sum_v{self.version}.pddl")
            )
            # The domain counts every operation in total-cost, and the point is
            # reaching the target in as few steps as possible, so the metric
            # belongs to the domain. Problem.clone() copies it into instances.
            domain.add_quality_metric(
                MinimizeExpressionOnFinalState(domain.fluent("total-cost")())
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
            self._get_object(f"r{i + 1}", self._Register)
            for i in range(params["n_registers"])
        ]

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        _, registers_upper = hyperparam_range(instance_parameters_space["n_registers"])
        return [
            self._get_object(f"r{i + 1}", self._Register)
            for i in range(registers_upper)
        ]

    def get_goal(self, params) -> List[FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")
        registers = self.get_objects(params)
        # the registers must add up to the target, and every one of them has to
        # be back to a normal state, so no half finished division is counted
        total = reduce(Plus, [self._value(r) for r in registers])
        res = [Equals(total, params["target"]), self._free()]
        for r in registers:
            res.append(self._normal(r))
            res.append(Equals(self._work_value(r), 0))
        return res

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")
        res: dict[FNode, FNode] = {
            self._free(): TRUE(),
            self._total_cost(): 0,
        }
        for r in self.get_objects(params):
            res[self._normal(r)] = TRUE()
            res[self._value(r)] = INITIAL_REGISTER_VALUE
            res[self._work_value(r)] = 0
        return res

    def check_instance_parameters(self, params: Configuration):
        # Every register starts at 1 and can be doubled or reduced with the
        # reversed Collatz step, so it can reach any value (assuming the Collatz
        # conjecture holds, as the domain description itself notes). A register
        # can also be brought down to 0, so any positive target is reachable
        # whatever the number of registers.
        return True
