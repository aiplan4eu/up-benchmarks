from pathlib import Path
from typing import Any, Optional, List

from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Categorical,
    Constant,
)
from unified_planning.io import PDDLReader  # type: ignore[import-untyped]
from unified_planning.model import Problem, Object, FNode  # type: ignore[import-untyped]
from unified_planning.shortcuts import TRUE, UserType  # type: ignore[import-untyped]
from typing import Any

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"


class MatchCellarGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        mapping["variant"] = Categorical(
            "variant", ["ipc", "variable_duration"], default="ipc"
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
        mapping["n_matches"] = Integer("n_matches", (0, MAX_INT), default=10)
        mapping["n_fuses"] = Integer("n_fuses", (0, MAX_INT), default=16)
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"MatchCellar V{self.version}"

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
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

        if self.variant == "ipc" and params["n_fuses"] > 2 * params["n_matches"]:
            raise ValueError(f"Requested instance is unsolvable")

        objs = []
        for i in range(params["n_matches"]):
            objs.append(self._get_object(f"match{i}", self._Match))
        for i in range(params["n_fuses"]):
            objs.append(self._get_object(f"fuse{i}", self._Fuse))
        return objs

    @property
    def object_universe(self, instance_parameters_space: ConfigurationSpace):

        return [
            self._get_object(f"match{i}", self._Match)
            for i in range(instance_parameters_space["n_matches"].upper)
        ] + [
            self._get_object(f"fuse{i}", self._Fuse)
            for i in range(instance_parameters_space["n_fuses"].upper)
        ]

    def get_goal(self, params) -> list[FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

        res = []
        for i in range(params["n_fuses"]):
            res.append(self._mended(self._get_object(f"fuse{i}", self._Fuse)))
        return res

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

        res = {self._handfree(): TRUE()}
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
        return True
