# UP-Benchmarks

NOTE - this library is still in development - behaviour might be instable

Planning Benchmarks Manager. This library provides a centralized repository and a unified interface to generate, sample, and manage planning problem instances.

## Installation

```bash
pip install .
```

## CLI Usage

The manager is accessible via `main.py`.

### List Registered Domains

```bash
python3 main.py domains
```

### Inspect Parameters

To see domain-level parameters (e.g., variants, versions):
```bash
python3 main.py domain-params matchcellar
```

To see instance-level parameters (e.g., number of objects) for a specific domain configuration:
```bash
python3 main.py instance-params matchcellar -d variant ipc
```

### Generate a Single Instance

Generate an instance and print it to stdout:
```bash
python3 main.py mkinstance matchcellar -d variant ipc -p n_matches 5 -p n_fuses 5
```

Save to a specific file:
```bash
python3 main.py mkinstance matchcellar -d variant ipc -p n_matches 5 -o problem.pddl -D domain.pddl
```

Note that if the requested instance is unsolvable an error will be raised

### Sample Instances

Sample 5 instances with random parameters, fixing some of them and giving a range for others:
```bash
python3 main.py sample matchcellar 5 -d variant ipc -p n_fuses 5 -r n_matches 3 10 -o ./samples
```

Use `-p parameter_name fixed_value` to fix a parameter value and `-r parameter_name min_value max_value` to specify a range.

If no constraint is specified for one parameter, it will be sampled from the maximum possible size (usually from the range [1, 2^31])

### Generate a Dataset from Spec

Generate all instances defined in a YAML specification:
```bash
python3 main.py mkset sets/matchcellar_small.yml ./out
```

## API Usage

The library can be used programmatically through the `DomainFactory` class.

### Basic Initialization

```python
from upbm import DomainFactory, Format

factory = DomainFactory()

# List all domains
domains = factory.get_registered_domains()
print(f"Available domains: {domains}")
```

### Generating an Instance

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

### Sampling and Exporting

```python
from upbm import dump_instance
from upbm.utils import get_reduced_instance_space

# Create smaller parameter space
largest_possible_space = factory.get_instance_parameter_space(domain="matchcellar", domain_params=domain_params)
reduced_space = get_reduced_instance_space(largest_possible_space, {"n_matches": 10, "n_fuses": (5, 20)})

# Sample 10 instances
problems = factory.sample_instances("matchcellar", domain_params, n=10, instance_parameter_space=reduced_space)

# Save the first one as PDDL
dump_instance(problems[0], Format.PDDL, "prob.pddl", "dom.pddl")
```

## Available Benchmarks

### "Our" Benchmarks
- **MAJSP (AAAI 2019) + modifications**
  - Format: UP
  - Features: ICE, Bounded Numbers, Bounded Numeric Params, Required Concurrency
- **Kitting (AAAI 21) + modifications**
  - Format: UP
  - Features: ICE, Bounded Numbers, Bounded Numeric Params, Required Concurrency
  - Hardness: "Looping Behavior", "Numeric Indexing Goals"
- **Replenish + modifications**
  - Format: UP
  - Features: Bounded Numbers, Bounded Numeric Params
  - Hardness: "Looping Behavior", "Numeric Indexing Goals"
- **Painter (AAAI 20)** _not yet implemented_
  - Format: ANML
  - Features: ICE, Bounded Numbers, Required Concurrency
- **Temporal Sailing (ICAPS 26)** _not yet implemented_
  - Format: PDDL
  - Features: Numbers, Timed Effects, Required Concurrency with Deadline
- **Temporal Plant Watering (ICAPS 26)** _not yet implemented_
  - Format: PDDL
  - Features: Numbers, Required Concurrency
- **SimpleMAIS/HSP (AAAI 2019 but extended)** _not yet implemented_
  - Format: ANML/TPACK
  - Features: ICE, Numbers, Bounded Numeric Params, Required Concurrency

### IPC Benchmarks
- **MatchCellar (Crickey) + modifications**
  - Format: UP/PDDL
  - Features: Required Concurrency
- **Driverlog** _not yet implemented_: PDDL
- **Satellite** _not yet implemented_: PDDL
- **Parking** _not yet implemented_: PDDL
- **FloorTile** _not yet implemented_: PDDL
- **TurnAndOpen** _not yet implemented_: PDDL
- **MapAnalyser** _not yet implemented_: PDDL
- **TMS** _not yet implemented_: PDDL
