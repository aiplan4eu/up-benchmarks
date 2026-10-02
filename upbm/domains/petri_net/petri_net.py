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
from typing import Any, List, NamedTuple, Optional, Tuple

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
from unified_planning.shortcuts import TRUE, Equals, LE, Plus

from upbm.generator import Generator
from upbm.utils import is_subspace, hyperparam_range

from .resources.ipc_petri_net_data import IPC_INSTANCES


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

INITIAL_TOKENS = 0

# The place the tokens have to end up in. All three nets call it "g".
GOAL_PLACE = "g"


class GoalStyle(NamedTuple):
    """One of the goal shapes a net is shipped with.

    Every shipped goal asks for a number of tokens in the goal place plus one
    condition on a handful of other places, described here. The number the
    condition asks for is the ``goal_amount`` of each IPC_INSTANCES entry;
    ``places`` are the places it talks about.
    """

    # "each": every place of `places` holds exactly `amount`
    # "sum_eq": the places of `places` hold `amount` tokens in total
    # "sum_ge": they hold at least `amount` tokens in total
    kind: str
    places: Tuple[str, ...]
    empty: Tuple[str, ...] = ()


class Net(NamedTuple):
    """One of the three petri nets of the IPC set.

    ``places`` lists the place names in the order the shipped files declare
    them, and ``facts`` lists the net structure as (predicate, place...)
    tuples. Both are fixed data: the hyper-edges that feed the goal place have
    a fixed arity (``three-to-one a7 b7 c7 g``, ``two-to-one p8 q8 g``), so the
    number of branches is baked into the net and cannot be a parameter.
    """

    places: List[str]
    facts: List[Tuple[str, ...]]
    goal_styles: List[GoalStyle]


def _recycling_net() -> Net:
    """The net of prob06 and prob08: 26 places, three branches of eight.

    A source feeds three identical branches ``a``, ``b`` and ``c``. Each runs
    a chain x1 -> x2 -> x3 -> x4, then x4 splits into x5, x6 and x7, which
    feed each other back into x4 (the "recycling" triangle) or combine into
    x8. The goal place is fed by the tips of all three branches at once.
    """
    branches = ("a", "b", "c")
    places = ["s0"] + [f"{x}{i}" for x in branches for i in range(1, 9)] + [GOAL_PLACE]
    facts: List[Tuple[str, ...]] = [("source", "s0")]
    facts += [("one-to-one", "s0", f"{x}1") for x in branches]
    for x in branches:
        facts += [
            ("one-to-one", f"{x}1", f"{x}2"),
            ("one-to-one", f"{x}2", f"{x}3"),
            ("one-to-one", f"{x}3", f"{x}4"),
            ("one-to-one", f"{x}4", f"{x}5"),
            ("one-to-one", f"{x}4", f"{x}6"),
            ("one-to-one", f"{x}4", f"{x}7"),
            ("one-to-two", f"{x}5", f"{x}6", f"{x}4"),
            ("one-to-two", f"{x}6", f"{x}7", f"{x}4"),
            ("one-to-two", f"{x}7", f"{x}5", f"{x}4"),
            ("three-to-one", f"{x}5", f"{x}6", f"{x}7", f"{x}8"),
        ]
    facts += [
        ("three-to-one", "a7", "b7", "c7", GOAL_PLACE),
        ("three-to-one", "a8", "b8", "c8", GOAL_PLACE),
    ]
    return Net(
        places=places,
        facts=facts,
        goal_styles=[
            # prob06: each branch hub holds the same number of tokens
            GoalStyle("each", ("a4", "b4", "c4")),
            # prob08: the branch tips hold at least that many between them
            GoalStyle("sum_ge", ("a7", "b7", "c7")),
        ],
    )


def _twin_line_net() -> Net:
    """The net of prob07: 18 places, two branches of eight.

    Each branch has a sink at x2 (so tokens can be thrown away) and merges
    pairs of tokens into x5 with a two-to-one edge. The self edge
    ``one-to-two x8 x8 x8`` consumes one token of x8 and returns two, so x8
    doubles. The two branches combine into the goal place.
    """
    branches = ("p", "q")
    places = ["s0"] + [f"{x}{i}" for x in branches for i in range(1, 9)] + [GOAL_PLACE]
    facts: List[Tuple[str, ...]] = [("source", "s0")]
    facts += [("sink", f"{x}2") for x in branches]
    facts += [("one-to-one", "s0", f"{x}1") for x in branches]
    for x in branches:
        facts += [
            ("one-to-one", f"{x}1", f"{x}2"),
            ("one-to-one", f"{x}1", f"{x}3"),
            ("one-to-one", f"{x}1", f"{x}4"),
            ("one-to-two", f"{x}1", f"{x}2", f"{x}4"),
            ("one-to-two", f"{x}1", f"{x}2", f"{x}3"),
            ("two-to-one", f"{x}1", f"{x}4", f"{x}5"),
            ("two-to-one", f"{x}1", f"{x}3", f"{x}5"),
            ("one-to-one", f"{x}5", f"{x}6"),
            ("one-to-one", f"{x}5", f"{x}7"),
            ("one-to-one", f"{x}6", f"{x}8"),
            ("one-to-two", f"{x}8", f"{x}8", f"{x}8"),
        ]
    facts += [("two-to-one", "p8", "q8", GOAL_PLACE)]
    return Net(
        places=places,
        facts=facts,
        goal_styles=[
            # prob07: both merge places hold the same number of tokens and
            # nothing is left half way down either branch
            GoalStyle(
                "each",
                ("p5", "q5"),
                empty=("p2", "p3", "p4", "q2", "q3", "q4"),
            ),
        ],
    )


