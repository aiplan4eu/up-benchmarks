import itertools
from typing import Iterable, Optional, Tuple, List, Dict, Union
import unified_planning as up
from unified_planning.shortcuts import (
    Equals,
    StartTiming,
    Object,
    Fluent,
    Problem,
    Not,
    EndTiming,
    UserType,
    BoolType,
    InstantaneousAction,
    DurativeAction,
    IntType,
    GE,
    TRUE,
)
from unified_planning.model.walkers import AnyChecker
from ConfigSpace import ConfigurationSpace, Configuration, Integer, Constant
from typing import Any

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range
import math

MAX_BATTERY = 100


class MaJSPGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space() -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        return ConfigurationSpace(name=mapping)

    def __init__(self, domain_params: Configuration) -> None:
        super().__init__(domain_params)
        domain_params.check_valid_configuration()
        if domain_params.config_space != self.get_domain_parameter_space():
            raise ValueError(f"Invalid domain parameters: {domain_params}")
        self._domain = self._build_domain()

        self._Robot = self._domain.user_type("Robot")
        self._Pallet = self._domain.user_type("Pallet")
        self._Position = self._domain.user_type("Position")
        self._treated = self._domain.fluent("treated")

        self._object_cache: Dict[Tuple[str, UserType], Object] = {}

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        return ConfigurationSpace(
            {
                "n_robots": Integer("n_robots", (1, MAX_INT), default=5),
                "n_pallets": Integer("n_pallets", (1, MAX_INT), default=10),
                "n_positions": Integer("n_positions", (1, MAX_INT), default=20),
                "n_treatments": Integer("n_treatments", (1, MAX_INT), default=5),
            }
        )

    @property
    def name(self) -> str:
        return f"MaJSP V{self.domain_params['version']}"

    @property
    def domain(self) -> Problem:
        return self._domain

    @property
    def pddl_expressible(self) -> bool:
        return False

    def _get_object(self, name: str, type: UserType) -> Object:
        res = self._object_cache.get((name, type))
        if res is None:
            res = Object(name, type)
            self._object_cache[(name, type)] = res
        return res

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ) -> Iterable[Object]:
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        objs = [
            self._domain.object("UNKNOWN"),
            self._domain.object("DEPOT"),
            self._domain.object("NOPALLET"),
        ]
        _, robots_upper = hyperparam_range(instance_parameters_space["n_robots"])
        _, pallets_upper = hyperparam_range(instance_parameters_space["n_pallets"])
        _, positions_upper = hyperparam_range(instance_parameters_space["n_positions"])

        for i in range(robots_upper):
            objs.append(self._get_object(f"r{i}", self._Robot))
        for i in range(pallets_upper):
            objs.append(self._get_object(f"b{i}", self._Pallet))
        for i in range(positions_upper):
            objs.append(self._get_object(f"p{i}", self._Position))
        return objs

    def _build_domain(self) -> Problem:
        domain = Problem("MaJSP")

        # Setting up Types
        Robot = UserType("Robot")
        Pallet = UserType("Pallet")
        Position = UserType("Position")

        UNKNOWN = Object("UNKNOWN", Position)
        DEPOT = Object("DEPOT", Position)
        NOPALLET = Object("NOPALLET", Pallet)
        domain.add_objects([UNKNOWN, DEPOT, NOPALLET])

        # Setting up Fluents
        robot_at = Fluent("robot_at", Position, r=Robot)
        domain.add_fluent(robot_at, default_initial_value=DEPOT)

        robot_has = Fluent("robot_has", Pallet, r=Robot)
        domain.add_fluent(robot_has, default_initial_value=NOPALLET)

        position_has = Fluent("position_has", Pallet, p=Position)
        domain.add_fluent(position_has, default_initial_value=NOPALLET)

        at_depot = Fluent("at_depot", BoolType(), b=Pallet)
        domain.add_fluent(at_depot, default_initial_value=TRUE())

        treated = Fluent("treated", BoolType(), b=Pallet, p=Position)
        domain.add_fluent(treated, default_initial_value=False)

        ready = Fluent("ready", BoolType(), b=Pallet, p=Position)
        domain.add_fluent(ready, default_initial_value=False)

        battery_level = Fluent("battery_level", IntType(0, MAX_BATTERY), r=Robot)
        domain.add_fluent(battery_level, default_initial_value=MAX_BATTERY)

        # Setting up Actions:
        move = DurativeAction("move", r=Robot, to=Position)
        r = move.parameter("r")
        to = move.parameter("to")
        move.set_fixed_duration(1)
        move.add_condition(StartTiming(), Not(Equals(to, UNKNOWN)))
        move.add_condition(StartTiming(), Not(Equals(robot_at(r), to)))
        move.add_condition(StartTiming(), Not(Equals(robot_at(r), UNKNOWN)))
        move.add_condition(StartTiming(), GE(battery_level(r), 1))
        move.add_decrease_effect(StartTiming(), battery_level(r), 1)
        move.add_effect(StartTiming(), robot_at(r), UNKNOWN)
        move.add_effect(EndTiming(), robot_at(r), to)

        unload_at_depot = InstantaneousAction("unload_at_depot", r=Robot)
        r = unload_at_depot.parameter("r")
        unload_at_depot.add_precondition(Not(Equals(robot_has(r), NOPALLET)))
        unload_at_depot.add_precondition(Equals(robot_at(r), DEPOT))
        unload_at_depot.add_effect(position_has(DEPOT), robot_has(r))
        unload_at_depot.add_effect(robot_has(r), NOPALLET)

        load_at_depot = InstantaneousAction("load_at_depot", r=Robot, p=Pallet)
        r = load_at_depot.parameter("r")
        p = load_at_depot.parameter("p")
        load_at_depot.add_precondition(Not(Equals(p, NOPALLET)))
        load_at_depot.add_precondition(Equals(robot_has(r), NOPALLET))
        load_at_depot.add_precondition(at_depot(p))
        load_at_depot.add_precondition(Equals(robot_at(r), DEPOT))
        load_at_depot.add_effect(robot_has(r), p)
        load_at_depot.add_effect(at_depot(p), False)

        make_treat = DurativeAction("make_treatment", r=Robot, b=Pallet, p=Position)
        r = make_treat.parameter("r")
        b = make_treat.parameter("b")
        p = make_treat.parameter("p")
        make_treat.set_fixed_duration(20)
        make_treat.add_condition(StartTiming(), Not(Equals(p, UNKNOWN)))
        make_treat.add_condition(StartTiming(), Not(Equals(b, NOPALLET)))
        make_treat.add_condition(StartTiming(), Not(Equals(p, DEPOT)))
        make_treat.add_condition(StartTiming(), Equals(position_has(p), NOPALLET))
        make_treat.add_condition(StartTiming(), Equals(robot_at(r), p))
        make_treat.add_condition(StartTiming(), Equals(robot_has(r), b))
        make_treat.add_condition(StartTiming(), Not(treated(b, p)))
        make_treat.add_effect(StartTiming(), position_has(p), b)
        make_treat.add_effect(StartTiming(), robot_has(r), NOPALLET)
        make_treat.add_effect(StartTiming(10), ready(b, p), TRUE())
        make_treat.add_condition(EndTiming(), treated(b, p))
        make_treat.add_condition(EndTiming(), Equals(position_has(p), NOPALLET))

        load = DurativeAction("load", r=Robot, b=Pallet, p=Position)
        r = load.parameter("r")
        b = load.parameter("b")
        p = load.parameter("p")
        load.set_fixed_duration(1)
        load.add_condition(StartTiming(), Not(Equals(p, UNKNOWN)))
        load.add_condition(StartTiming(), Not(Equals(b, NOPALLET)))
        load.add_condition(StartTiming(), Equals(position_has(p), b))
        load.add_condition(StartTiming(), Equals(robot_has(r), NOPALLET))
        load.add_condition(StartTiming(), ready(b, p))
        load.add_condition(StartTiming(), Equals(robot_at(r), p))
        load.add_effect(StartTiming(), ready(b, p), False)
        load.add_effect(StartTiming(), position_has(p), NOPALLET)
        load.add_effect(EndTiming(), robot_has(r), b)
        load.add_effect(EndTiming(), treated(b, p), TRUE())

        domain.add_actions([move, load_at_depot, unload_at_depot, make_treat, load])

        return domain

    def get_objects(self, params: Configuration) -> Iterable[Object]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

        objs = []
        for i in range(params["n_robots"]):
            objs.append(self._get_object(f"r{i}", self._Robot))
        for i in range(params["n_pallets"]):
            objs.append(self._get_object(f"b{i}", self._Pallet))
        for i in range(params["n_positions"]):
            objs.append(self._get_object(f"p{i}", self._Position))
        return objs

    def get_goal(self, params: Configuration) -> List[up.model.FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

        goals = []
        n_treat = min(params["n_treatments"], params["n_positions"])
        for p_idx in range(n_treat):
            po = self._get_object(f"p{p_idx}", self._Position)
            for b_idx in range(params["n_pallets"]):
                bo = self._get_object(f"b{b_idx}", self._Pallet)
                goals.append(self._treated(bo, po))
        return goals

    def get_initial_state(
        self, params: Configuration
    ) -> Dict[up.model.FNode, up.model.FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

        initial_values = {}
        objects = list(self.get_objects(params))
        # Add constants that are always present in instances
        objects.extend(
            [
                self._domain.object("UNKNOWN"),
                self._domain.object("DEPOT"),
                self._domain.object("NOPALLET"),
            ]
        )

        c = AnyChecker(lambda x: x.is_object_exp() and x.object() not in objects)
        for k, v in self._domain.initial_values.items():
            if c.any(k):
                continue
            initial_values[k] = v
        return initial_values

    def check_instance_parameters(self, params: Configuration):
        # NOTE FIXME this can be improved
        max_treatments = params["n_robots"] * (MAX_BATTERY - params["n_pallets"])
        n_treat = (
            min(params["n_treatments"], params["n_positions"]) * params["n_pallets"]
        )
        if n_treat > max_treatments:
            return False
        return True
