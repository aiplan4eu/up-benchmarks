from pathlib import Path
from typing import Any

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

from upbm.generator import Generator
from upbm.utils import MAX_INT


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"


class MatchCellarGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        return ConfigurationSpace(
            name=[
                Constant("version", 1),
                Categorical("variant", ["ipc", "variable_duration"], default="ipc"),
                Integer("max_matches", (0, MAX_INT), default=20),
                Integer("max_fuses", (0, MAX_INT), default=20),
            ]
        )

    def __init__(self, domain_params: Configuration):
        domain_params.check_valid_configuration()
        if (
            domain_params.config_space
            != MatchCellarGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.domain_params = domain_params
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
        return ConfigurationSpace(
            {
                "n_matches": (1, self.domain_params["max_matches"]),
                "n_fuses": (1, self.domain_params["max_fuses"]),
            }
        )

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
        if params.config_space != self.instance_parameter_space:
            raise ValueError(f"Invalid instance parameters: {params}")

        objs = []
        for i in range(params["n_matches"]):
            objs.append(self._get_object(f"match{i}", self._Match))
        for i in range(params["n_fuses"]):
            objs.append(self._get_object(f"fuse{i}", self._Fuse))
        return objs

    @property
    def object_universe(self):
        return [
            self._get_object(f"match{i}", self._Match)
            for i in range(self.domain_params["max_matches"])
        ] + [
            self._get_object(f"fuse{i}", self._Fuse)
            for i in range(self.domain_params["max_fuses"])
        ]

    def get_goal(self, params) -> list[FNode]:
        params.check_valid_configuration()
        if params.config_space != self.instance_parameter_space:
            raise ValueError(f"Invalid instance parameters: {params}")

        res = []
        for i in range(params["n_fuses"]):
            res.append(self._mended(self._get_object(f"fuse{i}", self._Fuse)))
        return res

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        params.check_valid_configuration()
        if params.config_space != self.instance_parameter_space:
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
