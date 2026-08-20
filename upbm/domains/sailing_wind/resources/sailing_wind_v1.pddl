;; Source: ipc2026-dataset/sailing-wind-{opt,sat}/domain.pddl (IPC 2026 dataset), unmodified.
;; The opt and sat variants of the dataset ship byte-identical domain files; they
;; differ only in the instances, so a single copy is kept here.


; Authors: Luigi Bonassi and Carl Hentges

(define (domain sailing-wind)

(:requirements :typing :numeric-fluents :disjunctive-preconditions)

(:types 
    boat - object
    person - object
)

(:predicates
    (saved ?t - person)
    
)

(:functions 
    (v ?b - boat)
	(x ?o - object)
	(y ?o - object)
	(r ?b - boat)
	(vmax_0 ?b - boat)
	(vmax_15 ?b - boat)
	(vmax_30 ?b - boat)
	(vmax_45 ?b - boat)
	(vmax_60 ?b - boat)
	(vmax_75 ?b - boat)
	(vmax_90 ?b - boat)
	(vmax_105 ?b - boat)
	(vmax_120 ?b - boat)
	(vmax_135 ?b - boat)
	(vmax_150 ?b - boat)
	(vmax_165 ?b - boat)
	(vmax_180 ?b - boat)
	(sailing-angle ?b - boat)
)

(:action move_0
	:parameters (?b - boat)
	:precondition (and (or (= (sailing-angle ?b) 345) (<= (sailing-angle ?b) 15)))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_0 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) 0.0))
		(increase (y ?b) (* (v ?b) 1.0))
		(assign (sailing-angle ?b) 0)))


(:action move_15
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 0) (<= (sailing-angle ?b) 30))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_15 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) 0.26))
		(increase (y ?b) (* (v ?b) 0.97))
		(assign (sailing-angle ?b) 15)))


(:action move_30
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 15) (<= (sailing-angle ?b) 45))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_30 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) 0.5))
		(increase (y ?b) (* (v ?b) 0.87))
		(assign (sailing-angle ?b) 30)))


(:action move_45
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 30) (<= (sailing-angle ?b) 60))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_45 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) 0.71))
		(increase (y ?b) (* (v ?b) 0.71))
		(assign (sailing-angle ?b) 45)))


(:action move_60
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 45) (<= (sailing-angle ?b) 75))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_60 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) 0.87))
		(increase (y ?b) (* (v ?b) 0.5))
		(assign (sailing-angle ?b) 60)))


(:action move_75
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 60) (<= (sailing-angle ?b) 90))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_75 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) 0.97))
		(increase (y ?b) (* (v ?b) 0.26))
		(assign (sailing-angle ?b) 75)))


(:action move_90
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 75) (<= (sailing-angle ?b) 105))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_90 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) 1.0))
		(increase (y ?b) (* (v ?b) 0.0))
		(assign (sailing-angle ?b) 90)))


(:action move_105
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 90) (<= (sailing-angle ?b) 120))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_105 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) 0.97))
		(increase (y ?b) (* (v ?b) -0.26))
		(assign (sailing-angle ?b) 105)))


(:action move_120
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 105) (<= (sailing-angle ?b) 135))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_120 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) 0.87))
		(increase (y ?b) (* (v ?b) -0.5))
		(assign (sailing-angle ?b) 120)))


(:action move_135
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 120) (<= (sailing-angle ?b) 150))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_135 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) 0.71))
		(increase (y ?b) (* (v ?b) -0.71))
		(assign (sailing-angle ?b) 135)))


(:action move_150
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 135) (<= (sailing-angle ?b) 165))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_150 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) 0.5))
		(increase (y ?b) (* (v ?b) -0.87))
		(assign (sailing-angle ?b) 150)))


(:action move_165
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 150) (<= (sailing-angle ?b) 180))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_165 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) 0.26))
		(increase (y ?b) (* (v ?b) -0.97))
		(assign (sailing-angle ?b) 165)))


(:action move_180
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 165) (<= (sailing-angle ?b) 195))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_180 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) 0.0))
		(increase (y ?b) (* (v ?b) -1.0))
		(assign (sailing-angle ?b) 180)))


(:action move_195
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 180) (<= (sailing-angle ?b) 210))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_165 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) -0.26))
		(increase (y ?b) (* (v ?b) -0.97))
		(assign (sailing-angle ?b) 195)))


(:action move_210
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 195) (<= (sailing-angle ?b) 225))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_150 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) -0.5))
		(increase (y ?b) (* (v ?b) -0.87))
		(assign (sailing-angle ?b) 210)))


(:action move_225
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 210) (<= (sailing-angle ?b) 240))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_135 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) -0.71))
		(increase (y ?b) (* (v ?b) -0.71))
		(assign (sailing-angle ?b) 225)))


(:action move_240
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 225) (<= (sailing-angle ?b) 255))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_120 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) -0.87))
		(increase (y ?b) (* (v ?b) -0.5))
		(assign (sailing-angle ?b) 240)))


(:action move_255
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 240) (<= (sailing-angle ?b) 270))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_105 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) -0.97))
		(increase (y ?b) (* (v ?b) -0.26))
		(assign (sailing-angle ?b) 255)))


(:action move_270
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 255) (<= (sailing-angle ?b) 285))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_90 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) -1.0))
		(increase (y ?b) (* (v ?b) -0.0))
		(assign (sailing-angle ?b) 270)))


(:action move_285
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 270) (<= (sailing-angle ?b) 300))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_75 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) -0.97))
		(increase (y ?b) (* (v ?b) 0.26))
		(assign (sailing-angle ?b) 285)))


(:action move_300
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 285) (<= (sailing-angle ?b) 315))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_60 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) -0.87))
		(increase (y ?b) (* (v ?b) 0.5))
		(assign (sailing-angle ?b) 300)))


(:action move_315
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 300) (<= (sailing-angle ?b) 330))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_45 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) -0.71))
		(increase (y ?b) (* (v ?b) 0.71))
		(assign (sailing-angle ?b) 315)))


(:action move_330
	:parameters (?b - boat)
	:precondition (and (>= (sailing-angle ?b) 315) (<= (sailing-angle ?b) 345))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_30 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) -0.5))
		(increase (y ?b) (* (v ?b) 0.87))
		(assign (sailing-angle ?b) 330)))


(:action move_345
	:parameters (?b - boat)
	:precondition (and (or (>= (sailing-angle ?b) 330) (= (sailing-angle ?b) 0)))
	:effect (and 
		(assign (v ?b) (+ (* (vmax_15 ?b) (- 1 (r ?b))) (* (r ?b) (v ?b))))
		(increase (x ?b) (* (v ?b) -0.26))
		(increase (y ?b) (* (v ?b) 0.97))
		(assign (sailing-angle ?b) 345)))


(:action save_person
	:parameters (?b - boat ?t - person)
	:precondition (and 
		(>= (x ?b) (- (x ?t) 15))
		(<= (x ?b) (+ (x ?t) 15))
		(>= (y ?b) (- (y ?t) 15))
		(<= (y ?b) (+ (y ?t) 15))
		(<= (v ?b) 0.1))
	:effect (and 
		(saved ?t)))



)
