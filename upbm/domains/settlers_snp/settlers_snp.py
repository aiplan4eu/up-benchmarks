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
from unified_planning.model.metrics import MinimizeExpressionOnFinalState
from unified_planning.shortcuts import TRUE, GE, Plus, Times

from upbm.generator import Generator
from upbm.utils import is_subspace, hyperparam_range

from .resources.ipc_settlers_snp_data import IPC_INSTANCES


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"


class SettlersSnpGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
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
            != SettlersSnpGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Place = self._domain.user_type("place")
        self._Vehicle = self._domain.user_type("vehicle")
        # The six resources (ore, iron, stone, wood, timber, coal) are
        # constants of the domain file, so they already exist in the skeleton
        # and are not objects an instance adds.
        self._resources = list(self._domain.objects(self._domain.user_type("resource")))
        self._available = self._domain.fluent("available")
        self._space_in = self._domain.fluent("space-in")
        self._housing = self._domain.fluent("housing")
        self._potential = self._domain.fluent("potential")
        self._land = self._domain.fluent("connected-by-land")
        self._sea = self._domain.fluent("connected-by-sea")
        self._labour = self._domain.fluent("labour")
        self._resource_use = self._domain.fluent("resource-use")
        self._pollution = self._domain.fluent("pollution")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant != "ipc":
            raise ValueError(f"invalid variant {self.variant}")
        # The shipped instances carry no record of how they were made - no
        # seed, no parameters - and each one is a random map (terrain and
        # connections) plus a hand-picked goal. So they are transcribed into a
        # table rather than described by parameters, and the index is the whole
        # parameter space: the number in the shipped file name, 1..20 with no
        # gaps.
        indices = sorted(IPC_INSTANCES)
        mapping["index"] = Integer(
            "index", (indices[0], indices[-1]), default=indices[0]
        )
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"SettlersSnp V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            domain = reader.parse_problem(
                str(RESOURCES_PATH / f"settlers_snp_v{self.version}.pddl")
            )
            # Every shipped instance asks for the same metric, so it belongs to
            # the domain; Problem.clone() copies it into every instance. The
            # weights of 1 are kept as the shipped files write them, so this is
            # the same expression UP's reader builds from a shipped file.
            # NOTE PDDLWriter leaves out a factor of 1 when it writes, so the
            # written metric is just the sum - the same happens to a shipped
            # file written back out.
            domain.add_quality_metric(
                MinimizeExpressionOnFinalState(
                    Plus(
                        Plus(
                            Times(1, domain.fluent("pollution")()),
                            Times(1, domain.fluent("resource-use")()),
                        ),
                        Times(1, domain.fluent("labour")()),
                    )
                )
            )
            return domain
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

    def _place(self, i: int) -> Object:
        return self._get_object(f"location{i}", self._Place)

    def _vehicle(self, i: int) -> Object:
        return self._get_object(f"vehicle{i}", self._Vehicle)

    def _row(self, params) -> dict:
        """The table row the instance is built from."""
        return IPC_INSTANCES[params["index"]]

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        row = self._row(params)
        return [self._place(i) for i in range(len(row["places"]))] + [
            self._vehicle(i) for i in range(row["n_vehicles"])
        ]

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        # The reachable rows decide the universe, so a narrowed `index` range
        # gives a smaller one.
        first, last = hyperparam_range(instance_parameters_space["index"])
        reachable = [
            entry for index, entry in IPC_INSTANCES.items() if first <= index <= last
        ]
        places_upper = max(len(entry["places"]) for entry in reachable)
        vehicles_upper = max(entry["n_vehicles"] for entry in reachable)
        return [self._place(i) for i in range(places_upper)] + [
            self._vehicle(i) for i in range(vehicles_upper)
        ]

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        res = []
        for name, *args in self._row(params)["goals"]:
            if name == "housing":
                place, level = args
                res.append(GE(self._housing(self._place(place)), level))
            else:
                # a building at a place, or a rail between two places: the
                # table stores the predicate name as the domain spells it
                predicate = self._domain.fluent(name)
                res.append(predicate(*[self._place(p) for p in args]))
        return res

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        row = self._row(params)
        # Nothing has happened yet: every counter and every stock is 0, and
        # nothing is built anywhere.
        res: dict[FNode, FNode] = {
            self._labour(): 0,
            self._resource_use(): 0,
            self._pollution(): 0,
        }
        for i, terrain in enumerate(row["places"]):
            place = self._place(i)
            for predicate in terrain:
                res[self._domain.fluent(predicate)(place)] = TRUE()
            res[self._housing(place)] = 0
            for resource in self._resources:
                res[self._available(resource, place)] = 0
        # A vehicle starts out `potential`: it exists only as something a
        # build action can turn into a cart, a train or a ship, which is also
        # where it gets its position and its space.
        for i in range(row["n_vehicles"]):
            vehicle = self._vehicle(i)
            res[self._potential(vehicle)] = TRUE()
            res[self._space_in(vehicle)] = 0
            for resource in self._resources:
                res[self._available(resource, vehicle)] = 0
        # The table stores each connection once; the shipped files always
        # state both directions, so both are emitted.
        for relation, edges in ((self._land, row["land"]), (self._sea, row["sea"])):
            for a, b in edges:
                res[relation(self._place(a), self._place(b))] = TRUE()
                res[relation(self._place(b), self._place(a))] = TRUE()
        return res

    def check_instance_parameters(self, params: Configuration):
        # Every index is a shipped IPC instance, rebuilt as it was shipped.
        return True
