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
from fractions import Fraction

from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Categorical,
    Constant,
)
from unified_planning.io import PDDLReader
from unified_planning.model import Problem, Object, FNode
from unified_planning.shortcuts import TRUE, UserType, Real, FALSE, Int
from typing import Any
import math

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"


class MatchCellarGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        mapping["variant"] = Categorical(
            "variant",
            ["ipc", "variable_duration", "legacy"],
            default="ipc",
        )
        return ConfigurationSpace(name=mapping)

    def __init__(self, domain_params: Configuration):
        domain_params.check_valid_configuration()
        if (
            domain_params.config_space
            != MatchCellarGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        self._Match = self._domain.user_type("match")
        self._Fuse = self._domain.user_type("fuse")
        self._mended = self._domain.fluent("mended")
        if self.variant == "legacy":
            self._match_used = self._domain.fluent("match_used")
        else:
            self._unused = self._domain.fluent("unused")
        self._handfree = self._domain.fluent("handfree")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant in ["ipc", "variable_duration"]:
            mapping["n_matches"] = Integer("n_matches", (0, MAX_INT), default=10)
            mapping["n_fuses"] = Integer("n_fuses", (0, MAX_INT), default=16)
        elif self.variant == "legacy":
            mapping["n_matches_fuses"] = Integer(
                "n_matches_fuses", (1, MAX_INT), default=10
            )
            mapping["total"] = Integer("total", (1, MAX_INT), default=15)
        else:
            raise ValueError(f"invalid variant {self.variant}")
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"MatchCellar V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        reader = PDDLReader()
        if self.version == 1:
            if self.variant == "ipc":
                return reader.parse_problem(
                    str(RESOURCES_PATH / f"matchcellar_v{self.version}.pddl")
                )
            elif self.variant == "variable_duration":
                return reader.parse_problem(
                    str(RESOURCES_PATH / f"matchcellar_variable_duration.pddl")
                )
            elif self.variant == "legacy":
                return reader.parse_problem(
                    str(RESOURCES_PATH / f"matchcellar_legacy.pddl")
                )
        raise ValueError(
            f"Unknown domain version {self.version} or variant {self.variant}"
        )

    def _get_object(self, name: str, type: UserType):
        res = self._object_cache.get((name, type), None)
        if res is None:
            res = Object(name, type)
            self._object_cache[(name, type)] = res
        return res

    def get_objects(self, params) -> list[Object]:
        params.check_valid_configuration()
        objs = []
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        if self.variant in ["ipc", "variable_duration"]:
            for i in range(params["n_matches"]):
                objs.append(self._get_object(f"match{i}", self._Match))
            for i in range(params["n_fuses"]):
                objs.append(self._get_object(f"fuse{i}", self._Fuse))
        elif self.variant == "legacy":
            for i in range(params["n_matches_fuses"]):
                objs.append(self._get_object(f"m{i}", self._Match))
                objs.append(self._get_object(f"f{i}", self._Fuse))
        else:
            raise ValueError(f"invalid variant {self.variant}")
        return objs

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if self.variant in ["ipc", "variable_duration"]:
            if instance_parameters_space is None:
                instance_parameters_space = self.instance_parameter_space
            _, matches_upper = hyperparam_range(instance_parameters_space["n_matches"])
            _, fuses_upper = hyperparam_range(instance_parameters_space["n_fuses"])
            return [
                self._get_object(f"match{i}", self._Match) for i in range(matches_upper)
            ] + [self._get_object(f"fuse{i}", self._Fuse) for i in range(fuses_upper)]
        elif self.variant == "legacy":
            if instance_parameters_space is None:
                instance_parameters_space = self.instance_parameter_space
            _, matches_upper = hyperparam_range(
                instance_parameters_space["n_matches_fuses"]
            )
            _, total_upper = hyperparam_range(instance_parameters_space["total"])
            actual_upper_limit = max(matches_upper, total_upper)
            return [
                self._get_object(f"m{i}", self._Match)
                for i in range(actual_upper_limit)
            ] + [
                self._get_object(f"f{i}", self._Fuse) for i in range(actual_upper_limit)
            ]
        else:
            raise ValueError(f"invalid variant {self.variant}")

    def get_goal(self, params) -> list[FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")
        res = []
        if self.variant in ["ipc", "variable_duration"]:
            for i in range(params["n_fuses"]):
                res.append(self._mended(self._get_object(f"fuse{i}", self._Fuse)))
        elif self.variant == "legacy":
            for i in range(params["n_matches_fuses"]):
                res.append(self._mended(self._get_object(f"f{i}", self._Fuse)))
        else:
            raise ValueError(f"invalid variant {self.variant}")
        return res

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")
        res = {self._handfree(): TRUE()}
        if self.variant in ["ipc", "variable_duration"]:
            for i in range(params["n_matches"]):
                res[self._unused(self._get_object(f"match{i}", self._Match))] = TRUE()

            if self.variant == "variable_duration":
                for i in range(params["n_matches"]):
                    res[
                        self._domain.fluent("match-duration")(
                            self._get_object(f"match{i}", self._Match)
                        )
                    ] = 5
                for i in range(params["n_fuses"]):
                    res[
                        self._domain.fluent("fuse-duration")(
                            self._get_object(f"fuse{i}", self._Fuse)
                        )
                    ] = 2
        elif self.variant == "legacy":
            res[self._domain.fluent("mend_fuse_duration")()] = Real(Fraction(6, 1))
            for i in range(params["n_matches_fuses"]):
                res[self._match_used(self._get_object(f"m{i}", self._Match))] = FALSE()
        else:
            raise ValueError(f"invalid variant {self.variant}")
        return res

    def check_instance_parameters(self, params: Configuration):
        if self.variant == "ipc" and params["n_fuses"] > 2 * params["n_matches"]:
            return False
        if (
            self.variant == "variable_duration"
            and params["n_fuses"] > 2 * params["n_matches"]
        ):
            # NOTE seems that for now the durations are hardcoded to be set the same way as ipc
            return False
        if self.variant in ["legacy"]:
            # this specific variants are always valid
            return True
        return True
