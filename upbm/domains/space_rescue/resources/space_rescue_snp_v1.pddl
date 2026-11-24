;; Space Rescue, simple numeric variant
;; Derived from the IPC-2026 expedition domain by Joan Espasa Arxer, itself based
;; on the expedition domain by Ben Pathak.
;;
;; Rovers drive on a graph of sites, and every drive drains one battery pack.
;; Packs lie on sites and are picked up or dropped, 1 or 3 at a time. A charging
;; station never runs out and charges 1 or 3 packs at a time, up to capacity.
;;
;; The same as space_rescue_v1.pddl, except that packs move only 1 or 3 at a
;; time, with one action for each, instead of in amounts whose value is a static
;; fluent, and that recharge adds packs instead of filling the rover. Every
;; numeric effect then adds or subtracts a literal number, which makes the
;; domain simple numeric. Capacities are at least 3, so a rover can always
;; recharge 3 packs from empty.

(define (domain space-rescue-snp)
  (:requirements :typing :fluents :negative-preconditions)
  (:types rover site)

  (:predicates
    (at ?r - rover ?s - site)
    (connected ?a - site ?b - site)
    (charging_station ?s - site))

  (:functions
    (rover_packs ?r - rover)
    (rover_capacity ?r - rover)
    (site_packs ?s - site))

  ;; Drive along an edge; drains one pack.
  (:action drive
    :parameters (?r - rover ?from - site ?to - site)
    :precondition (and (at ?r ?from)
                       (connected ?from ?to)
                       (>= (rover_packs ?r) 1))
    :effect (and (not (at ?r ?from))
                 (at ?r ?to)
                 (decrease (rover_packs ?r) 1)))

  ;; Pick up 1 (or 3) packs from the site, up to the rover's capacity.
  (:action pick_up_1
    :parameters (?r - rover ?s - site)
    :precondition (and (at ?r ?s)
                       (>= (site_packs ?s) 1)
                       (<= (+ (rover_packs ?r) 1) (rover_capacity ?r)))
    :effect (and (decrease (site_packs ?s) 1)
                 (increase (rover_packs ?r) 1)))

  (:action pick_up_3
    :parameters (?r - rover ?s - site)
    :precondition (and (at ?r ?s)
                       (>= (site_packs ?s) 3)
                       (<= (+ (rover_packs ?r) 3) (rover_capacity ?r)))
    :effect (and (decrease (site_packs ?s) 3)
                 (increase (rover_packs ?r) 3)))

  ;; Drop 1 (or 3) packs on the site. Not at a charging station: it would be
  ;; pointless there, and it would let the packs left there grow without bound.
  (:action drop_1
    :parameters (?r - rover ?s - site)
    :precondition (and (at ?r ?s)
                       (not (charging_station ?s))
                       (>= (rover_packs ?r) 1))
    :effect (and (increase (site_packs ?s) 1)
                 (decrease (rover_packs ?r) 1)))

  (:action drop_3
    :parameters (?r - rover ?s - site)
    :precondition (and (at ?r ?s)
                       (not (charging_station ?s))
                       (>= (rover_packs ?r) 3))
    :effect (and (increase (site_packs ?s) 3)
                 (decrease (rover_packs ?r) 3)))

  ;; Charge 1 (or 3) packs at a charging station, which never runs out, up to
  ;; the rover's capacity.
  (:action recharge_1
    :parameters (?r - rover ?s - site)
    :precondition (and (at ?r ?s)
                       (charging_station ?s)
                       (<= (+ (rover_packs ?r) 1) (rover_capacity ?r)))
    :effect (increase (rover_packs ?r) 1))

  (:action recharge_3
    :parameters (?r - rover ?s - site)
    :precondition (and (at ?r ?s)
                       (charging_station ?s)
                       (<= (+ (rover_packs ?r) 3) (rover_capacity ?r)))
    :effect (increase (rover_packs ?r) 3))
)
