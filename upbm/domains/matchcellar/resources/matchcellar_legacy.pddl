(define (domain matchcellar)
     (:requirements :typing :durative-actions :negative-preconditions :numeric-fluents)
     (:types match fuse)
     (:predicates
          (handfree)
          (match_used ?match - match)
          (mended ?fuse - fuse)
          (light))
     (:functions
          (mend_fuse_duration)
     )

     (:durative-action light_match
          :parameters (?m - match)
          :duration (= ?duration 7)
          :condition (and
                    (at start (not (match_used ?m)))
               )
          :effect (and
          (at start (match_used ?m))
          (at start (light))
          (at end (not (light)))))


     (:durative-action mend_fuse
          :parameters (?fuse - fuse)
          :duration (= ?duration (mend_fuse_duration))
          :condition (and
               (at start (handfree))
               (at start (light))(over all (light))(at end (light))
               )
          :effect (and
               (at start (not (handfree)))
               (at end (mended ?fuse))
               (at end (handfree))
          )
     )
)
