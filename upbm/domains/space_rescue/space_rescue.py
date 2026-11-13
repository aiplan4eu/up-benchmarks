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
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Constant,
)
from unified_planning.io import PDDLReader
from unified_planning.model import Problem, Object, FNode
from unified_planning.shortcuts import TRUE

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# Internal number of the charging station. Sites are numbered 0..n_sites-1
# while an instance is drawn; the names in the problem are shuffled later.
STATION = 0


@dataclass
class Layout:
    """One drawn instance, in internal numbers.

    Rovers are numbered by role: the saviour is 0, then come the leeches, the
    stranded rovers and the random rovers. None of this shows in the problem:
    `site_names` and `rover_names` give every site and rover a number drawn
    at random.
    """

    capacity: int
    neighbours: List[List[int]]
    site_packs: List[int]
    rover_site: List[int]
    rover_goal: List[int]
    site_names: List[str]
    rover_names: List[str]


def amount_values(capacity: int) -> List[int]:
    """The values of the amount objects: every power of two up to `capacity`.

    Any load from 1 to `capacity` is a sum of distinct ones (its binary
    digits), so it takes one pick_up or drop action per binary digit rather
    than one per pack.
    """
    values = [1]
    while values[-1] * 2 <= capacity:
        values.append(values[-1] * 2)
    return values


