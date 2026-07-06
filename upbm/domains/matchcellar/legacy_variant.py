from fractions import Fraction

# from examples import ProblemGenerator
from typing import Iterator, Optional, Tuple, List, Dict, Union
import unified_planning as up
from unified_planning.shortcuts import (
    Problem,
    UserType,
    Fluent,
    BoolType,
    DurativeAction,
    RealType,
    StartTiming,
    EndTiming,
    Not,
    Object,
    ClosedTimeInterval,
    Real,
    FluentExp,
)
from unified_planning.model.walkers import AnyChecker
import math


def get_legacy_domain():
    domain = Problem("MatchCellar")

    Match = UserType("match")
    Fuse = UserType("fuse")

    handfree = Fluent("handfree")
    light = Fluent("light")
    match_used = Fluent("match_used", BoolType(), match=Match)
    fuse_mended = Fluent("fuse_mended", BoolType(), fuse=Fuse)
    mend_fuse_duration = Fluent("mend_fuse_duration", RealType(0, 6))
    domain.add_fluent(handfree, default_initial_value=True)
    domain.add_fluent(light, default_initial_value=False)
    domain.add_fluent(match_used, default_initial_value=False)
    domain.add_fluent(fuse_mended, default_initial_value=False)
    domain.add_fluent(mend_fuse_duration, default_initial_value=6)

    light_match = DurativeAction("light_match", m=Match)
    m = light_match.parameter("m")
    light_match.set_fixed_duration(7)
    light_match.add_condition(StartTiming(), Not(match_used(m)))
    light_match.add_effect(StartTiming(), match_used(m), True)
    light_match.add_effect(StartTiming(), light, True)
    light_match.add_effect(EndTiming(), light, False)
    domain.add_action(light_match)

    mend_fuse = DurativeAction("mend_fuse", f=Fuse)
    f = mend_fuse.parameter("f")
    mend_fuse.set_fixed_duration(mend_fuse_duration)
    mend_fuse.add_condition(StartTiming(), handfree)
    mend_fuse.add_condition(ClosedTimeInterval(StartTiming(), EndTiming()), light)
    mend_fuse.add_effect(StartTiming(), handfree, False)
    mend_fuse.add_effect(EndTiming(), fuse_mended(f), True)
    mend_fuse.add_effect(EndTiming(), handfree, True)
    domain.add_action(mend_fuse)

    # for i in range(1, self._total + 1):
    #     f = Object(f"f{i}", Fuse)
    #     domain.add_object(f)
    #     if i <= self._total_light_match:
    #         m = Object(f"m{i}", Match)
    #         domain.add_object(m)

    return domain


# class MatchcellarGenerator():
#     def __init__(
#         self,
#         to_fix: Union[int, Tuple[int, int]],
#         total: int,
#         inside: Union[int, Tuple[int, int]] = 1,
#         extra_matches: int = 0,
#         isomorphic_instances: bool = True,
#     ) -> None:
#         super().__init__()
#         self._min_to_fix = to_fix[0] if isinstance(to_fix, tuple) else 1
#         self._max_to_fix = to_fix[1] if isinstance(to_fix, tuple) else to_fix
#         self._min_inside = inside[0] if isinstance(inside, tuple) else 1
#         self._max_inside = inside[1] if isinstance(inside, tuple) else inside
#         self._total = total
#         self._total_light_match = (total - self._min_to_fix) + math.ceil(
#             self._min_to_fix / self._min_inside
#         )  # need less matches if more inside
#         self._extra_matches = extra_matches
#         if self._total_light_match <= self._total - self._extra_matches:
#             self._total_light_match += (
#                 self._extra_matches
#             )  # extra matches to simplify the problem
#         self._isomorphic_instances = isomorphic_instances
#         self._domain = self._build_domain()

#     def _build_domain(self):
#         domain = Problem("MatchCellar")

#         Match = UserType("Match")
#         Fuse = UserType("Fuse")

#         handfree = Fluent("handfree")
#         light = Fluent("light")
#         match_used = Fluent("match_used", BoolType(), match=Match)
#         fuse_mended = Fluent("fuse_mended", BoolType(), fuse=Fuse)
#         mend_fuse_duration = Fluent("mend_fuse_duration", RealType(0, 6))
#         domain.add_fluent(handfree, default_initial_value=True)
#         domain.add_fluent(light, default_initial_value=False)
#         domain.add_fluent(match_used, default_initial_value=False)
#         domain.add_fluent(fuse_mended, default_initial_value=False)
#         domain.add_fluent(mend_fuse_duration, default_initial_value=6)

