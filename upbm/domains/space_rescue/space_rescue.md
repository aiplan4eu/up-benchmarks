# Space Rescue

On a remote planet, a colony of rovers has run out of energy, and most of them
are stuck where they stopped. A saviour rover is dropped close enough to the
charging station that it can surely get there, with the help of the battery
packs lying on its way. From the station it brings packs to the others. The
goal is to get every rover to the main station (when they all share one goal)
or to its own work station (when each has its own).

## Domain

Changes from the IPC expedition domain:

- **A graph.** `(connected ?a ?b)`, listed in both directions, and a single
  `drive` action replace `is_next` with `move_forwards` / `move_backwards`. A
  drive drains 1 pack.
- **One charging station that never runs out.** A `(charging_station ?s)`
  predicate and a `recharge` action that fills the rover to capacity without
  decreasing anything. A large finite stash would not do: proving solvability
  would then need a bound on what gets used.
- **Packs move in amounts.** `pick_up` and `drop` take an `?q - amount` object
  with a static `(value ?q)` set to powers of two (1, 2, 4, ...), so a load
  takes one action per binary digit (7 = 4 + 2 + 1) instead of one action per
  pack.
- **No dropping at the charging station.** `drop` requires
  `(not (charging_station ?s))`. Dropping packs there is pointless, and it
  would let the packs left at the station grow without bound: the state space
  becomes infinite, and no complete search can prove a dead end.
- **Rovers start with 0 packs**, so every pack is on the map, and a rover on an
  empty site is stranded.
- **Goals:** `(at rover site)` for every rover.

Checked with Tamerlite on 2026-10-15, under the old names: every feature of
the domain is supported, and Tamerlite grounds through unified-planning's
grounder, which turns `(value ?q)` and `rover_capacity` into plain numbers (the
grounded problem is simple numeric planning).

## Rover roles

In the base version every rover has the same capacity, `rover_capacity`,
written C below. Per-role capacities are optional additions, listed in the
quirk table where they help.

- **1 saviour**, guaranteed to reach the charging station D (see
  "Construction").
- **`n_leech` leeches**, starting with the saviour at S and sharing its packs.
  Any one of them can play the saviour in a plan; what matters is that only
  one leaves S first.
- **`n_stranded` stranded rovers**, each on an empty site with 0 packs
  (several may share one). They cannot move until another rover drops packs
  where they are.
- **`n_randoms` random rovers**, placed anywhere but on their own goal site,
  the charging station included. One that reaches D on its own acts as a
  second saviour and can defuse traps. `n_randoms` = 0 prevents that (see
  also `random_capacity` under "Quirks").

The roles exist only inside the generator. **Rover and site names are
generic and numbered in a random order; objects are listed by these numbers
and the initial facts are written in a random order**, so neither a name nor a
position in the file gives away
the saviour, the charging station's surroundings, or the distance to anything.
(The IPC expedition set's names, `wa0`…`wa5`, encode each waypoint's position
along its chain.)

## Generator parameters

| parameter | meaning |
|---|---|
| `n_sites` | size of the graph, at least C + `n_goal_sites` |
| `rover_capacity` | C, the capacity of every rover, at least 3; sets the goal band and the plan size (see "Size") |
| `n_leech`, `n_stranded`, `n_randoms` | how many rovers of each role |
| `slack` | packs beyond the saviour's exact need = wasted packs the instance forgives |
| `n_goal_sites` | 1 = every rover goes to the same site, the main station; one per rover = each to its own work station. At most the number of rovers |
| `stash_density` | percentage (0–100) of the sites holding a scattered stash, rounded down; fewer when not enough sites qualify (see step 6 of "Construction") |
| `stash_total` | total scattered packs, in units of C |
| `seed` | everything else: graph shape, positions, amounts, names, order of the facts |


## Construction

D is the charging station, S the saviour's start, and d the distance between
them.

1. Draw a random **connected** graph (a disconnected one is just two problems
   in one file). It starts as a random tree rooted at D: a chain of C sites
   leaves D, so some site is C steps away, and every other site hangs from a
   random site already placed, never more than 2C steps from D (see "Size").
   The first `n_goal_sites` − 1 of those hang at least C steps from D, so
   there are enough goal sites. Then the seed adds between none and
   `n_sites`/2 extra edges, each between two sites whose distances from D
   differ by at most 1. Such an edge cannot shorten any distance to D, so the
   tree's paths to D stay shortest paths on the full graph.
