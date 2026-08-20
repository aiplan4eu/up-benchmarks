# UP-Benchmarks

A centralized repository and unified interface to **generate, sample, and manage planning problem instances**.

> **Note:** This library is still under active development. Interfaces and behaviour may change between releases and might be unstable.

## Installation

Requires Python ≥ 3.10. From the repository root:

```bash
pip install .
```

## Quick Start

```bash
# 1. See what domains are available
python3 main.py domains

# 2. Generate a MatchCellar instance and print it to stdout
python3 main.py mkinstance matchcellar -d variant ipc -p n_matches 5 -p n_fuses 5
```

## CLI Usage

All commands are accessed via `main.py`.

### List registered domains

```bash
python3 main.py domains
```

### Inspect parameters

Domain-level parameters (e.g. variants, versions):

```bash
python3 main.py domain-params matchcellar
```

Instance-level parameters (e.g. number of objects) for a specific domain configuration:

```bash
python3 main.py instance-params matchcellar -d variant ipc
```

### Generate a single instance

Generate an instance and print it to stdout:

```bash
python3 main.py mkinstance matchcellar -d variant ipc -p n_matches 5 -p n_fuses 5
```

Save to specific files:

```bash
python3 main.py mkinstance matchcellar -d variant ipc -p n_matches 5 -o problem.pddl -D domain.pddl
```

If the requested instance is unsolvable, an error is raised.

### Sample instances

Sample 5 instances with random parameters, fixing some and giving a range for others:

```bash
python3 main.py sample matchcellar 5 -d variant ipc -p n_fuses 5 -r n_matches 3 10 -o ./samples
```

- `-p parameter_name fixed_value` — fix a parameter to a single value.
- `-r parameter_name min_value max_value` — sample a parameter from a range.
- If no constraint is given for a parameter, it is sampled from the maximum possible size (usually the range `[1, 2^31]`).

### Generate a dataset from a spec

