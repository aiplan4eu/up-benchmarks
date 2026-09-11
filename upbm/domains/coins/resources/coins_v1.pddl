;; Source: ipc2026-dataset/coins/domain.pddl (IPC 2026 dataset), unmodified.
;
; Minimum Coins
;
;   Author: Connor Little
;
;   Summary: Given a set of denominations of coins, make the target result using the minimum number.
;
;   Finding a feasible solution is easy, finding an optimal solution is hard.
;
;            ...

(define (domain coins)

    (:requirements :fluents :typing)

    (:types
        coin
    )

    (:predicates
        (coin-update ?c - coin)
        (no-coin-update ?c - coin)
    )


    (:functions
        (current-value); the current value in the sequence
        (coin-count) ; number of coins used
        (denomination ?c - coin) ; coin denominations available
        (denomination-penalty ?c - coin) ; penalty for using coin
        (penalty) ; penalty counter
    )

    (:action addCoin
        :parameters (?c - coin)
        :precondition (and 
                (= (penalty) 0)
                (no-coin-update ?c)
            )
        :effect (and 
            (increase (current-value) (denomination ?c))
            (increase (penalty) (denomination-penalty ?c))
            (coin-update ?c)
            (not (no-coin-update ?c))

        )
    )

    (:action update-penalty
        :parameters (?c - coin)
        :precondition (and (coin-update ?c))
        :effect (and 
            (increase (denomination-penalty ?c) 1)
            (not (coin-update ?c))
            (no-coin-update ?c)
        )
    )
    

    (:action apply-penalty-one
        :parameters ()
        :precondition (and 
            (>= (penalty) 1)
        )
        :effect (and 
            (decrease (penalty) 1)
            (increase (coin-count) 1)
        )
    )

    (:action apply-penalty-ten
        :parameters ()
        :precondition (and 
            (>= (penalty) 10)
        )
        :effect (and 
            (decrease (penalty) 10)
            (increase (coin-count) 10)
        )
    )

    (:action apply-penalty-hundred
        :parameters ()
        :precondition (and 
            (>= (penalty) 100)
        )
        :effect (and 
            (decrease (penalty) 100)
            (increase (coin-count) 100)
        )
    )

    (:action apply-penalty-thousand
        :parameters ()
        :precondition (and 
            (>= (penalty) 1000)
        )
        :effect (and 
            (decrease (penalty) 1000)
            (increase (coin-count) 1000)
        )
    )

    (:action apply-penalty-ten-thousand
        :parameters ()
        :precondition (and 
            (>= (penalty) 10000)
        )
        :effect (and 
            (decrease (penalty) 10000)
            (increase (coin-count) 10000)
        )
    )

)