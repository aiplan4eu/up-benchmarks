;;; Source: IPC 2026 dataset, rainbowttles-opt/domain.pddl (copied verbatim).
;;; The rainbowttles-sat folder ships the same domain, differing only by one
;;; extra ";;;" comment line.
;;;
;;; Constant-free compilation of the Rainbowttles domain.
;;;
;;; The original domain used the domain constant `empty`.  This version does
;;; not name any object in the domain.  Problems must provide one colour object
;;; marked with (empty-colour ?e), and mark the playable colours with
;;; (real-colour ?c).
;;;
;;; Author: Alba Gragera
;;;

(define (domain rainbowttles-constant-free)
  (:requirements :typing :action-costs :negative-preconditions :numeric-fluents :equality)

  (:types
      bottle colour - object
  )

  (:predicates
    (upper-colour ?b - bottle ?c - colour)
    (colour-below ?b - bottle ?c - colour ?c1 - colour)
    (closed ?b - bottle)
    (empty-colour ?c - colour)
    (real-colour ?c - colour)
  )

  (:functions
    (bottle-capacity ?b - bottle)
    (segments-filled ?b - bottle)
    (colour-segments ?b - bottle ?c - colour)
  )

  (:action pour
    :parameters (?b - bottle ?c ?c1 - colour ?b1 - bottle)
    :precondition (and
      (real-colour ?c)

      ; First bottle
      (not (closed ?b))
      (> (colour-segments ?b ?c) 0)
      (> (segments-filled ?b) 0)
      (upper-colour ?b ?c)
      (colour-below ?b ?c ?c1)

      ; Second bottle
      (not (closed ?b1))
      (> (colour-segments ?b1 ?c) 0)
      (> (segments-filled ?b1) 0)
      (upper-colour ?b1 ?c)
      (<= (+ (segments-filled ?b1) (colour-segments ?b ?c)) (bottle-capacity ?b1))

      (not (= ?b ?b1))
    )
    :effect (and
      ; First bottle
      (decrease (segments-filled ?b) (colour-segments ?b ?c))
      (not (upper-colour ?b ?c))
      (upper-colour ?b ?c1)
      (assign (colour-segments ?b ?c) 0)

      ; Second bottle
      (increase (segments-filled ?b1) (colour-segments ?b ?c))
      (increase (colour-segments ?b1 ?c) (colour-segments ?b ?c))
    )
  )

  (:action pour-to-empty-bottle
    :parameters (?b - bottle ?c ?c1 ?e - colour ?b1 - bottle)
    :precondition (and
      (real-colour ?c)
      (empty-colour ?e)

      ; First bottle
      (not (closed ?b))
      (> (colour-segments ?b ?c) 0)
      (> (segments-filled ?b) 0)
      (upper-colour ?b ?c)
      (colour-below ?b ?c ?c1)

      ; Second bottle
      (not (closed ?b1))
      (= (colour-segments ?b1 ?c) 0)
      (= (segments-filled ?b1) 0)
      (upper-colour ?b1 ?e)
      (<= (colour-segments ?b ?c) (bottle-capacity ?b1))

      (not (= ?b ?b1))
    )
    :effect (and
      ; First bottle
      (decrease (segments-filled ?b) (colour-segments ?b ?c))
      (not (upper-colour ?b ?c))
      (upper-colour ?b ?c1)
      (assign (colour-segments ?b ?c) 0)

      ; Second bottle
      (increase (segments-filled ?b1) (colour-segments ?b ?c))
      (increase (colour-segments ?b1 ?c) (colour-segments ?b ?c))
      (not (upper-colour ?b1 ?e))
      (upper-colour ?b1 ?c)
      (colour-below ?b1 ?c ?e)
    )
  )

  (:action close-bottle
    :parameters (?b - bottle ?c - colour)
    :precondition (and
      (real-colour ?c)
      (= (colour-segments ?b ?c) (bottle-capacity ?b))
    )
    :effect (and
      (closed ?b)
    )
  )

  (:action close-empty-bottle
    :parameters (?b - bottle)
    :precondition (and
      (= (segments-filled ?b) 0)
    )
    :effect (and
      (closed ?b)
    )
  )
)
