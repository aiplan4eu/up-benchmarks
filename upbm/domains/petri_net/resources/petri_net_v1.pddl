;; Source: IPC 2026 dataset, petri-net/domain.pddl (copied verbatim)
;;Anonymous
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;;; petri nets (max hyper edges are of size 4)
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

(define (domain petri-net)
    (:requirements :strips :typing :numeric-fluents)
    (:types place)

  (:predicates  (source ?p - place)
                (one-to-one ?p1 ?p2 - place)
                (one-to-two ?p1 ?p2 ?p3 - place)
		 (two-to-one ?p1 ?p2 ?p3 - place)
		 (three-to-one ?p1 ?p2 ?p3 ?p4 - place)
		 (two-to-two ?p1 ?p2 ?p3 ?p4 - place)
		 (one-to-three ?p1 ?p2 ?p3 ?p4 - place)
                (sink ?p - place)
   )
    (:functions
        (value ?p - place) ;; The value shown in counter ?c
        (cost) ;; cost function
    )

    ;; Generates a tocken in a source
    (:action create
         :parameters (?p - place)
         :precondition (and (source ?p))
         :effect (and (increase (value ?p)  1)
                      (increase (cost) 1))
    )
    
    ;; Destroys a tocken in a sink
    (:action increment
         :parameters (?p - place)
         :precondition (and (sink ?p)
                            (> (value ?p) 0))
         :effect (and (decrease (value ?p)  1)
                      (increase (cost) 1))
    )

    ;; fire one to oтe connection
    (:action fire-one-to-one
         :parameters (?p1 ?p2 - place)
         :precondition (and (one-to-one ?p1 ?p2)
                            (> (value ?p1) 0))
         :effect (and (decrease (value ?p1) 1)
                      (increase (value ?p2) 1)
                      (increase (cost) 1))
    )
    
    ;; fire one to two connection
    (:action fire-one-to-two
         :parameters (?p1 ?p2 ?p3 - place)
         :precondition (and (one-to-two ?p1 ?p2 ?p3)
                            (> (value ?p1) 0))
         :effect (and (decrease (value ?p1) 1)
                      (increase (value ?p2) 1)
                      (increase (value ?p3) 1)
                      (increase (cost) 1))
    )
    
    ;; fire two to one connection
    (:action fire-two-to-one
         :parameters (?p1 ?p2 ?p3 - place)
         :precondition (and (two-to-one ?p1 ?p2 ?p3)
                            (> (value ?p1) 0)
                            (> (value ?p2) 0))
         :effect (and (decrease (value ?p1) 1)
                      (decrease (value ?p2) 1)
                      (increase (value ?p3) 1)
                      (increase (cost) 1))
    )
    
    ;;fire three to one connection
    (:action fire-three-to-one
         :parameters (?p1 ?p2 ?p3 ?p4 - place)
         :precondition (and (three-to-one ?p1 ?p2 ?p3 ?p4)
                            (> (value ?p1) 0)
                            (> (value ?p2) 0)
                            (> (value ?p3) 0))
         :effect (and (decrease (value ?p1) 1)
                      (decrease (value ?p2) 1)
                      (decrease (value ?p3) 1)
                      (increase (value ?p4) 1)
                      (increase (cost) 1))
    )
    
    ;;fire three to one connection
    (:action fire-two-to-two
         :parameters (?p1 ?p2 ?p3 ?p4 - place)
         :precondition (and (two-to-two ?p1 ?p2 ?p3 ?p4)
                            (> (value ?p1) 0)
                            (> (value ?p2) 0))
         :effect (and (decrease (value ?p1) 1)
                      (decrease (value ?p2) 1)
                      (increase (value ?p3) 1)
                      (increase (value ?p4) 1)
                      (increase (cost) 1))
    )
    
    ;;fire three to one connection
    (:action fire-one-to-three
         :parameters (?p1 ?p2 ?p3 ?p4 - place)
         :precondition (and (one-to-three ?p1 ?p2 ?p3 ?p4)
                            (> (value ?p1) 0))
         :effect (and (decrease (value ?p1) 1)
                      (increase (value ?p2) 1)
                      (increase (value ?p3) 1)
                      (increase (value ?p4) 1)
                      (increase (cost) 1))
    )
)
