;; Source: IPC 2026 dataset, factory-robot/domain.pddl (copied verbatim)
;; Factory Robot Domain
;; -------------------- 
;; Authored by Joan Espasa Arxer
;;
;; A team of robots works in a factory with specialized stations. Each robot
;; has an energy reserve, accumulates workload (completed tasks), generates
;; heat while working, and can switch between production modes.
;;
;; Robots move between stations along a connected network. Each station can
;; hold at most one robot at a time. Stations have specialized equipment:
;;   - Charging stations: have chargers for energy recharge
;;   - Cooling stations: have coolers for temperature reduction and
;;     calibration equipment for post-turbo recalibration
;;   - Assembly stations: general-purpose work areas
;;
;; Each robot has fixed characteristics (capacity, work-cost, max-temp,
;; efficiency) that vary per unit. Working consumes energy and generates
;; heat; robots must manage their energy by visiting charging stations and
;; their temperature by visiting cooling stations. Production mode
;; (low/medium/high/turbo) controls the output rate for bulk work. After
;; turbo-work, robots must recalibrate at a calibration station before
;; performing regular or precision work.
;;
;; The objective is to reach a target workload for each robot while keeping
;; temperatures within safe limits.
;;
;; Numeric grounding features exercised:
;;   1. Ceiling freezing — energy assigned to constant capacity
;;   2. Floor freezing — workload only increases
;;   3. Multi-assign freezing — production set to 4 constant values
;;   4. Directional widening — temperature both increases and decreases
;;   5. Pruning via frozen ceiling — overcharge needs energy > capacity
;;   6. Pruning via frozen multi-assign — overdrive needs production > max mode
;;   7. Constant fluent references — work-cost, cooling-power in effects
;;   8. Interval arithmetic — workload * efficiency in preconditions
;;   9. Numeric goal checking — goals on workload and temperature

(define (domain factory-robot)

  (:requirements :typing :numeric-fluents :negative-preconditions)
  (:types robot station - object)

  (:predicates
    (at ?r - robot ?s - station)
    (connected ?s1 - station ?s2 - station)
    (has-charger ?s - station)       ; Station has charging equipment
    (has-calibrator ?s - station)    ; Station has calibration equipment
    (free ?s - station)              ; Station is unoccupied (mutual exclusion)
    (calibrated ?r - robot)          ; Robot is calibrated (cleared by turbo-work)
  )

  (:functions
    ;; Robot state (modified by actions)
    (energy ?r - robot)          ; Current energy level
    (workload ?r - robot)        ; Accumulated completed tasks
    (temperature ?r - robot)     ; Current heat level
    (production ?r - robot)      ; Current production mode setting

    ;; Robot characteristics (constant — never modified)
    (capacity ?r - robot)        ; Maximum energy after recharge
    (work-cost ?r - robot)       ; Energy consumed per work action
    (max-temp ?r - robot)        ; Maximum safe operating temperature
    (efficiency ?r - robot)      ; Energy-per-workload ratio for precision work

    ;; Station characteristics (constant — never modified)
    (cooling-power ?s - station) ; Temperature reduction per cool-down
  )

  ;; Recharge energy to full capacity. Requires a charging station.
  (:action recharge
    :parameters (?r - robot ?s - station)
    :precondition (and
      (at ?r ?s)
      (has-charger ?s)
    )
    :effect (and (assign (energy ?r) (capacity ?r)))
  )

  ;; Perform a standard work task. Consumes energy, produces heat.
  ;; Requires calibration (cleared by turbo-work).
  (:action work
    :parameters (?r - robot ?s - station)
    :precondition (and
      (at ?r ?s)
      (calibrated ?r)
      (>= (energy ?r) (work-cost ?r))
      (<= (temperature ?r) (max-temp ?r))
    )
    :effect (and
      (decrease (energy ?r) (work-cost ?r))
      (increase (workload ?r) 1)
      (increase (temperature ?r) 3)
    )
  )

  ;; Cool down at a station with cooling capability.
  (:action cool-down
    :parameters (?r - robot ?s - station)
    :precondition (and
      (at ?r ?s)
      (>= (temperature ?r) 1)
    )
    :effect (and
      (decrease (temperature ?r) (cooling-power ?s))
    )
  )

  ;; Set production mode — four discrete levels.
  (:action set-low-power
    :parameters (?r - robot)
    :effect (and (assign (production ?r) 10))
  )

  (:action set-medium-power
    :parameters (?r - robot)
    :effect (and (assign (production ?r) 50))
  )

  (:action set-high-power
    :parameters (?r - robot)
    :effect (and (assign (production ?r) 100))
  )

  (:action set-turbo
    :parameters (?r - robot)
    :effect (and (assign (production ?r) 200))
  )

  ;; Overdrive — requires impossible production level (always pruned).
  (:action overdrive
    :parameters (?r - robot)
    :precondition (and (>= (production ?r) 250))
    :effect (and (increase (workload ?r) 100))
  )

  ;; Overcharge — requires impossible energy level (always pruned).
  (:action overcharge
    :parameters (?r - robot)
    :precondition (and (>= (energy ?r) 200))
    :effect (and (increase (workload ?r) 50))
  )

  ;; Precision work — energy cost scales with accumulated workload.
  ;; Requires calibration (cleared by turbo-work).
  (:action precision-work
    :parameters (?r - robot ?s - station)
    :precondition (and
      (at ?r ?s)
      (calibrated ?r)
      (>= (energy ?r) (* (workload ?r) (efficiency ?r)))
      (<= (temperature ?r) (max-temp ?r))
    )
    :effect (and
      (decrease (energy ?r) (work-cost ?r))
      (increase (workload ?r) 5)
      (increase (temperature ?r) 1)
    )
  )

  ;; Move between connected stations. Target station must be unoccupied.
  (:action move
    :parameters (?r - robot ?s1 - station ?s2 - station)
    :precondition (and
      (at ?r ?s1)
      (connected ?s1 ?s2)
      (free ?s2)
      (>= (energy ?r) 5)
    )
    :effect (and
      (not (at ?r ?s1))
      (at ?r ?s2)
      (free ?s1)
      (not (free ?s2))
      (decrease (energy ?r) 5)
    )
  )

  ;; Turbo work — high output but requires turbo production mode.
  ;; Decalibrates the robot, requiring recalibration before regular work.
  (:action turbo-work
    :parameters (?r - robot ?s - station)
    :precondition (and
      (at ?r ?s)
      (>= (production ?r) 150)
      (>= (energy ?r) 20)
    )
    :effect (and
      (decrease (energy ?r) 20)
      (increase (workload ?r) 10)
      (increase (temperature ?r) 5)
      (not (calibrated ?r))
    )
  )

  ;; Recalibrate after turbo-work. Requires a calibration station.
  (:action calibrate
    :parameters (?r - robot ?s - station)
    :precondition (and
      (at ?r ?s)
      (has-calibrator ?s)
      (not (calibrated ?r))
    )
    :effect (and
      (calibrated ?r)
    )
  )
)
