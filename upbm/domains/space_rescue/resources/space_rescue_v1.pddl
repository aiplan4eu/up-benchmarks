;; Space Rescue
;; Derived from the IPC-2026 expedition domain by Joan Espasa Arxer, itself based
;; on the expedition domain by Ben Pathak.
;;
;; Rovers drive on a graph of sites, and every drive drains one battery pack.
;; Packs lie on sites and are picked up or dropped in amounts: objects whose
;; value is a power of two. A charging station fills a rover to capacity and
;; never runs out.

(define (domain space-rescue)
  (:requirements :typing :fluents :negative-preconditions)
  (:types rover site amount)

  (:predicates
    (at ?r - rover ?s - site)
    (connected ?a - site ?b - site)
    (charging_station ?s - site))

  (:functions
    (rover_packs ?r - rover)
    (rover_capacity ?r - rover)
    (site_packs ?s - site)
    (value ?q - amount))

  ;; Drive along an edge; drains one pack.
  (:action drive
    :parameters (?r - rover ?from - site ?to - site)
    :precondition (and (at ?r ?from)
                       (connected ?from ?to)
                       (>= (rover_packs ?r) 1))
    :effect (and (not (at ?r ?from))
                 (at ?r ?to)
                 (decrease (rover_packs ?r) 1)))

  ;; Pick up an amount of packs from the site, up to the rover's capacity.
  (:action pick_up
    :parameters (?r - rover ?s - site ?q - amount)
    :precondition (and (at ?r ?s)
                       (>= (site_packs ?s) (value ?q))
                       (<= (+ (rover_packs ?r) (value ?q)) (rover_capacity ?r)))
    :effect (and (decrease (site_packs ?s) (value ?q))
                 (increase (rover_packs ?r) (value ?q))))

  ;; Drop an amount of packs on the site. Not at a charging station: it would be
  ;; pointless there, and it would let the packs left there grow without bound.
  (:action drop
    :parameters (?r - rover ?s - site ?q - amount)
    :precondition (and (at ?r ?s)
                       (not (charging_station ?s))
                       (>= (rover_packs ?r) (value ?q)))
    :effect (and (increase (site_packs ?s) (value ?q))
                 (decrease (rover_packs ?r) (value ?q))))

  ;; Charge to capacity at a charging station, which never runs out.
  (:action recharge
    :parameters (?r - rover ?s - site)
    :precondition (and (at ?r ?s)
                       (charging_station ?s)
                       (< (rover_packs ?r) (rover_capacity ?r)))
    :effect (assign (rover_packs ?r) (rover_capacity ?r)))
)
