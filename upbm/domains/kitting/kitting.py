import itertools
from typing import Iterable, Optional, Tuple, List, Dict, Union
import unified_planning as up
from unified_planning.shortcuts import (
    Problem,
    UserType,
    Object,
    BoolType,
    Fluent,
    IntType,
    DurativeAction,
    Not,
    GT,
    StartTiming,
    EndTiming,
    Equals,
    ClosedTimeInterval,
    Plus,
)
from unified_planning.model.walkers import AnyChecker
from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Constant,
    Categorical,
    UniformIntegerHyperparameter,
)
from typing import Any

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


def generate_partitions_list(k: int, n: int):
    """
    Generate all n-length tuples by picking one element from each list
    [1], [1,2], ..., [1..min(n,k)].
    Keep only tuples where a number x appears only if (x-1) appears in an earlier position.
    """
    ranges = [range(1, min(i, k) + 1) for i in range(1, n + 1)]

    def valid(t):
        seen = set()
        for x in t:
            if x > 1 and (x - 1) not in seen:
                return False
            seen.add(x)
        return True

    return (t for t in itertools.product(*ranges) if valid(t))


class KittingGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space() -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        mapping["max_kit_size"] = Integer("max_kit_size", (1, MAX_INT), default=5)
        mapping["max_n_kit"] = Integer("max_n_kit", (1, MAX_INT), default=5)
        mapping["isomorphic_instances"] = Categorical(
            "isomorphic_instances", [True, False], default=True
        )
        return ConfigurationSpace(name=mapping)

    def __init__(self, domain_params: Configuration) -> None:
        super().__init__(domain_params)
        domain_params.check_valid_configuration()
        if domain_params.config_space != self.get_domain_parameter_space():
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self._max_kit_size = domain_params["max_kit_size"]
        self._max_n_kit = domain_params["max_n_kit"]
        self._isomorphic_instances = domain_params["isomorphic_instances"]

        self._object_cache: Dict[Tuple[str, UserType], Object] = {}
        self._domain = self._build_domain()

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: Dict[str, Union[Constant, UniformIntegerHyperparameter]] = {}
        mapping["n_components"] = Integer("n_components", (1, MAX_INT), default=10)
        mapping["n_robots"] = Integer("n_robots", (1, MAX_INT), default=5)
        mapping["combination_idx"] = Integer("combination_idx", (0, MAX_INT))

        if self._max_kit_size == 0:
            mapping["kit_size"] = Constant("kit_size", 0)
        else:
            mapping["kit_size"] = Integer("kit_size", (0, self._max_kit_size))

        if self._max_n_kit == 1:
            mapping["n_kit"] = Constant("n_kit", 1)
        else:
            mapping["n_kit"] = Integer("n_kit", (1, self._max_n_kit))
        return ConfigurationSpace(mapping)

    @property
    def name(self) -> str:
        return f"Kitting V{self.domain_params['version']}"

    @property
    def domain(self) -> Problem:
        return self._domain

    @property
    def pddl_expressible(self) -> bool:
        return False

    def _get_object(self, name: str, utype: UserType) -> Object:
        res = self._object_cache.get((name, utype))
        if res is None:
            res = Object(name, utype)
            self._object_cache[(name, utype)] = res
        return res

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ) -> Iterable[Object]:
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        objs = [
            self._domain.object("l0"),
            self._domain.object("k1"),
            self._domain.object("EMPTY"),
        ]
        Location = self._domain.user_type("Location")
        Component = self._domain.user_type("Component")
        Robot = self._domain.user_type("Robot")
        _, components_upper = hyperparam_range(
            instance_parameters_space["n_components"]
        )
        _, robots_upper = hyperparam_range(instance_parameters_space["n_robots"])
        for i in range(1, components_upper + 1):
            objs.append(self._get_object(f"l{i}", Location))
            objs.append(self._get_object(f"c{i}", Component))
        for i in range(robots_upper):
            objs.append(self._get_object(f"r{i}", Robot))
        return objs

    def _build_domain(self) -> Problem:
        domain = Problem("Kitting")

        Robot = UserType("Robot")
        Location = UserType("Location")
        Component = UserType("Component")
        Kit = UserType("Kit")

        l0 = Object("l0", Location)
        k1 = Object("k1", Kit)
        EMPTY = Object("EMPTY", Component)
        domain.add_objects([l0, k1, EMPTY])

        distance = Fluent("distance", IntType(0, 1), a=Location, b=Location)
        is_present = Fluent("is_present", BoolType(), c=Component, l=Location)
        components_on_kit = Fluent(
            "components_on_kit", Component, k=Kit, i=IntType(0, self._max_kit_size - 1)
        )
        robot_busy = Fluent("robot_busy", r=Robot)
        human_busy = Fluent("human_busy")
        ready_to_receive = Fluent(
            "ready_to_receive", BoolType(), i=IntType(0, self._max_n_kit - 1)
        )
        robot_at = Fluent("robot_at", BoolType(), r=Robot, l=Location)
        components_on_robot = Fluent(
            "components_on_robot",
            Component,
            r=Robot,
            i=IntType(0, self._max_kit_size - 1),
        )
        completed = Fluent(
            "completed", BoolType(), i=IntType(0, self._max_n_kit - 1), k=Kit
        )
        robot_cnt = Fluent("robot_cnt", IntType(0, self._max_kit_size), r=Robot)
        kit_cnt = Fluent("kit_cnt", IntType(0, self._max_n_kit))
        battery = Fluent("battery", IntType(0, 10), r=Robot)

        domain.add_fluent(distance, default_initial_value=1)
        domain.add_fluent(is_present, default_initial_value=False)
        domain.add_fluent(components_on_kit, default_initial_value=EMPTY)
        domain.add_fluent(robot_busy, default_initial_value=False)
        domain.add_fluent(human_busy, default_initial_value=False)
        domain.add_fluent(ready_to_receive, default_initial_value=False)
        domain.add_fluent(robot_at, default_initial_value=False)
        domain.add_fluent(components_on_robot, default_initial_value=EMPTY)
        domain.add_fluent(completed, default_initial_value=False)
        domain.add_fluent(robot_cnt, default_initial_value=0)
        domain.add_fluent(kit_cnt, default_initial_value=0)
        domain.add_fluent(battery, default_initial_value=self._max_kit_size + 1)

        move = DurativeAction("move", r=Robot, l_from=Location, l_to=Location)
        r = move.parameter("r")
        l_from = move.parameter("l_from")
        l_to = move.parameter("l_to")
        move.set_fixed_duration(distance(l_from, l_to))
        move.add_condition(StartTiming(), Not(robot_busy(r)))
        move.add_effect(StartTiming(), robot_busy(r), True)
        move.add_effect(EndTiming(), robot_busy(r), False)
        move.add_condition(StartTiming(), Not(Equals(l_from, l_to)))
        move.add_condition(StartTiming(), robot_at(r, l_from))
        move.add_condition(StartTiming(), GT(distance(l_from, l_to), 0))
        move.add_condition(StartTiming(), GT(battery(r), 0))
        move.add_decrease_effect(StartTiming(), battery(r), 1)
        move.add_effect(StartTiming(), robot_at(r, l_from), False)
        move.add_effect(EndTiming(), robot_at(r, l_to), True)
        domain.add_action(move)

        load = DurativeAction(
            "load",
            r=Robot,
            l=Location,
            c=Component,
            k=Kit,
            i=IntType(0, self._max_kit_size - 1),
        )
        r = load.parameter("r")
        l = load.parameter("l")
        c = load.parameter("c")
        k = load.parameter("k")
        i = load.parameter("i")
        load.set_fixed_duration(5)
        load.add_condition(StartTiming(), Not(robot_busy(r)))
        load.add_effect(StartTiming(), robot_busy(r), True)
        load.add_effect(EndTiming(), robot_busy(r), False)
        load.add_condition(StartTiming(), robot_at(r, l))
        load.add_condition(StartTiming(), is_present(c, l))
        load.add_condition(StartTiming(), Equals(robot_cnt(r), i))
        load.add_condition(StartTiming(), Equals(components_on_robot(r, i), EMPTY))
        load.add_condition(StartTiming(), Equals(components_on_kit(k, i), c))
        load.add_effect(EndTiming(), components_on_robot(r, i), c)
        load.add_effect(EndTiming(), robot_cnt(r), Plus(i, 1))
        domain.add_action(load)

        prepare_unload = DurativeAction(
            "prepare_unload", i=IntType(0, self._max_n_kit - 1)
        )
        i = prepare_unload.parameter("i")
        prepare_unload.set_fixed_duration(30)
        prepare_unload.add_condition(StartTiming(), Not(human_busy))
        prepare_unload.add_effect(StartTiming(), human_busy, True)
        prepare_unload.add_effect(EndTiming(), human_busy, False)
        prepare_unload.add_condition(StartTiming(), Equals(kit_cnt, i))
        prepare_unload.add_effect(StartTiming(10), ready_to_receive(i), True)
        prepare_unload.add_effect(StartTiming(20), ready_to_receive(i), False)
        domain.add_action(prepare_unload)

        unload = DurativeAction(
            "unload", r=Robot, k=Kit, i=IntType(0, self._max_n_kit - 1)
        )
        r = unload.parameter("r")
        k = unload.parameter("k")
        i = unload.parameter("i")
        unload.set_fixed_duration(5)
        unload.add_condition(StartTiming(), Not(robot_busy(r)))
        unload.add_effect(StartTiming(), robot_busy(r), True)
        unload.add_effect(EndTiming(), robot_busy(r), False)
        unload.add_condition(StartTiming(), robot_at(r, l0))
        unload.add_condition(StartTiming(), Equals(kit_cnt, i))
        unload.add_condition(
            ClosedTimeInterval(StartTiming(), EndTiming()), ready_to_receive(i)
        )
        for j in range(self._max_kit_size):
            unload.add_condition(
                StartTiming(),
                Equals(components_on_robot(r, j), components_on_kit(k, j)),
            )
            unload.add_effect(EndTiming(), components_on_robot(r, j), EMPTY)
        unload.add_effect(EndTiming(), robot_cnt(r), 0)
        unload.add_effect(EndTiming(), completed(i, k), True)
        unload.add_effect(EndTiming(), kit_cnt, Plus(i, 1))
        unload.add_effect(EndTiming(), battery(r), self._max_kit_size + 1)
        domain.add_action(unload)

        return domain

    def _get_combinations(
        self, n_components: int, length: int
    ) -> list[tuple[up.model.Object, ...]]:
        Component = self._domain.user_type("Component")
        if not self._isomorphic_instances:
            components_dict = {
                i: self._get_object(f"c{i}", Component)
                for i in range(1, n_components + 1)
            }
            not_iso_combinations = []
            for comb in generate_partitions_list(n_components, length):
                not_iso_combinations.append(tuple(components_dict[i] for i in comb))
            return not_iso_combinations
        else:
            components_list = [
                self._get_object(f"c{i}", Component) for i in range(1, n_components + 1)
            ]
            return list(itertools.product(components_list, repeat=length))

    def get_objects(self, params: Configuration) -> Iterable[Object]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

        Location = self._domain.user_type("Location")
        Component = self._domain.user_type("Component")
        Robot = self._domain.user_type("Robot")
        objs = []
        for i in range(1, params["n_components"] + 1):
            objs.append(self._get_object(f"l{i}", Location))
            objs.append(self._get_object(f"c{i}", Component))
        for i in range(params["n_robots"]):
            objs.append(self._get_object(f"r{i}", Robot))
        return objs

    def get_goal(self, params: Configuration) -> List[up.model.FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

        goals = []
        completed = self._domain.fluent("completed")
        k1 = self._domain.object("k1")
        for i in range(params["n_kit"]):
            goals.append(completed(i, k1))
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
                self._domain.object("l0"),
                self._domain.object("k1"),
                self._domain.object("EMPTY"),
            ]
        )

        c = AnyChecker(lambda x: x.is_object_exp() and x.object() not in objects)
        for k, v in self._domain.initial_values.items():
            if c.any(k):
                continue
            initial_values[k] = v

        Location = self._domain.user_type("Location")
        Component = self._domain.user_type("Component")
        Robot = self._domain.user_type("Robot")

        l0 = self._domain.object("l0")
        k1 = self._domain.object("k1")
        EMPTY = self._domain.object("EMPTY")

        is_present = self._domain.fluent("is_present")
        robot_at = self._domain.fluent("robot_at")
        components_on_kit = self._domain.fluent("components_on_kit")

        TRUE = self._domain.environment.expression_manager.TRUE()

        n_components = params["n_components"]
        kit_size = params["kit_size"]
        n_robots = params["n_robots"]

        # set is_present
        for i in range(1, n_components + 1):
            l = self._get_object(f"l{i}", Location)
            c = self._get_object(f"c{i}", Component)
            initial_values[is_present(c, l)] = TRUE

        # set robot_at l0
        for i in range(n_robots):
            r = self._get_object(f"r{i}", Robot)
            initial_values[robot_at(r, l0)] = TRUE

        # calculate the combination based on combination_idx
        combinations = self._get_combinations(n_components, kit_size)
        idx = params["combination_idx"] % len(combinations)
        combination = combinations[idx]

        # set components_on_kit
        for i, c in enumerate(combination):
            initial_values[
                components_on_kit(k1, i)
            ] = self._domain.environment.expression_manager.ObjectExp(c)

        # pad remaining kit capacity with EMPTY
        for i in range(kit_size, self._max_kit_size):
            initial_values[
                components_on_kit(k1, i)
            ] = self._domain.environment.expression_manager.ObjectExp(EMPTY)

        return initial_values

    def check_instance_parameters(self, params: Configuration):
        combinations = self._get_combinations(
            params["n_components"], params["kit_size"]
        )
        if params["combination_idx"] > (len(combinations) - 1):
            return False
        return True