Generate all instances defined in a YAML specification (see [Dataset Specification](#dataset-specification-yaml) below):

```bash
python3 main.py mkset sets/matchcellar_small.yml ./out
```

### Output format

`mkinstance`, `sample`, and `mkset` accept `--format {pddl,anml}` (default `pddl`):

```bash
python3 main.py mkinstance matchcellar -d variant ipc -p n_matches 5 --format anml -o problem.anml
```

PDDL output produces a separate domain and problem file; ANML output produces a single file. Generating PDDL for a domain that is not PDDL-expressible raises an error.

## Dataset Specification (YAML)

A `mkset` spec selects a domain, fixes the domain-level parameters, and lists named instances with their instance-level parameters:

```yaml
domain: matchcellar
params:                # domain-level parameters
  version: 1
  variant: ipc
instances:
  - name: instance1
    params:            # instance-level parameters
      n_matches: 1
      n_fuses: 1
  - name: instance2
    params:
      n_matches: 1
      n_fuses: 2
```

Output naming under the target directory:

- **PDDL** — `domain_<name>.pddl` and `problem_<name>.pddl` per instance.
- **ANML** — `<name>.anml` per instance.

## API Usage

The library can be used programmatically through the `DomainFactory` class.

### Basic initialization

```python
from upbm import DomainFactory, Format

factory = DomainFactory()

# List all domains
domains = factory.get_registered_domains()
print(f"Available domains: {domains}")
```

### Generating an instance

```python
# 1. Get parameter spaces
dom_space = factory.get_domain_parameter_space("matchcellar")

# 2. Parse configurations (validates types and ranges)
domain_params = factory.parse_configuration({"variant": "ipc"}, dom_space)

inst_space = factory.get_instance_parameter_space("matchcellar", domain_params)
instance_params = factory.parse_configuration({"n_matches": 5, "n_fuses": 5}, inst_space)

# 3. Generate the Unified Planning Problem object
problem = factory.generate_instance("matchcellar", domain_params, instance_params)

print(f"Problem name: {problem.name}")
```

### Sampling and exporting

```python
from upbm import dump_instance
from ConfigSpace import (
    ConfigurationSpace,
    Integer,
    Constant,
)

# Create a smaller parameter space
reduced_space = ConfigurationSpace(
    {
        "n_matches" : Constant("n_matches", 10),
        "n_fuses" : Integer("n_fuses", (5, 20))
    }
)

# Sample 10 instances
problems = factory.sample_instances(
    "matchcellar", domain_params, n=10, instance_parameter_space=reduced_space
)

# Save the first one as PDDL
dump_instance(problems[0], Format.PDDL, "prob.pddl", "dom.pddl")
```

### Registering domains

The built-in domains are registered automatically when a `DomainFactory` is
constructed. You can also register additional generators yourself — either to
expose your own generator class, or to register a bundled generator under a
different name.

Use `register(name, generator_class)` with any `Generator` subclass, including
the generator classes that ship with the package:

```python
from upbm import DomainFactory
from upbm.domains.matchcellar import MatchCellarGenerator

factory = DomainFactory()

# Register a bundled generator under an additional name
factory.register("matchcellar_alias", MatchCellarGenerator)

# ...or register your own generator class
# factory.register("my_domain", MyGenerator)

assert "matchcellar_alias" in factory.get_registered_domains()
```

Registrations are per-instance: each `DomainFactory()` starts with only the
built-ins, so names registered on one factory do not leak into another.

The bundled generator classes are:

| Domain | Import |
| --- | --- |
| matchcellar | `from upbm.domains.matchcellar import MatchCellarGenerator` |
| majsp | `from upbm.domains.majsp import MaJSPGenerator` |
| kitting | `from upbm.domains.kitting import KittingGenerator` |
| replenish | `from upbm.domains.replenish import ReplenishGenerator` |
| sailing-wind | `from upbm.domains.sailing_wind import SailingWindGenerator` |

### Registering domains via `.upbm` plugins

To register generators declaratively (without editing code), create a `.upbm`
YAML file in your home directory (`~/.upbm`) and/or the current working
directory (`./.upbm`). It declares a `plugins` mapping of
`domain_name: "module.path:ClassName"`:

```yaml
plugins:
  my_domain: "mypackage.generators:MyGenerator"
  matchcellar_alias: "upbm.domains.matchcellar:MatchCellarGenerator"
```

These are discovered and registered automatically when a `DomainFactory` is
constructed. The target module must be importable on `sys.path`. If you install
a new plugin during a session, call `factory.reload_plugins()` to pick it up
without creating a new factory.

## Available Benchmarks

The following domains are implemented and registered today:

| Domain | Format | Features | Notes |
| --- | --- | --- | --- |
| **MAJSP** (AAAI 2019) + modifications | UP | ICE, Bounded Numbers, Bounded Numeric Params, Required Concurrency | Multi-agent job-shop scheduling |
| **Kitting** (AAAI 2021) + modifications | UP | ICE, Bounded Numbers, Bounded Numeric Params, Required Concurrency | Hardness: Looping Behavior, Numeric Indexing Goals |
| **Replenish** + modifications | UP | Bounded Numbers, Bounded Numeric Params | Hardness: Looping Behavior, Numeric Indexing Goals |
| **MatchCellar** (IPC) + modifications | UP/PDDL | Required Concurrency | Running example throughout this README |
| **Sailing-Wind** (IPC 2026) | UP/PDDL | Numbers, Real Fluents, Disjunctive Conditions | A boat tacks against the wind to reach people at sea and stop next to them; `opt` and `sat` variants |

### Planned

These are referenced in our roadmap but **not yet implemented**:

| Domain | Intended format | Features |
| --- | --- | --- |
| Painter (AAAI 2020) | ANML | ICE, Bounded Numbers, Required Concurrency |
| Temporal Sailing (ICAPS 2026) | PDDL | Numbers, Timed Effects, Required Concurrency with Deadline |
| Temporal Plant Watering (ICAPS 2026) | PDDL | Numbers, Required Concurrency |
| SimpleMAIS/HSP (AAAI 2019, extended) | ANML/TPACK | ICE, Numbers, Bounded Numeric Params, Required Concurrency |
| Driverlog (IPC) | PDDL | — |
| Satellite (IPC) | PDDL | — |
| Parking (IPC) | PDDL | — |
| FloorTile (IPC) | PDDL | — |
| TurnAndOpen (IPC) | PDDL | — |
| MapAnalyser (IPC) | PDDL | — |
| TMS (IPC) | PDDL | — |

## License

Licensed under the [Apache License 2.0](LICENSE).
