; Source: IPC 2026 dataset, 2048/domain.pddl (copied verbatim).
;
; 2048
;
;   Author: Christian Muise, Samantha Papais, Ronny Rochwerg
;
;   Summary: A numeric planning model of the 2048 sliding tile puzzle. Tiles
;            are moved individually in four directions; equal adjacent tiles
;            merge and double. The goal is to create a target board configuration
;
;   Notes: In the real game all tiles slide simultaneously and a new tile
;          spawns after each move. This model abstracts away spawning and
;          treats each individual tile slide/merge as a separate action.
;
;   Shift actions are named by their zero/non-zero pattern at ordered
;   positions p1..p4 (target-edge to far-edge). Positions are resolved
;   via (pos-at ?d ?r ?idx ?p) so the grounder never enumerates pos^4.
;
;   Phase state machine (free-to-play x must-combine):
;     (T, F) -> play      -> (F, T)  first shift
;     (F, T) -> shift     -> (T, T)  combine
;     (T, T) -> combine   -> (F, F)  second shift
;     (F, F) -> shift     -> (T, F)  ready

(define (domain twenty-forty-eight)

    (:requirements :fluents :typing :negative-preconditions :equality)

    (:types pos status direction idx)

    (:constants
        p11 p12 p13 p14
        p21 p22 p23 p24
        p31 p32 p33 p34
        p41 p42 p43 p44 - pos

        top midtop midbot bot - status
        left midleft midright right - status
        done - status

        U D L R - direction

        i1 i2 i3 i4 - idx
    )

    (:predicates

        (shifting ?d - direction)
        (combining ?d - direction)
        (must-combine)
        (shiftstatus ?rowcol - status)
        (free-to-play)
        (next ?d - direction ?s1 ?s2 - status)

        (start-status ?d - direction ?s - status)

        ; Maps (direction, row-or-col, index) to a board position.
        ; Index i1 is closest to the target edge, i4 is farthest.
        (pos-at ?d - direction ?r - status ?i - idx ?p - pos)

        ; Chains idx positions for pair-by-pair combine iteration.
        (next-idx ?ia ?ib - idx)

        ; Tracks the current pair start index during the combine phase.
        (combine-at ?i - idx)
    )

    (:functions
        (value ?p - pos)
    )

    ; Choose a direction to shift. (T,F) -> (F,T)
    (:action play
        :parameters (?d - direction ?s - status)
        :precondition (and
            (free-to-play)
            (not (must-combine))
            (start-status ?d ?s)
        )
        :effect (and
            (not (free-to-play))
            (shifting ?d)
            (must-combine)
            (shiftstatus ?s)
        )
    )

    ;; ============================================================
    ;; Shift actions
    ;;
    ;; p1..p4 are the four positions in the current row/col,
    ;; ordered from target-edge (p1) to far-edge (p4) via pos-at.
    ;; The 4-bit name encodes the zero(0)/non-zero(1) pattern.
    ;;
    ;; Packed patterns just advance to the next row/col.
    ;; Non-packed patterns use simultaneous assign (old values)
    ;; to compact non-zeros toward the target edge, preserving
    ;; their original order.
    ;; ============================================================

    ;; ---------- Packed (no movement needed) ----------

    (:action shift-0000
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (= (value ?p1) 0) (= (value ?p2) 0) (= (value ?p3) 0) (= (value ?p4) 0)
        )
        :effect (and (not (shiftstatus ?r1)) (shiftstatus ?r2))
    )

    (:action shift-1000
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (> (value ?p1) 0) (= (value ?p2) 0) (= (value ?p3) 0) (= (value ?p4) 0)
        )
        :effect (and (not (shiftstatus ?r1)) (shiftstatus ?r2))
    )

    (:action shift-1100
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (> (value ?p1) 0) (> (value ?p2) 0) (= (value ?p3) 0) (= (value ?p4) 0)
        )
        :effect (and (not (shiftstatus ?r1)) (shiftstatus ?r2))
    )

    (:action shift-1110
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (> (value ?p1) 0) (> (value ?p2) 0) (> (value ?p3) 0) (= (value ?p4) 0)
        )
        :effect (and (not (shiftstatus ?r1)) (shiftstatus ?r2))
    )

    (:action shift-1111
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (> (value ?p1) 0) (> (value ?p2) 0) (> (value ?p3) 0) (> (value ?p4) 0)
        )
        :effect (and (not (shiftstatus ?r1)) (shiftstatus ?r2))
    )

    ;; ---------- 1-tile, non-packed ----------

    ; _ _ _ X  ->  X _ _ _
    (:action shift-0001
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (= (value ?p1) 0) (= (value ?p2) 0) (= (value ?p3) 0) (> (value ?p4) 0)
        )
        :effect (and
            (not (shiftstatus ?r1)) (shiftstatus ?r2)
            (assign (value ?p1) (value ?p4))
            (assign (value ?p4) 0)
        )
    )

    ; _ _ X _  ->  X _ _ _
    (:action shift-0010
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (= (value ?p1) 0) (= (value ?p2) 0) (> (value ?p3) 0) (= (value ?p4) 0)
        )
        :effect (and
            (not (shiftstatus ?r1)) (shiftstatus ?r2)
            (assign (value ?p1) (value ?p3))
            (assign (value ?p3) 0)
        )
    )

    ; _ X _ _  ->  X _ _ _
    (:action shift-0100
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (= (value ?p1) 0) (> (value ?p2) 0) (= (value ?p3) 0) (= (value ?p4) 0)
        )
        :effect (and
            (not (shiftstatus ?r1)) (shiftstatus ?r2)
            (assign (value ?p1) (value ?p2))
            (assign (value ?p2) 0)
        )
    )

    ;; ---------- 2-tile, non-packed ----------

    ; _ _ X X  ->  X X _ _
    (:action shift-0011
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (= (value ?p1) 0) (= (value ?p2) 0) (> (value ?p3) 0) (> (value ?p4) 0)
        )
        :effect (and
            (not (shiftstatus ?r1)) (shiftstatus ?r2)
            (assign (value ?p1) (value ?p3))
            (assign (value ?p2) (value ?p4))
            (assign (value ?p3) 0)
            (assign (value ?p4) 0)
        )
    )

    ; _ X _ X  ->  X X _ _
    (:action shift-0101
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (= (value ?p1) 0) (> (value ?p2) 0) (= (value ?p3) 0) (> (value ?p4) 0)
        )
        :effect (and
            (not (shiftstatus ?r1)) (shiftstatus ?r2)
            (assign (value ?p1) (value ?p2))
            (assign (value ?p2) (value ?p4))
            (assign (value ?p4) 0)
        )
    )

    ; _ X X _  ->  X X _ _
    (:action shift-0110
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (= (value ?p1) 0) (> (value ?p2) 0) (> (value ?p3) 0) (= (value ?p4) 0)
        )
        :effect (and
            (not (shiftstatus ?r1)) (shiftstatus ?r2)
            (assign (value ?p1) (value ?p2))
            (assign (value ?p2) (value ?p3))
            (assign (value ?p3) 0)
        )
    )

    ; X _ _ X  ->  X X _ _
    (:action shift-1001
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (> (value ?p1) 0) (= (value ?p2) 0) (= (value ?p3) 0) (> (value ?p4) 0)
        )
        :effect (and
            (not (shiftstatus ?r1)) (shiftstatus ?r2)
            (assign (value ?p2) (value ?p4))
            (assign (value ?p4) 0)
        )
    )

    ; X _ X _  ->  X X _ _
    (:action shift-1010
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (> (value ?p1) 0) (= (value ?p2) 0) (> (value ?p3) 0) (= (value ?p4) 0)
        )
        :effect (and
            (not (shiftstatus ?r1)) (shiftstatus ?r2)
            (assign (value ?p2) (value ?p3))
            (assign (value ?p3) 0)
        )
    )

    ;; ---------- 3-tile, non-packed ----------

    ; _ X X X  ->  X X X _
    (:action shift-0111
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (= (value ?p1) 0) (> (value ?p2) 0) (> (value ?p3) 0) (> (value ?p4) 0)
        )
        :effect (and
            (not (shiftstatus ?r1)) (shiftstatus ?r2)
            (assign (value ?p1) (value ?p2))
            (assign (value ?p2) (value ?p3))
            (assign (value ?p3) (value ?p4))
            (assign (value ?p4) 0)
        )
    )

    ; X _ X X  ->  X X X _
    (:action shift-1011
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (> (value ?p1) 0) (= (value ?p2) 0) (> (value ?p3) 0) (> (value ?p4) 0)
        )
        :effect (and
            (not (shiftstatus ?r1)) (shiftstatus ?r2)
            (assign (value ?p2) (value ?p3))
            (assign (value ?p3) (value ?p4))
            (assign (value ?p4) 0)
        )
    )

    ; X X _ X  ->  X X X _
    (:action shift-1101
        :parameters (?p1 ?p2 ?p3 ?p4 - pos ?r1 ?r2 - status ?d - direction)
        :precondition (and
            (shifting ?d) (shiftstatus ?r1) (next ?d ?r1 ?r2)
            (pos-at ?d ?r1 i1 ?p1) (pos-at ?d ?r1 i2 ?p2)
            (pos-at ?d ?r1 i3 ?p3) (pos-at ?d ?r1 i4 ?p4)
            (> (value ?p1) 0) (> (value ?p2) 0) (= (value ?p3) 0) (> (value ?p4) 0)
        )
        :effect (and
            (not (shiftstatus ?r1)) (shiftstatus ?r2)
            (assign (value ?p3) (value ?p4))
            (assign (value ?p4) 0)
        )
    )

    ;; ============================================================
    ;; Shift finish
    ;;
    ;; Two variants distinguished by the phase table:
    ;;   (F,T) -> shift-finish-to-combine -> (T,T)  first shift done
    ;;   (F,F) -> shift-finish            -> (T,F)  second shift done
    ;; ============================================================

    (:action shift-finish-to-combine
        :parameters (?d - direction ?s - status)
        :precondition (and
            (shifting ?d)
            (shiftstatus done)
            (must-combine)
            (start-status ?d ?s)
        )
        :effect (and
            (not (shifting ?d))
            (not (shiftstatus done))
            (free-to-play)
            (combining ?d)
            (shiftstatus ?s)
            (combine-at i1)
        )
    )

    (:action shift-finish
        :parameters (?d - direction)
        :precondition (and
            (shifting ?d)
            (shiftstatus done)
            (not (must-combine))
        )
        :effect (and
            (not (shifting ?d))
            (not (shiftstatus done))
            (free-to-play)
        )
    )

    ;; ============================================================
    ;; Combine phase
    ;;
    ;; Iterates pair-by-pair through each row/col using combine-at
    ;; to track the current pair start index (i1..i3). Two action
    ;; variants: match (merge) and no-match (advance only).
    ;; Merging 0==0 is a harmless no-op (2*0=0).
    ;; ============================================================

    (:action combine-match
        :parameters (?d - direction ?r - status ?ia ?ib - idx ?pa ?pb - pos)
        :precondition (and
            (combining ?d)
            (shiftstatus ?r)
            (combine-at ?ia)
            (next-idx ?ia ?ib)
            (pos-at ?d ?r ?ia ?pa)
            (pos-at ?d ?r ?ib ?pb)
            (= (value ?pa) (value ?pb))
        )
        :effect (and
            (not (combine-at ?ia))
            (combine-at ?ib)
            (assign (value ?pa) (* 2 (value ?pa)))
            (assign (value ?pb) 0)
        )
    )

    (:action combine-no-match
        :parameters (?d - direction ?r - status ?ia ?ib - idx ?pa ?pb - pos)
        :precondition (and
            (combining ?d)
            (shiftstatus ?r)
            (combine-at ?ia)
            (next-idx ?ia ?ib)
            (pos-at ?d ?r ?ia ?pa)
            (pos-at ?d ?r ?ib ?pb)
            (not (= (value ?pa) (value ?pb)))
        )
        :effect (and
            (not (combine-at ?ia))
            (combine-at ?ib)
        )
    )

    ; Advance to the next row/col; reset pair index to i1.
    (:action combine-row-advance
        :parameters (?d - direction ?r1 ?r2 - status)
        :precondition (and
            (combining ?d)
            (shiftstatus ?r1)
            (next ?d ?r1 ?r2)
            (combine-at i4)
        )
        :effect (and
            (not (shiftstatus ?r1))
            (shiftstatus ?r2)
            (not (combine-at i4))
            (combine-at i1)
        )
    )

    ; All rows/cols processed. Transition (T,T) -> (F,F): start second shift.
    (:action combine-finish
        :parameters (?d - direction ?s - status)
        :precondition (and
            (combining ?d)
            (shiftstatus done)
            (combine-at i1)
            (start-status ?d ?s)
        )
        :effect (and
            (not (combining ?d))
            (not (combine-at i1))
            (not (shiftstatus done))
            (not (free-to-play))
            (not (must-combine))
            (shifting ?d)
            (shiftstatus ?s)
        )
    )

)
