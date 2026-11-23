;; Source: domain.pddl distributed with the temporal plant watering instance generator (copied verbatim).
;; Joan Espasa Arxer (jea20@st-andrews.ac.uk)
;; Based on the Plant Watering domain originally created by
;; Guillem Franc`es (guillem.frances@upf.edu) and Hector Geffner (hector.geffner@upf.edu)
;; and adapted to numeric planning by Enrico Scala (enricos83@gmail.com) and Miquel Ramirez (miquel.ramirez@gmail.com)
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Extended Plant Watering
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;;; A set of agents on a map aims to water some plants by
;;; carrying water from a central reservoir to the plants.
;;; All agents can move along the eigth compass directions, and have specific
;;; actions to load the water and pouring the plants. This version adds a
;;; contraint over the total amount of water and the maximum amount of water
;;; that can be carried by an agent
;;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

(define (domain temporal-plant-watering)
    (:requirements :typing :fluents :numeric-fluents :durative-actions :duration-inequalities)
    (:types agent plant pump)

    (:predicates
        (pump_opened ?t - pump)
        (pump_closed ?t - pump)
        (free ?t - pump)
        (used ?t - pump)
        (has ?a - agent ?t - pump)
        (handfree ?a - agent)
    )

    (:functions
        ;; constant bounds
        (maxx)
        (maxy)
        (miny)
        (minx)
        (water_reserve) ;; The total amount of water we have

        ;; fluents
        (x ?a - agent) ;; x coordinate of the location for ?t
        (y ?a - agent) ;; y coordinate of the location for ?t
        (plant_x ?p - plant) ;; x coordinate of the location for ?t
        (plant_y ?p - plant) ;; y coordinate of the location for ?t
        (tap_x ?t - pump) ;; x coordinate of the location for ?t
        (tap_y ?t - pump) ;; y coordinate of the location for ?t
        (poured ?p - plant) ;; The amount of water poured to the plant so far.
    )

    ;; Move an agent to a neighboring location
    (:action move_up
     :parameters (?a - agent)
     :precondition (and (<= (+ (y ?a) 1) (maxy)) (handfree ?a))
     :effect (and
    		(increase (y ?a) 1)))

    (:action move_down
     :parameters (?a - agent)
     :precondition (and (>= (- (y ?a) 1) (miny)) (handfree ?a))
     :effect (and
    		(decrease (y ?a) 1)))

    (:action move_right
     :parameters (?a - agent)
     :precondition (and (<= (+ (x ?a) 1) (maxx)) (handfree ?a))
     :effect (and
    		(increase (x ?a) 1)))

    (:action move_left
     :parameters (?a - agent)
     :precondition (and (>= (- (x ?a) 1) (minx)) (handfree ?a))
     :effect (and
    		(decrease (x ?a) 1)))

    ;; Move an agent to a neighboring location while carrying a closed pump
    (:action move_up_with_pump
     :parameters (?a - agent ?t - pump)
     :precondition (and (<= (+ (y ?a) 1) (maxy)) (has ?a ?t) (pump_closed ?t))
     :effect (and
    		(increase (y ?a) 1)))

    (:action move_down_with_pump
     :parameters (?a - agent ?t - pump)
     :precondition (and (>= (- (y ?a) 1) (miny)) (has ?a ?t) (pump_closed ?t))
     :effect (and
    		(decrease (y ?a) 1)))

    (:action move_right_with_pump
     :parameters (?a - agent ?t - pump)
     :precondition (and (<= (+ (x ?a) 1) (maxx)) (has ?a ?t) (pump_closed ?t))
     :effect (and
    		(increase (x ?a) 1)))

    (:action move_left_with_pump
     :parameters (?a - agent ?t - pump)
     :precondition (and (>= (- (x ?a) 1) (minx)) (has ?a ?t) (pump_closed ?t))
     :effect (and
    		(decrease (x ?a) 1)))

    ;; move diagonals
    ; (:action move_up_left
    ;  :parameters (?a - agent)
    ;  :precondition (and (>= (- (x ?a) 1) (minx)) (<= (+ (y ?a) 1) (maxy)) (handfree ?a))
    ;  :effect (and
    ;     (increase (y ?a) 1) (decrease (x ?a) 1)))

    ; (:action move_up_right
    ;  :parameters (?a - agent)
    ;  :precondition (and (<= (+ (x ?a) 1) (maxx)) (<= (+ (y ?a) 1) (maxy)) (handfree ?a))
    ;  :effect (and
    ;     (increase (y ?a) 1) (increase (x ?a) 1)))

    ; (:action move_down_left
    ;  :parameters (?a - agent)
    ;  :precondition (and (>= (- (x ?a) 1) (minx)) (>= (- (y ?a) 1) (miny)) (handfree ?a))
    ;  :effect (and
    ;     (decrease (x ?a) 1) (decrease (y ?a) 1) )
    ; )

    ; (:action move_down_right
    ;  :parameters (?a - agent)
    ;  :precondition (and (<= (+ (x ?a) 1) (maxx)) (>= (- (y ?a) 1) (miny)) (handfree ?a))
    ;  :effect (and
    ;     (decrease (y ?a) 1) (increase (x ?a) 1)))

    ;; Take the water pump
    (:action take_pump
        :parameters (?a - agent ?t - pump)
        :precondition (and (= (x ?a) (tap_x ?t)) (=(y ?a) (tap_y ?t)) (handfree ?a) (free ?t))
        :effect (and (not (free ?t)) (used ?t) (has ?a ?t) (not (handfree ?a)))
    )

    ;; Drop the water pump
    (:action drop_pump
        :parameters (?a - agent ?t - pump)
        :precondition (and (= (x ?a) (tap_x ?t)) (=(y ?a) (tap_y ?t)) (has ?a ?t))
        :effect (and (free ?t) (not (used ?t)) (not (has ?a ?t)) (handfree ?a))
    )

    ;; Open the water pump
    (:durative-action open_water_pump
    :parameters (?a - agent ?t - pump)
    :duration (= ?duration 10)
    :condition (and (at start
                       (and (= (x ?a) (tap_x ?t)) (=(y ?a) (tap_y ?t)) (handfree ?a) (used ?t))
                    )
                ) ; we are on the tap
    :effect (and
                (at start (and (pump_opened ?t) (not (pump_closed ?t)) (not (handfree ?a))))
                (at end (and (not (pump_opened ?t)) (pump_closed ?t) (handfree ?a)))
            ))

    ;; Pours one unit of water
    (:action pour
    :parameters (?a - agent ?t - pump ?p - plant)
    :precondition (and (= (x ?a) (plant_x ?p)) (=(y ?a) (plant_y ?p)) (has ?a ?t) (pump_opened ?t) (> (water_reserve) 0)) ; we are on the plant and the pump is opened
    :effect       (and
                    (decrease (water_reserve) 1)
                    (increase (poured ?p) 1)))
)
