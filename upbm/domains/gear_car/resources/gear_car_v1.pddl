;; Source: ipc2026-dataset/gear-car/domain.pddl (IPC 2026), copied verbatim.
(define (domain car_linear_gears_numeric)

    (:requirements :strips :typing :numeric-fluents)

    (:types
        gear
    )

    (:predicates
        (current_gear ?g - gear)
        (gear_next ?lower ?higher - gear)
    )

    (:functions
        (d)
        (v)
        (a)

        (max_acceleration)
        (min_acceleration)
        (max_speed)
        (acc_step)

        (fuel)
        (fuel_used)
        (elapsed_time)
        (cost)
        (alpha)
        (beta)

        (shift_count)

        (gear_v_min ?g - gear)
        (gear_v_max ?g - gear)
        (gear_min_acceleration ?g - gear)
        (gear_max_acceleration ?g - gear)

        (gear_fuel_aligned ?g - gear)
        (gear_fuel_under ?g - gear)
        (gear_fuel_over ?g - gear)
    )

    (:action accelerate
        :parameters (?g - gear)
        :precondition (and
            (current_gear ?g)
            (>= (v) 0)
            (<= (v) (max_speed))
            (>= (fuel) 0)
            (>= (a) (min_acceleration))
            (<= (a) (max_acceleration))
            (<= (+ (a) (acc_step)) (max_acceleration))
            (>= (a) (gear_min_acceleration ?g))
            (<= (a) (gear_max_acceleration ?g))
            (<= (+ (a) (acc_step)) (gear_max_acceleration ?g))
        )
        :effect (and
            (increase (a) (acc_step))
        )
    )

    (:action decelerate
        :parameters (?g - gear)
        :precondition (and
            (current_gear ?g)
            (>= (v) 0)
            (<= (v) (max_speed))
            (>= (fuel) 0)
            (>= (a) (min_acceleration))
            (<= (a) (max_acceleration))
            (>= (- (a) (acc_step)) (min_acceleration))
            (>= (a) (gear_min_acceleration ?g))
            (<= (a) (gear_max_acceleration ?g))
            (>= (- (a) (acc_step)) (gear_min_acceleration ?g))
        )
        :effect (and
            (decrease (a) (acc_step))
        )
    )

    (:action gear_up
        :parameters (?from ?to - gear)
        :precondition (and
            (current_gear ?from)
            (gear_next ?from ?to)
            (>= (v) 0)
            (<= (v) (max_speed))
            (>= (fuel) 0)
            (>= (a) (min_acceleration))
            (<= (a) (max_acceleration))
            (= (a) 0)
            (>= (a) (gear_min_acceleration ?to))
            (<= (a) (gear_max_acceleration ?to))
        )
        :effect (and
            (not (current_gear ?from))
            (current_gear ?to)
            (increase (shift_count) 1)
            (increase (cost) 1)
        )
    )

    (:action gear_down
        :parameters (?from ?to - gear)
        :precondition (and
            (current_gear ?from)
            (gear_next ?to ?from)
            (>= (v) 0)
            (<= (v) (max_speed))
            (>= (fuel) 0)
            (>= (a) (min_acceleration))
            (<= (a) (max_acceleration))
            (= (a) 0)
            (>= (a) (gear_min_acceleration ?to))
            (<= (a) (gear_max_acceleration ?to))
        )
        :effect (and
            (not (current_gear ?from))
            (current_gear ?to)
            (increase (shift_count) 1)
            (increase (cost) 1)
        )
    )

    (:action drive_aligned_gear
        :parameters (?g - gear)
        :precondition (and
            (current_gear ?g)
            (>= (v) 0)
            (<= (v) (max_speed))
            (>= (+ (v) (a)) 0)
            (<= (+ (v) (a)) (max_speed))
            (>= (fuel) 0)
            (>= (fuel) (gear_fuel_aligned ?g))
            (>= (a) (min_acceleration))
            (<= (a) (max_acceleration))
            (>= (a) (gear_min_acceleration ?g))
            (<= (a) (gear_max_acceleration ?g))
            (>= (v) (gear_v_min ?g))
            (<= (v) (gear_v_max ?g))
        )
        :effect (and
            (increase (d) (+ (* 2 (v)) (a)))
            (increase (v) (a))
            (decrease (fuel) (gear_fuel_aligned ?g))
            (increase (fuel_used) (gear_fuel_aligned ?g))
            (increase (elapsed_time) 1)
            (increase (cost) (+ (alpha) (* (beta) (gear_fuel_aligned ?g))))
        )
    )

    (:action drive_under_gear
        :parameters (?g - gear)
        :precondition (and
            (current_gear ?g)
            (>= (v) 0)
            (<= (v) (max_speed))
            (>= (+ (v) (a)) 0)
            (<= (+ (v) (a)) (max_speed))
            (>= (fuel) 0)
            (>= (fuel) (gear_fuel_under ?g))
            (>= (a) (min_acceleration))
            (<= (a) (max_acceleration))
            (>= (a) (gear_min_acceleration ?g))
            (<= (a) (gear_max_acceleration ?g))
            (< (v) (gear_v_min ?g))
        )
        :effect (and
            (increase (d) (+ (* 2 (v)) (a)))
            (increase (v) (a))
            (decrease (fuel) (gear_fuel_under ?g))
            (increase (fuel_used) (gear_fuel_under ?g))
            (increase (elapsed_time) 1)
            (increase (cost) (+ (alpha) (* (beta) (gear_fuel_under ?g))))
        )
    )

    (:action drive_over_gear
        :parameters (?g - gear)
        :precondition (and
            (current_gear ?g)
            (>= (v) 0)
            (<= (v) (max_speed))
            (>= (+ (v) (a)) 0)
            (<= (+ (v) (a)) (max_speed))
            (>= (fuel) 0)
            (>= (fuel) (gear_fuel_over ?g))
            (>= (a) (min_acceleration))
            (<= (a) (max_acceleration))
            (>= (a) (gear_min_acceleration ?g))
            (<= (a) (gear_max_acceleration ?g))
            (> (v) (gear_v_max ?g))
        )
        :effect (and
            (increase (d) (+ (* 2 (v)) (a)))
            (increase (v) (a))
            (decrease (fuel) (gear_fuel_over ?g))
            (increase (fuel_used) (gear_fuel_over ?g))
            (increase (elapsed_time) 1)
            (increase (cost) (+ (alpha) (* (beta) (gear_fuel_over ?g))))
        )
    )
)
