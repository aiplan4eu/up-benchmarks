;; Source: ipc2026-dataset/ztalloc-sum/domain.pddl (IPC 2026 dataset), unmodified.
;
; Ztalloc: Reversed Collatz
;
;   Original author: Christian Muise
;
;   Summary: A numeric domain for the reversed Collatz problem, where the objective is to start from 1 to reach a target number n.
;            Either of the reversed Collatz operations can be applied at each step, and the goal is to minimize the number of steps.
;
;            The original Collatz problem is to start with a number n and apply the following operations until you reach 1:
;            - If n is even, divide it by 2.
;            - If n is odd, multiply it by 3 and add 1.
;
;            In this reversed version, we start with 1 and try to reach some arbitrary number. No restrictions are
;            placed on the intermediate values, and the goal is to minimize the number of steps taken to reach 1.
;
;            Solutions are guaranteed to exist, assuming the Collatz conjecture holds. The author personally thinks this is
;            probably the case ;).
;
;   IPC Edit: The original domain was modified to accommodate multiple numbers to be combined together in order to reach a given target
;

(define (domain ztalloc-sum)

    (:requirements :typing :strips :numeric-fluents :action-costs)

    (:types register)

    (:predicates
        (free)
        (normal ?r - register)
        (m1d3-after-dec ?r - register)
        (m1d3-dividing ?r - register)
    )

    (:functions
        (value ?r - register)
        (work-value ?r - register)
        (total-cost)
    )

    (:action double
        :parameters (?r - register)
        :precondition (and
            (free)
            (normal ?r)
        )
        :effect (and
            (increase (value ?r) (value ?r))
            (increase (total-cost) 1)
        )
    )

    (:action m1d3-start
        :parameters (?r - register)
        :precondition (and
            (free)
            (normal ?r)
            (>= (value ?r) 1)
            (= (work-value ?r) 0)
        )
        :effect (and
            (not (free))
            (not (normal ?r))
            (m1d3-after-dec ?r)
            (decrease (value ?r) 1)
            (increase (total-cost) 1)
        )
    )

    (:action m1d3-copy-reset
        :parameters (?r - register)
        :precondition (and
            (m1d3-after-dec ?r)
        )
        :effect (and
            (not (m1d3-after-dec ?r))
            (m1d3-dividing ?r)
            (increase (work-value ?r) (value ?r))
            (decrease (value ?r) (value ?r))
        )
    )

    (:action m1d3-div-step
        :parameters (?r - register)
        :precondition (and
            (m1d3-dividing ?r)
            (>= (work-value ?r) 3)
        )
        :effect (and
            (decrease (work-value ?r) 3)
            (increase (value ?r) 1)
        )
    )

    (:action m1d3-finish
        :parameters (?r - register)
        :precondition (and
            (m1d3-dividing ?r)
            (= (work-value ?r) 0)
        )
        :effect (and
            (not (m1d3-dividing ?r))
            (free)
            (normal ?r)
        )
    )
)