2. Pick the `n_goal_sites` goal sites, between C and 2C steps from D. Each goal
   site goes to at least one rover; the other rovers get one of them at
   random.
3. Pick S, at least 2 steps from D and not a goal site, so that no rover at S
   starts on its goal.
4. Supply the saviour's path, the tree's path from S to D: a stash every C
   steps from S (the last gap shorter), each holding exactly the distance to
   the next stash or to D, plus `slack` at S. So if d ≤ C, S alone holds
   d + `slack`. The saviour starts with 0 packs and reaches D with none left.
5. Place the leeches at S, the stranded rovers on sites with no packs other
   than D, and the random rovers anywhere. No rover starts on its own goal
   site: its goal would be reached for free, and a stranded rover there would
   need no rescue.
6. Scatter the stashes: `stash_total` × C packs, split at random over
   `stash_density` % of the sites, at least 1 pack each. **No scattered stash
   may give the rovers at S more than their d + `slack` packs**, or it would
   defuse the traps below. Until some rover reaches D, those rovers have only
   the packs on the saviour's path, and every drive spends one, so none of
   them gets further than d + `slack` steps from S on a path that avoids D.
   Stashes go only beyond that, on sites with no packs and no stranded rover;
   when too few sites qualify, there are fewer stashes. (A rule based on the
   distance from the saviour's path would miss sites on a second shortest
   path from S to D, which cost nothing to visit.) Random rovers are not
   covered: one standing on a stash can carry it anywhere, as a second
   saviour.
7. Number the rovers and the sites at random, and shuffle the initial facts
   (see "Rover roles").

## Why every instance is solvable

The saviour reaches D by construction (step 4). From D, a rover with C ≥ 3 can
place any number of packs on any site: each round trip over an edge leaves
C − 2 ≥ 1 at the far end. So every rover can be supplied to its goal, stranded
ones included, whatever the other roles' capacities. Steps 5 and 6 only add
rovers, which D can supply, and packs, so they cannot break this. The generator
builds no plan: solvability rests on this argument.

## Size

This is the jeep problem. Within C steps of packs a rover just drives; each
further C of distance multiplies the packs needed by about e² ≈ 7 (about 8
loads at 2C, about 57 at 3C). Hence the goal band of C to 2C from D: some
caching, no blow-up. For the same reason no site is more than 2C from D, so no
rescue blows up either. The size comes from the C-to-distance ratio, not from
the number of sites.

## Quirks

- **trap:** a dead end a heuristic can walk into.
- **shortcut:** a much shorter plan a heuristic can miss.
- **requirement:** something every plan has to do.

Every trap here is a budget trap: it wastes the saviour's packs. It bites only
if no second saviour exists and if the waste exceeds `slack`. No second
saviour means `n_randoms` = 0, or, with the **new** `random_capacity`, random
rovers of capacity ≤ 2, too small to build caches from D. Step 6 keeps
scattered stashes from defusing it.

The generator implements the two quirks that need no **new** parameter, the
leeches and the stranded rovers. The rest of the table is planned, though some
of those quirks can already appear at random, as their rows say.

**"At random"** means the quirk shows up when parameter values are sampled
from their ranges (as ConfigSpace does), or when the seed's placement happens
to create it. The generator adds no randomness of its own for these.

The **bait zone** is the sites one or two steps off the saviour's path, near S,
that lie on no shortest path from S to D. If the graph has none, the generator
would add a short spur. A bait k steps off the path wastes 2k packs.

