from ConfigSpace import (
    ConfigurationSpace,
    Constant,
    CategoricalHyperparameter,
)

MAX_INT = 2**31 - 1


def is_subspace(small: ConfigurationSpace, big: ConfigurationSpace):
    if len(small.keys()) != len(big.keys()):
        return False
    for key in small.keys():
        if key not in big.keys():
            return False
        small_hyperpar = small[key]
        big_hyperpar = big[key]
        if isinstance(small_hyperpar, Constant):
            # big is either a constant of the same value or a range that contains the value
            if isinstance(big_hyperpar, Constant):
                if big_hyperpar.value != small_hyperpar.value:
                    return False
            else:  # range
                if (
                    small_hyperpar.value > big_hyperpar.upper
                    or small_hyperpar.value < big_hyperpar.lower
                ):
                    return False
        elif isinstance(small_hyperpar, CategoricalHyperparameter):
            # big is categorical and contains all possible values found in small
            if not isinstance(big_hyperpar, CategoricalHyperparameter):
                return False
            for small_choice in small_hyperpar.choices:
                if small_choice not in big_hyperpar.choices:
                    return False
        else:
            # this should be a range, check min max
            if small_hyperpar.lower < big_hyperpar.lower:
                return False
            if small_hyperpar.upper > big_hyperpar.upper:
                return False
    return True
