;; Space Rescue, classical variant
;; Derived from the IPC-2026 expedition domain by Joan Espasa Arxer, itself based
;; on the expedition domain by Ben Pathak.
;;
;; Rovers drive on a graph of sites, and every drive drains one battery pack.
;; Packs lie on sites and are picked up or dropped in amounts: objects whose
;; value is a power of two. A charging station fills a rover to capacity and
;; never runs out.
;;
;; The same as space_rescue_v1.pddl with every number of packs an object of
;; type count, n0, n1, ... up to the most packs a site can hold. Static facts
;; do the arithmetic: (next ?a ?b) says b = a + 1, (sum ?a ?q ?b) says
;; b = a + the value of amount q, and (leq ?a ?b) says a <= b, given up to the
;; rovers' capacity, the only place it is used. Every action keeps the
;; parameters it has there and adds counts after them, so a plan here is a plan
;; there once the counts are removed.

(define (domain space-rescue-classical)
  (:requirements :typing :negative-preconditions :equality)
  (:types rover site amount count)

  (:predicates
    (at ?r - rover ?s - site)
    (connected ?a - site ?b - site)
    (charging_station ?s - site)
    (rover_packs ?r - rover ?n - count)
    (rover_capacity ?r - rover ?n - count)
    (site_packs ?s - site ?n - count)
    (next ?a - count ?b - count)
    (sum ?a - count ?q - amount ?b - count)
    (leq ?a - count ?b - count))

  ;; Drive along an edge; drains one pack (n = m + 1).
  (:action drive
    :parameters (?r - rover ?from - site ?to - site ?n - count ?m - count)
    :precondition (and (at ?r ?from)
                       (connected ?from ?to)
                       (rover_packs ?r ?n)
                       (next ?m ?n))
    :effect (and (not (at ?r ?from))
                 (at ?r ?to)
                 (not (rover_packs ?r ?n))
                 (rover_packs ?r ?m)))

  ;; Pick up an amount of packs from the site, up to the rover's capacity
  ;; (site: sn = sm + q; rover: rm = rn + q <= c).
  (:action pick_up
    :parameters (?r - rover ?s - site ?q - amount
                 ?sn - count ?sm - count ?rn - count ?rm - count ?c - count)
    :precondition (and (at ?r ?s)
                       (site_packs ?s ?sn)
                       (sum ?sm ?q ?sn)
                       (rover_packs ?r ?rn)
                       (sum ?rn ?q ?rm)
                       (rover_capacity ?r ?c)
                       (leq ?rm ?c))
    :effect (and (not (site_packs ?s ?sn))
                 (site_packs ?s ?sm)
                 (not (rover_packs ?r ?rn))
                 (rover_packs ?r ?rm)))

  ;; Drop an amount of packs on the site, if the site can hold them (rover:
  ;; rn = rm + q; site: sm = sn + q). Not at a charging station: it would be
  ;; pointless there.
  (:action drop
    :parameters (?r - rover ?s - site ?q - amount
                 ?rn - count ?rm - count ?sn - count ?sm - count)
    :precondition (and (at ?r ?s)
                       (not (charging_station ?s))
                       (rover_packs ?r ?rn)
                       (sum ?rm ?q ?rn)
                       (site_packs ?s ?sn)
                       (sum ?sn ?q ?sm))
    :effect (and (not (rover_packs ?r ?rn))
                 (rover_packs ?r ?rm)
                 (not (site_packs ?s ?sn))
                 (site_packs ?s ?sm)))

  ;; Charge to capacity at a charging station, which never runs out (n < c).
  (:action recharge
    :parameters (?r - rover ?s - site ?n - count ?c - count)
    :precondition (and (at ?r ?s)
                       (charging_station ?s)
                       (rover_packs ?r ?n)
                       (rover_capacity ?r ?c)
                       (leq ?n ?c)
                       (not (= ?n ?c)))
    :effect (and (not (rover_packs ?r ?n))
                 (rover_packs ?r ?c)))
)
