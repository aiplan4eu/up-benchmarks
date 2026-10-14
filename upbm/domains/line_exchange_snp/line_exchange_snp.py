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

from .resources.ipc_line_exchange_snp_data import IPC_INSTANCES


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# Only used for the bounded_5 variant
MAX_ROBOTS = 5


class LineExchangeSnpGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        mapping["variant"] = Categorical(
            "variant",
            [
                "ipc",  # index to the problem data stored in a separate file
                "bounded_5",  # limit to 5 robots, can specify the load value for each
                "unbounded_random",  # unlimited number of robots, initial load drawn with parameters
            ],
            default="bounded_5",
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
        if self.variant == "ipc":
            indices = sorted(IPC_INSTANCES)
            mapping["index"] = Integer(
                "index", (indices[0], indices[-1]), default=indices[0]
            )
            return ConfigurationSpace(name=mapping)
        if self.variant not in ("bounded_5", "unbounded_random"):
            raise ValueError(f"invalid variant {self.variant}")
        mapping["n_robots"] = Integer(
            "n_robots",
            (2, MAX_ROBOTS if self.variant == "bounded_5" else MAX_INT),
            default=3,
        )
        mapping["segment_length"] = Integer("segment_length", (1, MAX_INT), default=50)

        if self.variant == "bounded_5":
            for slot, default in enumerate([3, 6, 6, 0, 0]):
                mapping[f"q_{slot}"] = Integer(
                    f"q_{slot}", (0, MAX_INT), default=default
                )
        else:
            mapping["mean_load"] = Integer("mean_load", (0, MAX_INT), default=10)
            mapping["seed"] = Integer("seed", (0, MAX_INT), default=42)
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

    def _row(self, params) -> dict:
        """The table row an "ipc" instance is built from."""
        return IPC_INSTANCES[params["index"]]

    def n_robots(self, params) -> int:
        """How many robots are on the line.

        A parameter under "bounded_5" and "unbounded_random"; table data under
        "ipc", where the index is the only parameter there is.
        """
        if self.variant == "ipc":
            return self._row(params)["n_robots"]
        return params["n_robots"]

    def segment_length(self, params) -> int:
        """The (D) fluent, likewise a parameter except under "ipc"."""
        if self.variant == "ipc":
            return self._row(params)["segment_length"]
        return params["segment_length"]

    def _loads(self, params) -> List[int]:
        """The load of each robot, in order.

        One line per variant: "ipc" reads the shipped loads out of the table,
        "bounded_5" reads them off the q slots, ignoring the unused ones, and
        "unbounded_random" draws them.
        """
        if self.variant == "ipc":
            return list(self._row(params)["loads"])
        if self.variant == "bounded_5":
            return [params[f"q_{slot}"] for slot in range(params["n_robots"])]
        return self._drawn_loads(params)

    @staticmethod
    def _drawn_loads(params) -> List[int]:
        """Loads drawn by cutting the total load into random pieces.

        The total is n_robots * mean_load. It is cut at n_robots - 1 random
        points, and each robot gets the piece between two neighbouring cuts,
        so no load is negative and the loads add up to the total.

        That is all the goal needs: since the total divides evenly, every
        robot can end up holding mean_load.
        """
        n_robots = params["n_robots"]
        total = n_robots * params["mean_load"]
        rng = random.Random(params["seed"])
        cuts = sorted(rng.randint(0, total) for _ in range(n_robots - 1))
        return [end - start for start, end in zip([0] + cuts, cuts + [total])]

    def _home(self, params, i: int) -> Fraction:
        """Where robot i starts, and has to be again at the end.

        Every shipped instance puts robot i in the middle of its own segment,
        at D/2 + i*D.
        """
        d = Fraction(self.segment_length(params))
        return d / 2 + i * d

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        return [self._robot(i) for i in range(self.n_robots(params))]

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        if self.variant == "ipc":
            first, last = hyperparam_range(instance_parameters_space["index"])
            robots_upper = max(
                entry["n_robots"]
                for index, entry in IPC_INSTANCES.items()
                if first <= index <= last
            )
            return [self._robot(i) for i in range(robots_upper)]
        _, robots_upper = hyperparam_range(instance_parameters_space["n_robots"])
        return [self._robot(i) for i in range(robots_upper)]

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        n_robots = self.n_robots(params)
        res = [
            Equals(self._x(self._robot(i)), Real(self._home(params, i)))
            for i in range(n_robots)
        ]
        for i in range(n_robots - 1):
            res.append(Equals(self._q(self._robot(i)), self._q(self._robot(i + 1))))
        return res

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        n_robots = self.n_robots(params)
        res: dict[FNode, FNode] = {self._d(): self.segment_length(params)}
        for i, load in enumerate(self._loads(params)):
            robot = self._robot(i)
            res[self._i(robot)] = i
            res[self._x(robot)] = Real(self._home(params, i))
            res[self._q(robot)] = load
            if i + 1 < n_robots:
                res[self._next(robot, self._robot(i + 1))] = TRUE()
        return res

    def check_instance_parameters(self, params: Configuration):
        # An exchange moves one unit from a robot to its neighbour, so the
        # total load never changes. The goal asks for every robot to hold the
        # same amount, which is only reachable when that total splits evenly.
        # the only variant where this could be wrong is "bounded_5".
        if self.variant != "bounded_5":
            return True
        return sum(self._loads(params)) % params["n_robots"] == 0
