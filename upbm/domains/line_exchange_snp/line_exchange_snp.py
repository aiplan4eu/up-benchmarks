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

# How many robots the "bounded_5" variant can describe. That variant states one
# load parameter per robot (see instance_parameter_space), and ConfigSpace has
# no variable-length parameter, so the number of those slots is what sets this
# ceiling - and the "_5" in the variant's own name spells the same number, so
# the two have to be changed together. Neither of the other two variants has
# this limit: "unbounded_random" draws the loads and "ipc" tabulates them.
#
# It happens to equal MAX_IPC_ROBOTS, the largest shipped line, but only by
# coincidence: this is a count of declared parameters, that one is a property of
# the dataset. test_the_bounded_variant_covers_the_shipped_sizes pins the
# coincidence so that lowering this number cannot quietly make "bounded_5"
# unable to express what "ipc" ships.
MAX_ROBOTS = 5

# How much the "unbounded_random" variant shuffles the loads before handing
# them out: one transfer per robot. That number is calibrated against the
# shipped set, whose spread between the largest and smallest load, as a
# fraction of the mean, averages 0.46 / 0.65 / 1.45 at imbalance 25 / 50 / 90.
# One transfer per robot gives 0.44 / 0.91 / 1.41; two or more overshoot
# throughout.
TRANSFERS_PER_ROBOT = 1


class LineExchangeSnpGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        # The three variants differ in where the size and the loads come from.
        #
        #   "ipc"               both are table data: one parameter, the index of
        #                       a shipped instance. This is the only variant
        #                       that reproduces the IPC set, and the only thing
        #                       it can do.
        #   "bounded_5"         the caller states the loads, one parameter per
        #                       robot, so the line is capped at MAX_ROBOTS. Use
        #                       it to ask for a load vector of your own, which
        #                       is the one thing "ipc" cannot do.
        #   "unbounded_random"  the loads are drawn from a mean and an imbalance
        #                       - which is what the shipped file names say the
        #                       original parameters actually were - so it needs
        #                       no slot per robot and the line is unbounded.
        #
        # There is no fourth combination: explicit loads always cost a slot per
        # robot, because ConfigSpace has no variable-length parameter, so an
        # unbounded line can only ever have its loads drawn or tabulated.
        mapping["variant"] = Categorical(
            "variant",
            ["ipc", "bounded_5", "unbounded_random"],
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
        if self.variant == "ipc":
            # Everything else about a shipped instance - how many robots, how
            # long their segments are, what they start holding - is table data,
            # so the index is the whole parameter space.
            indices = sorted(IPC_INSTANCES)
            mapping["index"] = Integer(
                "index", (indices[0], indices[-1]), default=indices[0]
            )
            return ConfigurationSpace(name=mapping)
        if self.variant not in ("bounded_5", "unbounded_random"):
            raise ValueError(f"invalid variant {self.variant}")

        # --- shared by the two parameterised variants ---
        #
        # The IPC set uses 3, 4 or 5 robots; two is the smallest line that can
        # exchange anything at all. Only "bounded_5" is capped, because only it
        # needs a load slot per robot.
        mapping["n_robots"] = Integer(
            "n_robots",
            (2, MAX_ROBOTS if self.variant == "bounded_5" else MAX_INT),
            default=3,
        )
        # The (D) function: each robot owns the segment [D*i, D*(i+1)]. The IPC
        # set uses 10, 50 and 100.
        mapping["segment_length"] = Integer("segment_length", (1, MAX_INT), default=50)

        if self.variant == "bounded_5":
            # One load per robot. The shipped instances draw these at random
            # and record no seed, so the only way to reproduce them exactly is
            # to state each load; the mean and imbalance in the file names
            # cannot be inverted. Slots from n_robots upwards are ignored.
            # The defaults reproduce the instance named 3_5_50_50.
            for slot, default in enumerate([3, 6, 6, 0, 0]):
                mapping[f"q_{slot}"] = Integer(
                    f"q_{slot}", (0, MAX_INT), default=default
                )
        else:
            # The two knobs the shipped file names record, as knobs rather
            # than as their outcome. Every shipped instance holds
            # sum(q) = n_robots * mean_q, so asking for the mean instead of
            # the totals makes the even split the generator's job rather than
            # the caller's.
            mapping["mean_load"] = Integer("mean_load", (0, MAX_INT), default=10)
            # How far from that mean the loads are pushed, as a percentage of
            # it: a single transfer moves up to mean_load * imbalance / 100
            # units. The IPC set uses 25, 50 and 90. Zero hands every robot
            # the mean, which is already the goal; above 100 just means a
            # robot may hand over everything it has.
            mapping["imbalance"] = Integer("imbalance", (0, MAX_INT), default=50)
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
        return self._scrambled_loads(params)

    @staticmethod
    def _scrambled_loads(params) -> List[int]:
        """Loads drawn by undoing a few exchanges from the balanced state.

        Everyone starts on the mean, which is exactly the goal, and then the
        loads are scrambled by moving units between neighbours - the same
        thing the `exch` actions do, just in reverse. So the scramble is a
        witness plan and the instance is solvable by construction: the total
        is conserved, so it still divides evenly, and no robot can hand over
        more than it holds, so no load goes negative.
        """
        n_robots = params["n_robots"]
        loads = [params["mean_load"]] * n_robots
        # the most one transfer may move
        step = params["mean_load"] * params["imbalance"] // 100
        rng = random.Random(params["seed"])
        for _ in range(n_robots * TRANSFERS_PER_ROBOT):
            # pick a neighbouring pair, then which way round the unit goes
            left = rng.randrange(n_robots - 1)
            donor, receiver = (left, left + 1) if rng.randrange(2) else (left + 1, left)
            amount = rng.randint(0, min(loads[donor], step))
            loads[donor] -= amount
            loads[receiver] += amount
        return loads

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
            # The reachable rows decide the universe, so a narrowed `index`
            # range gives a smaller one. All twenty rows together need
            # MAX_IPC_ROBOTS robots.
            first, last = hyperparam_range(instance_parameters_space["index"])
            robots_upper = max(
                entry["n_robots"]
                for index, entry in IPC_INSTANCES.items()
                if first <= index <= last
            )
            return [self._robot(i) for i in range(robots_upper)]
        # The universe is as big as the upper bound on n_robots, so for the
        # "unbounded_random" variant, whose bound is MAX_INT, pass a space
        # narrowed with get_reduced_instance_space rather than the default one.
        _, robots_upper = hyperparam_range(instance_parameters_space["n_robots"])
        return [self._robot(i) for i in range(robots_upper)]

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        n_robots = self.n_robots(params)
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
        n_robots = self.n_robots(params)
        res: dict[FNode, FNode] = {self._d(): self.segment_length(params)}
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
        # The "unbounded_random" variant scrambles a balanced start, so it
        # always does, and every "ipc" row is a shipped instance that divides
        # evenly by construction. Only "bounded_5", where the caller states the
        # loads, can get this wrong - which is why the check stays with it
        # rather than moving to a shared place.
        if self.variant != "bounded_5":
            return True
        return sum(self._loads(params)) % params["n_robots"] == 0
