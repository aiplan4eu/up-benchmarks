import argparse
from pathlib import Path

from upbm import (
    DomainFactory,
    Format,
    dump_instance,
    print_instance,
    print_parameter_space,
)


def main():
    parser = argparse.ArgumentParser(description="Temporal Planning Benchmarks Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # mkset command
    mkset_parser = subparsers.add_parser("mkset", help="Create a new dataset")
    mkset_parser.add_argument("set", type=Path, help="Path to the dataset to generate")
    mkset_parser.add_argument(
        "outdir", type=Path, help="Output directory for the generated dataset"
    )
    mkset_parser.add_argument(
        "--format",
        type=str,
        required=False,
        choices=["pddl", "anml"],
        default="pddl",
        help="Output format",
    )

    # mkinstance command
    mkinstance_parser = subparsers.add_parser(
        "mkinstance", help="Create a new instance"
    )
    mkinstance_parser.add_argument("domain", type=str, help="Domain name")
    mkinstance_parser.add_argument(
        "-d",
        "--domparam",
        nargs=2,
        action="append",
        default=[],
        help="Domain parameter in the form -d param_name param_value",
    )
    mkinstance_parser.add_argument(
        "-p",
        "--param",
        nargs=2,
        action="append",
        default=[],
        help="Instance parameter in the form -p param_name param_value",
    )
    mkinstance_parser.add_argument(
        "-D",
        "--output-dom",
        type=Path,
        required=False,
        help="Output file for the generated domain (PDDL format only)",
    )
    mkinstance_parser.add_argument(
        "-o",
        "--output-prob",
        type=Path,
        required=False,
        help="Output file for the generated problem",
    )
    mkinstance_parser.add_argument(
        "--format",
        type=str,
        required=False,
        choices=["pddl", "anml"],
        default="pddl",
        help="Output format",
    )

    # instance-params command
    showparams_parser = subparsers.add_parser(
        "instance-params", help="Show available parameters for a domain"
    )
    showparams_parser.add_argument("domain", type=str, help="Domain name")
    showparams_parser.add_argument(
        "-d",
        "--domparam",
        nargs=2,
        action="append",
        default=[],
        help="Domain parameter in the form -d param_name param_value",
    )

    # domain-params command
    domparams_parser = subparsers.add_parser(
        "domain-params", help="Show domain-level parameters for a domain"
    )
    domparams_parser.add_argument("domain", type=str, help="Domain name")

    # domains command
    subparsers.add_parser("domains", help="List all registered domains")

    # sample command
    sample_parser = subparsers.add_parser("sample", help="Sample from dataset")
    sample_parser.add_argument("domain", type=str, help="Domain name")
    sample_parser.add_argument("n", type=int, help="Sample size")
    sample_parser.add_argument(
        "-d",
        "--domparam",
        nargs=2,
        action="append",
        default=[],
        help="Domain parameter in the form -d param_name param_value",
    )
    sample_parser.add_argument(
        "-p",
        "--param",
        nargs=2,
        action="append",
        default=[],
        help="Instance parameter in the form -p param_name param_value",
    )
    sample_parser.add_argument(
        "-r",
        "--paramrange",
        nargs=3,
        action="append",
        default=[],
        help="Instance parameter range in the form -r param_name min_value, max_value",
    )
    sample_parser.add_argument(
        "-o",
        "--output-folder",
        type=Path,
        required=False,
        help="Output folder for the generated instances",
    )
    sample_parser.add_argument(
        "--format",
        type=str,
        required=False,
        choices=["pddl", "anml"],
        default="pddl",
        help="Output format",
    )

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    factory = DomainFactory()

    match args.command:
        case "domains":
            for domain in factory.get_registered_domains():
                print(domain)

        case "mkset":
            print(
                f"Creating dataset at {args.set} with output directory {args.outdir} in format {args.format}"
            )
            args.outdir.mkdir(parents=True, exist_ok=True)
            fmt = Format(args.format)

            instances, pddl_expressible = factory.generate_dataset(args.set)
            if fmt == Format.PDDL and not pddl_expressible:
                raise ValueError(f"Domain {args.domain} is not expressible in PDDL.")

            for name, problem in instances:
                print(f"Generated instance {name}...")
                if fmt == Format.PDDL:
                    dom_file = args.outdir / f"domain_{name}.pddl"
                    prob_file = args.outdir / f"problem_{name}.pddl"
                else:
                    dom_file = None
                    prob_file = args.outdir / f"{name}.anml"

                dump_instance(problem, fmt, prob_file, dom_file)

        case "mkinstance":
            print(
                f"Creating instance for domain {args.domain} with params {args.param} in format {args.format}"
            )

            dom_space = factory.get_domain_parameter_space(args.domain)
            domain_params = factory.parse_configuration(dict(args.domparam), dom_space)

            inst_space = factory.get_instance_parameter_space(
                args.domain, domain_params
            )
            instance_params = factory.parse_configuration(dict(args.param), inst_space)

            instance = factory.generate_instance(
                args.domain, domain_params, instance_params
            )

            fmt = Format(args.format)
            if fmt == Format.PDDL and not factory.is_pddl_expressible(
                args.domain, domain_params
            ):
                raise ValueError(f"Domain {args.domain} is not expressible in PDDL.")

            if args.output_prob:
                dump_instance(instance, fmt, args.output_prob, args.output_dom)
            else:
                print_instance(instance, fmt)

        case "domain-params":
            print(f"Showing domain parameters for domain {args.domain}")
            dom_space = factory.get_domain_parameter_space(args.domain)
            print_parameter_space(dom_space)

        case "instance-params":
            print(f"Showing instance parameters for domain {args.domain}")
            dom_space = factory.get_domain_parameter_space(args.domain)
            domain_params = factory.parse_configuration(dict(args.domparam), dom_space)

            inst_space = factory.get_instance_parameter_space(
                args.domain, domain_params
            )
            print_parameter_space(inst_space)

        case "sample":
            print(
                f"Sampling {args.n} instances from domain {args.domain} in format {args.format}"
            )

            dom_space = factory.get_domain_parameter_space(args.domain)
            domain_params = factory.parse_configuration(dict(args.domparam), dom_space)

            if args.output_folder:
                args.output_folder.mkdir(parents=True, exist_ok=True)

            fmt = Format(args.format)
            if fmt == Format.PDDL and not factory.is_pddl_expressible(
                args.domain, domain_params
            ):
                raise ValueError(f"Domain {args.domain} is not expressible in PDDL.")

            reducing_dict = {}
            for plist in args.param:
                reducing_dict[plist[0]] = plist[1]
            for prlist in args.paramrange:
                reducing_dict[prlist[0]] = (prlist[1], prlist[2])

            instance_space = factory.get_reduced_instance_space(
                args.domain, domain_params, reducing_dict
            )

            problems = factory.sample_instances(
                args.domain, domain_params, args.n, instance_space
            )

            for i, instance in enumerate(problems):
                print(f"Generated sample instance {i+1}/{args.n}")
                if args.output_folder:
                    prob_file = args.output_folder / f"problem_{i+1}.pddl"
                    dom_file = (
                        args.output_folder / f"domain_{i+1}.pddl"
                        if fmt == Format.PDDL
                        else None
                    )
                    if fmt == Format.ANML:
                        prob_file = args.output_folder / f"{i+1}.anml"
                    dump_instance(instance, fmt, prob_file, dom_file)
                else:
                    print_instance(instance, fmt)

        case _:
            print(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