#         light_match = DurativeAction("light_match", m=Match)
#         m = light_match.parameter("m")
#         light_match.set_fixed_duration(7)
#         light_match.add_condition(StartTiming(), Not(match_used(m)))
#         light_match.add_effect(StartTiming(), match_used(m), True)
#         light_match.add_effect(StartTiming(), light, True)
#         light_match.add_effect(EndTiming(), light, False)
#         domain.add_action(light_match)

#         mend_fuse = DurativeAction("mend_fuse", f=Fuse)
#         f = mend_fuse.parameter("f")
#         mend_fuse.set_fixed_duration(mend_fuse_duration)
#         mend_fuse.add_condition(StartTiming(), handfree)
#         mend_fuse.add_condition(ClosedTimeInterval(StartTiming(), EndTiming()), light)
#         mend_fuse.add_effect(StartTiming(), handfree, False)
#         mend_fuse.add_effect(EndTiming(), fuse_mended(f), True)
#         mend_fuse.add_effect(EndTiming(), handfree, True)
#         domain.add_action(mend_fuse)

#         for i in range(1, self._total + 1):
#             f = Object(f"f{i}", Fuse)
#             domain.add_object(f)
#             if i <= self._total_light_match:
#                 m = Object(f"m{i}", Match)
#                 domain.add_object(m)

#         return domain

#     def domain(self) -> up.model.Problem:
#         return self._domain

#     def size(self) -> Optional[int]:
#         res = 0
#         # for s in range(5, self._to_fix+1, 5):
#         for n in range(self._min_inside, self._max_inside + 1):
#             for s in range(self._min_to_fix, self._max_to_fix + 1):
#                 if self._isomorphic_instances:
#                     combinations = list(range(1, self._total - s + 2))
#                 else:
#                     combinations = [1]
#                 for j in combinations:
#                     res += 1
#         return res

#     def _get_problem_items(
#         self, n, s, j
#     ) -> Tuple[
#         Dict["up.model.FNode", "up.model.FNode"],
#         List["up.model.Object"],
#         List["up.model.FNode"],
#     ]:
#         goals = []
#         objects = []
#         initial_values = {}
#         for i in range(j, j + s):
#             f = self._domain.object(f"f{i}")
#             objects.append(f)
#             goals.append(self._domain.fluent("fuse_mended")(f))
#         n_matches = s
#         if n > 1 and s > math.ceil(s / n) + self._extra_matches:
#             n_matches = math.ceil(s / n)
#             n_matches += self._extra_matches  # extra matches to simplify the problem
#         for i in range(j, j + n_matches):
#             objects.append(self._domain.object(f"m{i}"))
#         c = AnyChecker(lambda x: x.is_object_exp() and x.object() not in objects)
#         for k, v in self._domain.initial_values.items():
#             if c.any(k):
#                 continue
#             initial_values[k] = v
#         mend_fuse_duration = self._domain.fluent("mend_fuse_duration")
#         initial_values[FluentExp(mend_fuse_duration)] = Real(Fraction(6, n))
#         return initial_values, objects, goals

#     def get_problems(
#         self,
#     ) -> Iterator[
#         Tuple[
#             Dict["up.model.FNode", "up.model.FNode"],
#             List["up.model.Object"],
#             List["up.model.FNode"],
#         ]
#     ]:
#         # for s in range(5, self._to_fix+1, 5):
#         for n in range(self._min_inside, self._max_inside + 1):
#             for s in range(self._min_to_fix, self._max_to_fix + 1):
#                 if self._isomorphic_instances:
#                     combinations = list(range(1, self._total - s + 2))
#                 else:
#                     combinations = [1]
#                 for j in combinations:
#                     yield self._get_problem_items(n, s, j)

#     def get_problem(self, n, s, j) -> Problem:
#         problem = self.domain().clone()
#         problem.all_objects.clear()
#         init, objects, goals = self._get_problem_items(n, s, j)
#         for o in objects:
#             problem.add_object(o)
#         for k, v in init.items():
#             problem.set_initial_value(k, v)
#         for g in goals:
#             problem.add_goal(g)
#         return problem

#     def dump_problem_params(self, filename: str):
#         with open(filename, "w") as f:
#             for n in range(self._min_inside, self._max_inside + 1):
#                 for s in range(self._min_to_fix, self._max_to_fix + 1):
#                     if self._isomorphic_instances:
#                         combinations = list(range(1, self._total - s + 2))
#                     else:
#                         combinations = [1]
#                     for j in combinations:
#                         f.write(f"{n},{s},{j}\n")