class SpaceRescueGenerator(Generator):
    """Space Rescue: rovers out of energy on a graph of sites.

    Every drive drains one battery pack. Packs lie on sites and are picked up
    or dropped, and a charging station fills a rover to its capacity and never
    runs out. A saviour rover can surely reach the station with the packs on
    its way; from there it brings packs to the others. The goal is to get
    every rover to its goal site.

    The domain is derived from the IPC 2026 expedition domain: a graph instead
    of chains, an unlimited charging station, packs moved in amounts, and
    several rovers that may need each other.

    Instances are solvable by construction, see `_draw`.
    """

    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        return ConfigurationSpace(name=mapping)

    def __init__(self, domain_params: Configuration):
        domain_params.check_valid_configuration()
        if (
            domain_params.config_space
            != SpaceRescueGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Rover = self._domain.user_type("rover")
        self._Site = self._domain.user_type("site")
        self._Amount = self._domain.user_type("amount")
        self._at = self._domain.fluent("at")
        self._connected = self._domain.fluent("connected")
        self._charging_station = self._domain.fluent("charging_station")
        self._rover_packs = self._domain.fluent("rover_packs")
        self._rover_capacity = self._domain.fluent("rover_capacity")
        self._site_packs = self._domain.fluent("site_packs")
        self._value = self._domain.fluent("value")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        # number of sites (graph nodes) in the map
        mapping["n_sites"] = Integer("n_sites", (4, MAX_INT), default=12)
        # Every rover has this capacity, C below. From the charging station a
        # rover of capacity 3 or more can leave packs anywhere: a round trip
        # over one edge leaves C - 2 >= 1 at the far end. Every instance being
        # solvable rests on this.
        mapping["rover_capacity"] = Integer("rover_capacity", (3, MAX_INT), default=4)
        # Leeches start with the saviour and share its packs: if they drive
        # off with some, the saviour may no longer reach the station.
        mapping["n_leech"] = Integer("n_leech", (0, MAX_INT), default=0)
        # Stranded rovers start on a site with no packs and cannot move until
        # another rover brings them some.
        mapping["n_stranded"] = Integer("n_stranded", (0, MAX_INT), default=2)
        # Random rovers start anywhere. One that can reach the station on its
        # own is a second saviour and makes the traps above harmless.
        mapping["n_randoms"] = Integer("n_randoms", (0, MAX_INT), default=0)
        # Packs on the saviour's start beyond what it needs to reach the
        # station, that is how many wasted packs the instance forgives.
        mapping["slack"] = Integer("slack", (0, MAX_INT), default=0)
        # 1 sends every rover to the same site; one per rover gives each
        # rover a goal site of its own.
        mapping["n_goal_sites"] = Integer("n_goal_sites", (1, MAX_INT), default=1)
        # Percentage of the sites that get a scattered stash (rounded down).
        # Fewer get one when not enough sites are far enough from the saviour,
        # see `_scatter_stashes`.
        mapping["stash_density"] = Integer("stash_density", (0, 100), default=25)
        # Packs in the scattered stashes, all together, in units of C.
        mapping["stash_total"] = Integer("stash_total", (0, MAX_INT), default=2)
        mapping["seed"] = Integer("seed", (0, MAX_INT), default=42)
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"SpaceRescue V{self.version}"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            return reader.parse_problem(
                str(RESOURCES_PATH / f"space_rescue_v{self.version}.pddl")
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

    @staticmethod
    def _n_rovers(params) -> int:
        return 1 + params["n_leech"] + params["n_stranded"] + params["n_randoms"]

    def _rover(self, name: str) -> Object:
        return self._get_object(name, self._Rover)

    def _site(self, name: str) -> Object:
        return self._get_object(name, self._Site)

    def _amount(self, value: int) -> Object:
        return self._get_object(f"q{value}", self._Amount)

    # --- drawing an instance -------------------------------------------------

    def _layout(self, params) -> Layout:
        return self._draw(params, random.Random(params["seed"]))

    def _draw(self, params, rng: random.Random) -> Layout:
        """Draw the whole instance from the seed.

        1. A random connected graph (`_draw_graph`) where every site is
           between 0 and 2C steps from the charging station.
        2. The goal sites, between C and 2C steps from the station: far
           enough to need some caching, near enough not to blow up. Every
           further C steps multiply the packs a trip needs by about e^2.
        3. The saviour's start S, at least 2 steps from the station.
        4. The packs for the saviour's way: along a shortest path from S to
           the station, stashes C steps apart (the last gap shorter), each
           holding exactly the distance to the next one (plus `slack` at S). The saviour
           starts with no packs, picks each stash up, and reaches the station
           with none left.
        5. The other rovers: leeches at S, stranded rovers on sites with no
           packs, random rovers anywhere. Every rover starts with no packs,
           and none starts on its own goal site, where its goal would be
           reached for free (a stranded rover would need no rescue).
        6. The scattered stashes (`_scatter_stashes`).

        Why every instance is solvable: the saviour reaches the station by
        step 4, and from the station a rover of capacity C >= 3 can leave any
        number of packs on any site. So every rover can be given what it needs
        to reach the station and then its goal. Nothing drawn after step 4
        takes packs away, so nothing can break this.
        """
        capacity = params["rover_capacity"]
        n_sites = params["n_sites"]

        # 1.
        parent, depth, neighbours = self._draw_graph(
            rng, n_sites, capacity, params["n_goal_sites"]
        )

        # 2. `_draw_graph` makes sure there are enough sites this far. The
        # first goal sites go to distinct rovers, so each goal site is used.
        band = [s for s in range(n_sites) if depth[s] >= capacity]
        goal_sites = rng.sample(band, params["n_goal_sites"])
        n_rovers = self._n_rovers(params)
        rover_goal = [STATION] * n_rovers
        order = list(range(n_rovers))
        rng.shuffle(order)
        for k, rover in enumerate(order):
            if k < len(goal_sites):
                rover_goal[rover] = goal_sites[k]
            else:
                rover_goal[rover] = rng.choice(goal_sites)

        # 3. Not on a goal site, so that the saviour and the leeches do not
        # start on theirs. There is always a choice: the spine's site 2 steps
        # from the station is closer than any goal site (C >= 3).
        start = rng.choice(
            [s for s in range(n_sites) if depth[s] >= 2 and s not in goal_sites]
        )
        # On a tree rooted at the station, following the parents is a
        # shortest path, and `_draw_graph` keeps it one on the full graph.
        path = [start]
        while path[-1] != STATION:
            path.append(parent[path[-1]])

        # 4. The stashes are exactly C apart, the last gap shorter.
        site_packs = [0] * n_sites
        distance = depth[start]
        for position in range(0, distance, capacity):
            site_packs[path[position]] = min(capacity, distance - position)
        site_packs[start] += params["slack"]

        # 5. Rovers in role order: the saviour, leeches, stranded, random.
        # A stranded rover always has an empty site other than its goal: the
        # sites 1 and 2 steps along the saviour's path from S are empty when
        # S is more than C steps from the station, and otherwise the sites
        # on that path are all closer than C, so none is a goal site. Stranded
        # rovers may share a site.
        empty = [s for s in range(n_sites) if s != STATION and site_packs[s] == 0]
        rover_site = [start] * (1 + params["n_leech"])
        for rover in range(len(rover_site), len(rover_site) + params["n_stranded"]):
            rover_site.append(rng.choice([s for s in empty if s != rover_goal[rover]]))
        stranded = rover_site[1 + params["n_leech"] :]
        for rover in range(len(rover_site), n_rovers):
            rover_site.append(
                rng.choice([s for s in range(n_sites) if s != rover_goal[rover]])
            )

        # 6.
        self._scatter_stashes(
            rng, params, neighbours, site_packs, start, distance, set(stranded)
        )

        site_numbers = list(range(1, n_sites + 1))
        rng.shuffle(site_numbers)
        rover_numbers = list(range(1, n_rovers + 1))
        rng.shuffle(rover_numbers)
        return Layout(
            capacity=capacity,
            neighbours=neighbours,
            site_packs=site_packs,
            rover_site=rover_site,
            rover_goal=rover_goal,
            site_names=[f"s{k}" for k in site_numbers],
            rover_names=[f"r{k}" for k in rover_numbers],
        )

    @staticmethod
    def _draw_graph(
        rng: random.Random, n_sites: int, capacity: int, n_goal_sites: int
    ) -> Tuple[List[int], List[int], List[List[int]]]:
        """A random connected graph, as (parent, depth, neighbours).

        It starts as a random tree rooted at the charging station, where
        `depth` is the distance from the station and `parent` the next site
        towards it:

        - a spine of C sites leaves the station, so some site is C steps away
          and the goals have somewhere to go;
        - every other site hangs from a random site already placed, kept at
          most 2C steps from the station, so no rescue or goal is far enough
          to blow up the plan;
        - the first n_goal_sites - 1 of those hang at C steps or more, so
          there are enough goal sites.

        Then extra edges make loops, between sites at the same distance from
        the station or one step apart. Such an edge cannot shorten any
        distance to the station, so the tree's depths and parents stay right
        on the full graph. The seed picks how many, from none (a tree) to one
        per two sites (on average three neighbours per site, like a road
        map).
        """
        parent = [STATION]
        depth = [0]
        for site in range(1, capacity + 1):
            parent.append(site - 1)
            depth.append(site)
        for site in range(capacity + 1, n_sites):
            lowest = capacity - 1 if site - capacity - 1 < n_goal_sites - 1 else 0
            hook = rng.choice(
                [s for s in range(site) if lowest <= depth[s] < 2 * capacity]
            )
            parent.append(hook)
            depth.append(depth[hook] + 1)

        edges = {(min(s, parent[s]), max(s, parent[s])) for s in range(1, n_sites)}
        candidates = [
            (a, b)
            for a in range(n_sites)
            for b in range(a + 1, n_sites)
            if abs(depth[a] - depth[b]) <= 1 and (a, b) not in edges
        ]
        n_extra = min(rng.randint(0, n_sites // 2), len(candidates))
        edges.update(rng.sample(candidates, n_extra))

        neighbours: List[List[int]] = [[] for _ in range(n_sites)]
        for a, b in sorted(edges):
            neighbours[a].append(b)
            neighbours[b].append(a)
        return parent, depth, neighbours

    @staticmethod
    def _scatter_stashes(
        rng: random.Random,
        params,
        neighbours: List[List[int]],
        site_packs: List[int],
        start: int,
        distance: int,
        stranded_sites: Set[int],
    ) -> None:
        """Add the scattered stashes to `site_packs`.

        A scattered stash must not give the rovers at S more packs than the
        instance means them to have, or the leech trap stops being one. So it
        only goes where they cannot get before some rover reaches the
        station. Until then, all the packs they can use are the
        distance + slack on the saviour's way, and every drive spends one, so
        none of them gets further from S than distance + slack steps without
        passing the station. A stash is never put on a stranded rover's site
        either: it would no longer be stranded.

        Random rovers ignore this rule: one sitting on a stash may carry it
        anywhere, as a second saviour.

        `stash_total` * C packs are cut at random points into one piece per
        stash, each piece at least 1.
        """
        n_sites = len(site_packs)
        reach = {start: 0}
        queue = deque([start])
        while queue:
            site = queue.popleft()
            for other in neighbours[site]:
                if other != STATION and other not in reach:
                    reach[other] = reach[site] + 1
                    queue.append(other)
        budget = distance + params["slack"]
        allowed = [
            s
            for s in range(n_sites)
            if s != STATION
            and site_packs[s] == 0
            and s not in stranded_sites
            and reach.get(s, budget + 1) > budget
        ]
        total = params["stash_total"] * params["rover_capacity"]
        n_stashes = min(len(allowed), n_sites * params["stash_density"] // 100, total)
        if n_stashes == 0:
            return
        sites = rng.sample(allowed, n_stashes)
        cuts = sorted(rng.sample(range(1, total), n_stashes - 1))
        for site, start_cut, end_cut in zip(sites, [0] + cuts, cuts + [total]):
            site_packs[site] = end_cut - start_cut

    # --- the problem ---------------------------------------------------------

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        layout = self._layout(params)
        # Sorted by number: the numbers are random, so the order says nothing.
        rovers = sorted(layout.rover_names, key=lambda name: int(name[1:]))
        sites = sorted(layout.site_names, key=lambda name: int(name[1:]))
        objs: List[Object] = [self._rover(name) for name in rovers]
        objs += [self._site(name) for name in sites]
        objs += [self._amount(v) for v in amount_values(params["rover_capacity"])]
        return objs

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        space = instance_parameters_space
        n_rovers = 1 + sum(
            hyperparam_range(space[name])[1]
            for name in ("n_leech", "n_stranded", "n_randoms")
        )
        _, n_sites = hyperparam_range(space["n_sites"])
        _, capacity = hyperparam_range(space["rover_capacity"])
        objs: List[Object] = [self._rover(f"r{k}") for k in range(1, n_rovers + 1)]
        objs += [self._site(f"s{k}") for k in range(1, n_sites + 1)]
        objs += [self._amount(v) for v in amount_values(capacity)]
        return objs

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        layout = self._layout(params)
        goals = [
            (layout.rover_names[r], layout.site_names[layout.rover_goal[r]])
            for r in range(len(layout.rover_names))
        ]
        goals.sort(key=lambda goal: int(goal[0][1:]))
        return [self._at(self._rover(r), self._site(s)) for r, s in goals]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        rng = random.Random(params["seed"])
        layout = self._draw(params, rng)
        site = [self._site(name) for name in layout.site_names]
        rover = [self._rover(name) for name in layout.rover_names]

        facts: List[Tuple[FNode, Any]] = [
            (self._charging_station(site[STATION]), TRUE())
        ]
        for a, others in enumerate(layout.neighbours):
            facts += [(self._connected(site[a], site[b]), TRUE()) for b in others]
        for s, packs in enumerate(layout.site_packs):
            facts.append((self._site_packs(site[s]), packs))
        for r in range(len(rover)):
            facts.append((self._at(rover[r], site[layout.rover_site[r]]), TRUE()))
            facts.append((self._rover_packs(rover[r]), 0))
            facts.append((self._rover_capacity(rover[r]), layout.capacity))
        for v in amount_values(layout.capacity):
            facts.append((self._value(self._amount(v)), v))

        # Written in a random order, so that nothing in the problem file
        # (where the station's edges are, which rovers come first) gives away
        # who is who. This continues the random stream of the draw.
        rng.shuffle(facts)
        return dict(facts)

    def check_instance_parameters(self, params: Configuration):
        # The spine of C sites plus one more site per extra goal site, see
        # `_draw_graph`.
        if params["n_sites"] < params["rover_capacity"] + params["n_goal_sites"]:
            return False
        # Each goal site is some rover's goal.
        if params["n_goal_sites"] > self._n_rovers(params):
            return False
        return True