| quirk | type | description | to guarantee it | to make it appear at random | consequences on the generator |
|---|---|---|---|---|---|
| Leeches | trap | Rovers sharing the saviour's exact budget at S. With `slack` 0, two of them driving one step together is already a dead end | `n_leech` ≥ 1; `slack` sets how many joint steps are survivable (implemented) | sample `n_leech` from a range that includes 0 | place the leeches at S |
| Weak leech (wrong saviour) | trap | A leech drives the path to D, which looks like progress, but with capacity ≤ 2 it cannot build caches from D, and S's budget is gone | **new:** `leech_capacity` ≤ 2; `n_leech` ≥ 1 | sample `leech_capacity` from a range reaching down to 1 | path stashes at most `leech_capacity` apart when it is below C, so the leech can drive the path (changes step 4); D at least 2 steps from S (step 3). When `leech_capacity` is 2, no stranded rover of capacity ≥ 3 next to D: a capacity-2 rover can carry 1 pack one step from D, enough to free it, and it becomes a real saviour |
| Stranded rover | requirement | 0 packs on an empty site; it has a goal, so it must be rescued | `n_stranded` ≥ 1 (implemented) | sample `n_stranded` | no stash on its site (step 6) |
| Big stranded rover | shortcut | A stranded rover bigger than the saviour. Rescuing it first and letting it ferry is much shorter | **new:** `stranded_capacity` > C; `n_stranded` ≥ 1 | sample `stranded_capacity` above and below C | one stranded rover within C/2 of D, so its rescue is a single trip (changes step 5). Above 2C nothing changes, since every goal is within 2C of D. Very likely the shorter plan, but proving it would need an optimal planner |
| Saviour near its goal | trap | The saviour's goal is in the bait zone; going there first strands it. The right plan goes to D, helps the others, and returns last. Targets heuristics that reward satisfied goals | **new:** `saviour_goal_bait` flag; `slack` < 2k | seed: the saviour's goal lands in the bait zone (rare) | bait zone. With `n_goal_sites` = 1 every goal moves next to S, so S must be C to 2C from D and its path needs stashes |
| Premature rescue | trap | A stranded rover in the bait zone. A saviour that detours to rescue it before reaching D leaves both stuck | **new:** `stranded_bait` flag; `n_stranded` ≥ 1; `slack` < 2k | seed: a stranded rover lands in the bait zone | bait zone; the bait is one of the `n_stranded` rovers |
| Bait stash | trap | A stash in the bait zone holding g packs, with 2k − g > `slack`: it costs more to fetch than it gives | **new:** `n_bait_stashes` | none: step 6 keeps scattered stashes out of reach of S, bait zone included | bait zone; amounts outside `stash_total` |
| Decoy station | trap | A large but finite stash nearer than D, on the far side from it. Rovers that go there use it up and can no longer reach D. Targets heuristics that treat a large stash as unlimited | **new:** `n_decoys` | none in practice | its amount must stay below the cost of reaching D from it, computed with the ferry arithmetic; outside `stash_total`. Only possible when D is well beyond C from the decoy: on a small map, any stash large enough to look like a charging station gets a rover to D |

Two parameters shape every instance without being quirks:

- **Goal layout** (`n_goal_sites`): one shared goal site, the main station,
  means one route to stock for everyone; separate goal sites, the work
  stations, mean separate routes, and the order of rescues matters.
- **Symmetry:** many identical leeches or stashes give large plateaus of
  equivalent states, a difficulty knob that `n_leech` already provides.

The **new** per-role capacities give every rover of a role the same capacity;
mixing weak and strong leeches would need a range per role.

## Possible expansions: domain changes (a possible later version)

- **Collapsing ground.** An edge that can be crossed only once: a tempting
  shortcut on the way out, but the way back is long. The proof holds if the
  graph stays connected without the collapsing edges.
- **Narrow canyons.** A site that holds one rover at a time. A rover stranded
  in a canyon blocks it for good, since nobody can enter to drop packs. Adds
  factory-robot-style blocking. For the proof: never place a stranded rover in
  a canyon, and keep the graph connected without the canyons.
- **Locked station.** D charges only after some rover has switched on a relay
  at a key site, which tests enabling steps far from any goal. For the proof,
  the saviour's path runs from S through the key site to D.
- **Drain per edge** (`(drain ?a ?b)`). Rough terrain drains more packs per
  drive, so routes differ by more than hop count. Needs C ≥ 2·(largest drain)
  + 1.

## Name and theme

The design started as expedition+, a variant of the IPC expedition domain, and
was then renamed:

| expedition+ | Space Rescue |
|---|---|
| sled (`sled`) | rover (`rover`) |
| waypoint (`waypoint`) | site (`site`) |
| supplies: `sled_supplies`, `waypoint_supplies` | battery packs: `rover_packs`, `site_packs` |
| `sled_capacity` | `rover_capacity` (the rover's battery slots) |
| depot, `(depot ?w)` | charging station, `(charging_station ?s)` |
| `move`, `retrieve`, `store`, `resupply` | `drive`, `pick_up`, `drop`, `recharge` |
| sleds `s1`…, waypoints `w1`… | rovers `r1`…, sites `s1`… |
| `n_waypoints`, `sled_capacity`, `n_goal_nodes` | `n_sites`, `rover_capacity`, `n_goal_sites` |
