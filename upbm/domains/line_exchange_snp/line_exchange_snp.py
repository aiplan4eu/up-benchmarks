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

from fractions import Fraction
from pathlib import Path
from typing import Any, List, Optional

from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Categorical,
    Constant,
)
from unified_planning.io import PDDLReader
from unified_planning.model import Problem, Object, FNode
from unified_planning.shortcuts import TRUE, Equals, Real

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# How many robots the generator can describe. The IPC set uses 3 to 5, and each
# robot needs its own load parameter (see instance_parameter_space), so the
# number of those slots is what sets this ceiling.
MAX_ROBOTS = 5


class LineExchangeSnpGenerator(Generator):
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
            != LineExchangeSnpGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Robot = self._domain.user_type("robot")
        # the PDDL calls the segment length (D); the reader lowercases it
        self._d = self._domain.fluent("d")
        self._i = self._domain.fluent("i")
        self._x = self._domain.fluent("x")
        self._q = self._domain.fluent("q")
        self._next = self._domain.fluent("next")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant != "ipc":
            raise ValueError(f"invalid variant {self.variant}")
        # The IPC set uses 3, 4 or 5 robots; two is the smallest line that can
        # exchange anything at all.
        mapping["n_robots"] = Integer("n_robots", (2, MAX_ROBOTS), default=3)
        # The (D) function: each robot owns the segment [D*i, D*(i+1)]. The IPC
        # set uses 10, 50 and 100.
        mapping["segment_length"] = Integer("segment_length", (1, MAX_INT), default=50)
        # One load per robot. The shipped instances draw these at random and
        # record no seed, so the only way to reproduce them exactly is to state
        # each load; the mean and imbalance in the file names cannot be
        # inverted. Slots from n_robots upwards are ignored.
        # The defaults reproduce the instance named 3_5_50_50.
        for slot, default in enumerate([3, 6, 6, 0, 0]):
            mapping[f"q_{slot}"] = Integer(f"q_{slot}", (0, MAX_INT), default=default)
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"LineExchangeSnp V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            # The shipped instances define no :metric, so no quality metric is
            # attached to the skeleton either.
            return reader.parse_problem(
                str(RESOURCES_PATH / f"line_exchange_snp_v{self.version}.pddl")
            )
        raise ValueError(f"Unknown domain version {self.version}")

    def _get_object(self, name: str, type: Any):
        res = self._object_cache.get((name, type), None)
        if res is None:
            res = Object(name, type)
            self._object_cache[(name, type)] = res
        return res

    def _check_params(self, params: Configuration) -> None:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

    def _robot(self, i: int) -> Object:
        return self._get_object(f"r{i}", self._Robot)

    @staticmethod
    def _loads(params) -> List[int]:
        """The load of each robot, in order, ignoring the unused slots."""
        return [params[f"q_{slot}"] for slot in range(params["n_robots"])]

    @staticmethod
    def _home(params, i: int) -> Fraction:
        """Where robot i starts, and has to be again at the end.

        Every shipped instance puts robot i in the middle of its own segment,
        at D/2 + i*D.
        """
        d = Fraction(params["segment_length"])
        return d / 2 + i * d

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        return [self._robot(i) for i in range(params["n_robots"])]

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        _, robots_upper = hyperparam_range(instance_parameters_space["n_robots"])
        return [self._robot(i) for i in range(robots_upper)]

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        n_robots = params["n_robots"]
        # every robot back where it started ...
        res = [
            Equals(self._x(self._robot(i)), Real(self._home(params, i)))
            for i in range(n_robots)
        ]
        # ... and the loads levelled out, stated as a chain of equalities
        # between neighbours exactly as the shipped instances do
        for i in range(n_robots - 1):
            res.append(Equals(self._q(self._robot(i)), self._q(self._robot(i + 1))))
        return res

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        n_robots = params["n_robots"]
        res: dict[FNode, FNode] = {self._d(): params["segment_length"]}
        for i, load in enumerate(self._loads(params)):
            robot = self._robot(i)
            res[self._i(robot)] = i
            res[self._x(robot)] = Real(self._home(params, i))
            res[self._q(robot)] = load
            if i + 1 < n_robots:
                res[self._next(robot, self._robot(i + 1))] = TRUE()
        # `ps` and `pd` both default to false and the shipped instances leave
        # them out too, so every robot starts free and unpaired.
        return res

    def check_instance_parameters(self, params: Configuration):
        # An exchange moves one unit from a robot to its neighbour, so the
        # total load never changes. The goal asks for every robot to hold the
        # same amount, which is only reachable when that total splits evenly.
        loads = LineExchangeSnpGenerator._loads(params)
        return sum(loads) % params["n_robots"] == 0
