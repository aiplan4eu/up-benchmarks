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
from unified_planning.shortcuts import TRUE, UserType, Real
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
            "variant", ["ipc", "variable_duration", "long_short_fuse"], default="ipc"
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
        elif self.variant == "long_short_fuse":
            mapping["short_fuses"] = Integer("short_fuses", (0, MAX_INT), default=5)
            mapping["long_fuses"] = Integer("long_fuses", (0, MAX_INT), default=5)
            mapping["shorts_in_one_match"] = Integer(
                "shorts_in_one_match", (1, MAX_INT), default=2
            )
            mapping["longs_in_one_match"] = Integer(
                "longs_in_one_match", (1, MAX_INT), default=1
            )
            mapping["extra_matches"] = Integer("extra_matches", (0, MAX_INT), default=0)
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
            elif self.variant == "long_short_fuse":
                return reader.parse_problem(
                    str(RESOURCES_PATH / f"matchcellar_long_short_fuse.pddl")
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
        elif self.variant == "long_short_fuse":
            for i in range(params["long_fuses"]):
                objs.append(self._get_object(f"long_fuse_{i}", self._Fuse))
            for i in range(params["short_fuses"]):
                objs.append(self._get_object(f"short_fuse_{i}", self._Fuse))
            useful_matches = math.ceil(
                params["short_fuses"] / params["shorts_in_one_match"]
            ) + math.ceil(params["long_fuses"] / params["longs_in_one_match"])
            for i in range(useful_matches + params["extra_matches"]):
                objs.append(self._get_object(f"match_{i}", self._Match))
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
        elif self.variant == "long_short_fuse":
            if instance_parameters_space is None:
                instance_parameters_space = self.instance_parameter_space
            _, short_fuses_upper = hyperparam_range(
                instance_parameters_space["short_fuses"]
            )
            _, long_fuses_upper = hyperparam_range(
                instance_parameters_space["long_fuses"]
            )
            _, extra_matches_upper = hyperparam_range(
                instance_parameters_space["extra_matches"]
            )
            shorts_in_one_match_lower, _ = hyperparam_range(
                instance_parameters_space["shorts_in_one_match"]
            )
            longs_in_one_match_lower, _ = hyperparam_range(
                instance_parameters_space["longs_in_one_match"]
            )
            useful_matches = math.ceil(
                short_fuses_upper / shorts_in_one_match_lower
            ) + math.ceil(long_fuses_upper / longs_in_one_match_lower)
            shorts = []
            longs = []
            matches = []
            for i in range(short_fuses_upper):
                shorts.append(self._get_object(f"short_fuse_{i}", self._Fuse))
            for i in range(long_fuses_upper):
                longs.append(self._get_object(f"long_fuse_{i}", self._Fuse))
            for i in range(useful_matches + extra_matches_upper):
                matches.append(self._get_object(f"match_{i}", self._Match))
            return shorts + longs + matches
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
        elif self.variant == "long_short_fuse":
            for i in range(params["long_fuses"]):
                res.append(self._mended(self._get_object(f"long_fuse_{i}", self._Fuse)))
            for i in range(params["short_fuses"]):
                res.append(
                    self._mended(self._get_object(f"short_fuse_{i}", self._Fuse))
                )
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
        elif self.variant == "long_short_fuse":
            useful_matches = math.ceil(
                params["short_fuses"] / params["shorts_in_one_match"]
            ) + math.ceil(params["long_fuses"] / params["longs_in_one_match"])
            for i in range(useful_matches + params["extra_matches"]):
                res[self._unused(self._get_object(f"match_{i}", self._Match))] = TRUE()

            for i in range(params["long_fuses"]):
                res[
                    self._domain.fluent("fuse-duration")(
                        self._get_object(f"long_fuse_{i}", self._Fuse)
                    )
                ] = Real(Fraction(6, params["longs_in_one_match"]))
            for i in range(params["short_fuses"]):
                res[
                    self._domain.fluent("fuse-duration")(
                        self._get_object(f"short_fuse_{i}", self._Fuse)
                    )
                ] = Real(Fraction(6, params["shorts_in_one_match"]))
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
        if self.variant == "long_short_fuse":
            # this specific variant is always valid
            return True
        return True