def _funnel_net() -> Net:
    """The net of prob09 and prob10: 13 places, three branches of three.

    Three short chains feed a common place d1 one token at a time, and feed
    d2 only three tokens at a time (one from each branch). The goal place
    needs one token from each of d1 and d2, so it costs four tokens.
    """
    branches = ("a", "b", "c")
    places = (
        ["s0"]
        + [f"{x}{i}" for x in branches for i in range(1, 4)]
        + ["d1", "d2", GOAL_PLACE]
    )
    facts: List[Tuple[str, ...]] = [("source", "s0")]
    facts += [("one-to-one", "s0", f"{x}1") for x in branches]
    for x in branches:
        facts += [
            ("one-to-one", f"{x}1", f"{x}2"),
            ("one-to-one", f"{x}2", f"{x}3"),
            ("one-to-one", f"{x}3", "d1"),
        ]
    facts += [
        ("three-to-one", "a3", "b3", "c3", "d2"),
        ("two-to-one", "d1", "d2", GOAL_PLACE),
    ]
    return Net(
        places=places,
        facts=facts,
        goal_styles=[
            # prob09: that many tokens left across the three branch tips
            GoalStyle("sum_eq", ("a3", "b3", "c3")),
            # prob10: each branch tip holds exactly that many
            GoalStyle("each", ("a3", "b3", "c3")),
        ],
    )


# The IPC instances are these three nets under five
# goal shapes: prob06 and prob08 share net 0, prob07 is net 1, prob09 and
# prob10 share net 2.
NETS = [_recycling_net(), _twin_line_net(), _funnel_net()]


class PetriNetGenerator(Generator):
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
        if domain_params.config_space != PetriNetGenerator.get_domain_parameter_space():
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Place = self._domain.user_type("place")
        self._value = self._domain.fluent("value")
        self._cost = self._domain.fluent("cost")
        self._predicates = {
            name: self._domain.fluent(name)
            for name in (
                "source",
                "sink",
                "one-to-one",
                "one-to-two",
                "two-to-one",
                "three-to-one",
                "two-to-two",
                "one-to-three",
            )
        }

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant != "ipc":
            raise ValueError(f"invalid variant {self.variant}")
        indices = sorted(IPC_INSTANCES)
        mapping["index"] = Integer(
            "index", (indices[0], indices[-1]), default=indices[0]
        )
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"PetriNet V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            domain = reader.parse_problem(
                str(RESOURCES_PATH / f"petri_net_v{self.version}.pddl")
            )
            domain.add_quality_metric(
                MinimizeExpressionOnFinalState(domain.fluent("cost")())
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

    def _place(self, name: str) -> Object:
        return self._get_object(name, self._Place)

    def _entry(self, params: Configuration) -> dict[str, Any]:
        """The transcribed instance this index asks for."""
        return IPC_INSTANCES[params["index"]]

    def _net(self, params: Configuration) -> Net:
        return NETS[self._entry(params)["net"]]

    def _goal_style(self, params: Configuration) -> GoalStyle:
        return self._net(params).goal_styles[self._entry(params)["goal_style"]]

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        return [self._place(p) for p in self._net(params).places]

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        first, last = hyperparam_range(instance_parameters_space["index"])
        nets = sorted(
            {IPC_INSTANCES[i]["net"] for i in IPC_INSTANCES if first <= i <= last}
        )
        names: List[str] = []
        for i in nets:
            names += [p for p in NETS[i].places if p not in names]
        return [self._place(p) for p in names]

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        entry = self._entry(params)
        style = self._goal_style(params)
        amount = entry["goal_amount"]
        places = [self._value(self._place(p)) for p in style.places]
        goals = [Equals(entry["goal_tokens"], self._value(self._place(GOAL_PLACE)))]
        if style.kind == "each":
            goals += [Equals(p, amount) for p in places]
        elif style.kind == "sum_eq":
            total = Plus(*places)
            goals.append(Equals(total, amount))
        elif style.kind == "sum_ge":
            total = Plus(*places)
            goals.append(LE(amount, total))
        else:
            raise ValueError(f"Unknown goal style {style.kind}")
        goals += [
            Equals(self._value(self._place(p)), INITIAL_TOKENS) for p in style.empty
        ]
        return goals

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        net = self._net(params)
        res: dict[FNode, FNode] = {}
        for fact in net.facts:
            predicate, args = fact[0], fact[1:]
            res[self._predicates[predicate](*[self._place(a) for a in args])] = TRUE()
        for place in net.places:
            res[self._value(self._place(place))] = INITIAL_TOKENS
        res[self._cost()] = 0
        return res

    def check_instance_parameters(self, params: Configuration):
        return True
