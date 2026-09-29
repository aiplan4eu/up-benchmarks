# Copyright 2026 Unified Planning library and its maintainers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any, List, Tuple

from ConfigSpace import Configuration
from unified_planning.engines.results import ValidationResultStatus

from upbm.domains.twenty_forty_eight import TwentyFortyEightGenerator
from upbm.tests.base_domain_test import BaseDomainTest


PFILE8_PLAN = """
; move 1 of 8: up
(play u left)
(shift-1101 p11 p21 p31 p41 left midleft u)
(shift-0011 p12 p22 p32 p42 midleft midright u)
(shift-1100 p13 p23 p33 p43 midright right u)
(shift-1001 p14 p24 p34 p44 right done u)
(shift-finish-to-combine u left)
(combine-match u left i1 i2 p11 p21)
(combine-no-match u left i2 i3 p21 p31)
(combine-no-match u left i3 i4 p31 p41)
(combine-row-advance u left midleft)
(combine-no-match u midleft i1 i2 p12 p22)
(combine-no-match u midleft i2 i3 p22 p32)
(combine-match u midleft i3 i4 p32 p42)
(combine-row-advance u midleft midright)
(combine-no-match u midright i1 i2 p13 p23)
(combine-no-match u midright i2 i3 p23 p33)
(combine-match u midright i3 i4 p33 p43)
(combine-row-advance u midright right)
(combine-no-match u right i1 i2 p14 p24)
(combine-no-match u right i2 i3 p24 p34)
(combine-match u right i3 i4 p34 p44)
(combine-row-advance u right done)
(combine-finish u left)
(shift-1010 p11 p21 p31 p41 left midleft u)
(shift-1100 p12 p22 p32 p42 midleft midright u)
(shift-1100 p13 p23 p33 p43 midright right u)
(shift-1100 p14 p24 p34 p44 right done u)
(shift-finish u)

; move 2 of 8: left
(play l top)
(shift-1111 p11 p12 p13 p14 top midtop l)
(shift-1111 p21 p22 p23 p24 midtop midbot l)
(shift-0000 p31 p32 p33 p34 midbot bot l)
(shift-0000 p41 p42 p43 p44 bot done l)
(shift-finish-to-combine l top)
(combine-no-match l top i1 i2 p11 p12)
(combine-match l top i2 i3 p12 p13)
(combine-no-match l top i3 i4 p13 p14)
(combine-row-advance l top midtop)
(combine-no-match l midtop i1 i2 p21 p22)
(combine-no-match l midtop i2 i3 p22 p23)
(combine-no-match l midtop i3 i4 p23 p24)
(combine-row-advance l midtop midbot)
(combine-match l midbot i1 i2 p31 p32)
(combine-match l midbot i2 i3 p32 p33)
(combine-match l midbot i3 i4 p33 p34)
(combine-row-advance l midbot bot)
(combine-match l bot i1 i2 p41 p42)
(combine-match l bot i2 i3 p42 p43)
(combine-match l bot i3 i4 p43 p44)
(combine-row-advance l bot done)
(combine-finish l top)
(shift-1101 p11 p12 p13 p14 top midtop l)
(shift-1111 p21 p22 p23 p24 midtop midbot l)
(shift-0000 p31 p32 p33 p34 midbot bot l)
(shift-0000 p41 p42 p43 p44 bot done l)
(shift-finish l)

; move 3 of 8: down
(play d left)
(shift-0011 p41 p31 p21 p11 left midleft d)
(shift-0011 p42 p32 p22 p12 midleft midright d)
(shift-0011 p43 p33 p23 p13 midright right d)
(shift-0010 p44 p34 p24 p14 right done d)
(shift-finish-to-combine d left)
(combine-no-match d left i1 i2 p41 p31)
(combine-no-match d left i2 i3 p31 p21)
(combine-match d left i3 i4 p21 p11)
(combine-row-advance d left midleft)
(combine-no-match d midleft i1 i2 p42 p32)
(combine-no-match d midleft i2 i3 p32 p22)
(combine-match d midleft i3 i4 p22 p12)
(combine-row-advance d midleft midright)
(combine-match d midright i1 i2 p43 p33)
(combine-match d midright i2 i3 p33 p23)
(combine-match d midright i3 i4 p23 p13)
(combine-row-advance d midright right)
(combine-no-match d right i1 i2 p44 p34)
(combine-match d right i2 i3 p34 p24)
(combine-match d right i3 i4 p24 p14)
(combine-row-advance d right done)
(combine-finish d left)
(shift-1100 p41 p31 p21 p11 left midleft d)
(shift-1100 p42 p32 p22 p12 midleft midright d)
(shift-1000 p43 p33 p23 p13 midright right d)
(shift-1000 p44 p34 p24 p14 right done d)
(shift-finish d)

; move 4 of 8: right
(play r top)
(shift-0000 p14 p13 p12 p11 top midtop r)
(shift-0000 p24 p23 p22 p21 midtop midbot r)
(shift-0011 p34 p33 p32 p31 midbot bot r)
(shift-1111 p44 p43 p42 p41 bot done r)
(shift-finish-to-combine r top)
(combine-match r top i1 i2 p14 p13)
(combine-match r top i2 i3 p13 p12)
(combine-match r top i3 i4 p12 p11)
(combine-row-advance r top midtop)
(combine-match r midtop i1 i2 p24 p23)
(combine-match r midtop i2 i3 p23 p22)
(combine-match r midtop i3 i4 p22 p21)
(combine-row-advance r midtop midbot)
(combine-no-match r midbot i1 i2 p34 p33)
(combine-no-match r midbot i2 i3 p33 p32)
(combine-match r midbot i3 i4 p32 p31)
(combine-row-advance r midbot bot)
(combine-no-match r bot i1 i2 p44 p43)
(combine-match r bot i2 i3 p43 p42)
(combine-no-match r bot i3 i4 p42 p41)
(combine-row-advance r bot done)
(combine-finish r top)
(shift-0000 p14 p13 p12 p11 top midtop r)
(shift-0000 p24 p23 p22 p21 midtop midbot r)
(shift-1100 p34 p33 p32 p31 midbot bot r)
(shift-1101 p44 p43 p42 p41 bot done r)
(shift-finish r)

; move 5 of 8: down
(play d left)
(shift-0000 p41 p31 p21 p11 left midleft d)
(shift-1000 p42 p32 p22 p12 midleft midright d)
(shift-1100 p43 p33 p23 p13 midright right d)
(shift-1100 p44 p34 p24 p14 right done d)
(shift-finish-to-combine d left)
(combine-match d left i1 i2 p41 p31)
(combine-match d left i2 i3 p31 p21)
(combine-match d left i3 i4 p21 p11)
(combine-row-advance d left midleft)
(combine-no-match d midleft i1 i2 p42 p32)
(combine-match d midleft i2 i3 p32 p22)
(combine-match d midleft i3 i4 p22 p12)
(combine-row-advance d midleft midright)
(combine-match d midright i1 i2 p43 p33)
(combine-match d midright i2 i3 p33 p23)
(combine-match d midright i3 i4 p23 p13)
(combine-row-advance d midright right)
(combine-no-match d right i1 i2 p44 p34)
(combine-no-match d right i2 i3 p34 p24)
(combine-match d right i3 i4 p24 p14)
(combine-row-advance d right done)
(combine-finish d left)
(shift-0000 p41 p31 p21 p11 left midleft d)
(shift-1000 p42 p32 p22 p12 midleft midright d)
(shift-1000 p43 p33 p23 p13 midright right d)
(shift-1100 p44 p34 p24 p14 right done d)
(shift-finish d)

; move 6 of 8: left
(play l top)
(shift-0000 p11 p12 p13 p14 top midtop l)
(shift-0000 p21 p22 p23 p24 midtop midbot l)
(shift-0001 p31 p32 p33 p34 midbot bot l)
(shift-0111 p41 p42 p43 p44 bot done l)
(shift-finish-to-combine l top)
(combine-match l top i1 i2 p11 p12)
(combine-match l top i2 i3 p12 p13)
(combine-match l top i3 i4 p13 p14)
(combine-row-advance l top midtop)
(combine-match l midtop i1 i2 p21 p22)
(combine-match l midtop i2 i3 p22 p23)
(combine-match l midtop i3 i4 p23 p24)
(combine-row-advance l midtop midbot)
(combine-no-match l midbot i1 i2 p31 p32)
(combine-match l midbot i2 i3 p32 p33)
(combine-match l midbot i3 i4 p33 p34)
(combine-row-advance l midbot bot)
(combine-no-match l bot i1 i2 p41 p42)
(combine-match l bot i2 i3 p42 p43)
(combine-match l bot i3 i4 p43 p44)
(combine-row-advance l bot done)
(combine-finish l top)
(shift-0000 p11 p12 p13 p14 top midtop l)
(shift-0000 p21 p22 p23 p24 midtop midbot l)
(shift-1000 p31 p32 p33 p34 midbot bot l)
(shift-1100 p41 p42 p43 p44 bot done l)
(shift-finish l)

; move 7 of 8: left
(play l top)
(shift-0000 p11 p12 p13 p14 top midtop l)
(shift-0000 p21 p22 p23 p24 midtop midbot l)
(shift-1000 p31 p32 p33 p34 midbot bot l)
(shift-1100 p41 p42 p43 p44 bot done l)
(shift-finish-to-combine l top)
(combine-match l top i1 i2 p11 p12)
(combine-match l top i2 i3 p12 p13)
(combine-match l top i3 i4 p13 p14)
(combine-row-advance l top midtop)
(combine-match l midtop i1 i2 p21 p22)
(combine-match l midtop i2 i3 p22 p23)
(combine-match l midtop i3 i4 p23 p24)
(combine-row-advance l midtop midbot)
(combine-no-match l midbot i1 i2 p31 p32)
(combine-match l midbot i2 i3 p32 p33)
(combine-match l midbot i3 i4 p33 p34)
(combine-row-advance l midbot bot)
(combine-match l bot i1 i2 p41 p42)
(combine-match l bot i2 i3 p42 p43)
(combine-match l bot i3 i4 p43 p44)
(combine-row-advance l bot done)
(combine-finish l top)
(shift-0000 p11 p12 p13 p14 top midtop l)
(shift-0000 p21 p22 p23 p24 midtop midbot l)
(shift-1000 p31 p32 p33 p34 midbot bot l)
(shift-1000 p41 p42 p43 p44 bot done l)
(shift-finish l)

; move 8 of 8: up
(play u left)
(shift-0011 p11 p21 p31 p41 left midleft u)
(shift-0000 p12 p22 p32 p42 midleft midright u)
(shift-0000 p13 p23 p33 p43 midright right u)
(shift-0000 p14 p24 p34 p44 right done u)
(shift-finish-to-combine u left)
(combine-match u left i1 i2 p11 p21)
(combine-match u left i2 i3 p21 p31)
(combine-match u left i3 i4 p31 p41)
(combine-row-advance u left midleft)
(combine-match u midleft i1 i2 p12 p22)
(combine-match u midleft i2 i3 p22 p32)
(combine-match u midleft i3 i4 p32 p42)
(combine-row-advance u midleft midright)
(combine-match u midright i1 i2 p13 p23)
(combine-match u midright i2 i3 p23 p33)
(combine-match u midright i3 i4 p33 p43)
(combine-row-advance u midright right)
(combine-match u right i1 i2 p14 p24)
(combine-match u right i2 i3 p24 p34)
(combine-match u right i3 i4 p34 p44)
(combine-row-advance u right done)
(combine-finish u left)
(shift-1000 p11 p21 p31 p41 left midleft u)
(shift-0000 p12 p22 p32 p42 midleft midright u)
(shift-0000 p13 p23 p33 p43 midright right u)
(shift-0000 p14 p24 p34 p44 right done u)
(shift-finish u)
"""


class TestTwentyFortyEight(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self) -> str:
        return "2048"

    @property
    def generator(self) -> Any:
        return TwentyFortyEightGenerator

    def _get_configs(self, index: int) -> Tuple[Configuration, Configuration]:
        """A (domain config, instance config) pair for one shipped instance."""
        domain_space = TwentyFortyEightGenerator.get_domain_parameter_space()
        domain_config = Configuration(
            domain_space, values={"version": 1, "variant": "ipc"}
        )
        gen = TwentyFortyEightGenerator(domain_config)
        return domain_config, Configuration(
            gen.instance_parameter_space, values={"index": index}
        )

    @property
    def validation_cases(self):
        domain_config, pfile8 = self._get_configs(8)
        pfile9 = self._get_configs(9)[1]
        return [
            (domain_config, pfile8, PFILE8_PLAN, ValidationResultStatus.VALID),
            (domain_config, pfile8, "", ValidationResultStatus.INVALID),
            (domain_config, pfile9, PFILE8_PLAN, ValidationResultStatus.INVALID),
        ]

    @property
    def plannable(self) -> List[Tuple[Configuration, Configuration]]:
        # Every instance this generator can build is one of
        # the twenty IPC ones, and those are hard by design, unreasonable
        # to test here.
        return []

    @property
    def object_data(self):
        counts = [("pos", 16), ("status", 9), ("direction", 4), ("idx", 4)]
        return [
            (*self._get_configs(8), counts),
            (*self._get_configs(29), counts),
        ]

    @property
    def problem_actions(self) -> List[Tuple[Configuration, Configuration, int]]:
        return [(*self._get_configs(8), 23)]
