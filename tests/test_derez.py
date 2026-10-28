"""Pool persistente e apagamento dos rastros através de curvas e portais."""

import math
import unittest
from unittest.mock import patch

from derez import Derez
from effects import Effects
from test_style import RecordingCanvas
import theme as T


class EffectCanvas(RecordingCanvas):
    itemconfig = RecordingCanvas.itemconfigure

    def delete(self, item):
        self.items.pop(item, None)


class DerezTests(unittest.TestCase):
    def test_all_fragments_follow_the_bike_heading_including_diagonals(self):
        for heading in (0, math.pi / 2, math.pi, -math.pi / 2, .73):
            cv=EffectCanvas()
            fx=Derez(cv)
            fx.spawn(400,300,heading=heading)
            forward=(math.cos(heading),math.sin(heading))
            particles=[p for p in fx._all if p.active and p.kind in ("cube","shard","spark")]
            origins=[(p.x,p.y) for p in particles]
            for p in particles:
                along=p.vx*forward[0]+p.vy*forward[1]
                side=abs(-p.vx*forward[1]+p.vy*forward[0])
                self.assertGreater(along,0)
                self.assertLessEqual(side,along*.73)
            fx.update(.4)
            for p,(x,y) in zip(particles,origins):
                self.assertGreater((p.x-x)*forward[0]+(p.y-y)*forward[1],0)
                self.assertLess(math.dist((p.x, p.y), (x, y)), 110)
            self.assertEqual(sum(p.active for p in fx.pools["ring"]),2)
            self.assertGreater(sum(p.active for p in fx.pools["cube"]),100)

    def test_ring_stays_at_impact_while_fragments_move_forward(self):
        cv=EffectCanvas()
        fx=Derez(cv)
        fx.spawn(400,300,heading=math.pi)
        fx.update(.4)
        for p in fx.pools["ring"]:
            if p.active:
                x0,y0,x1,y1=cv.items[p.item][0]
                self.assertAlmostEqual((x0+x1)/2,400)
                self.assertAlmostEqual((y0+y1)/2,300)

    def test_dense_bursts_have_capacity_for_all_four_bikes(self):
        cv=EffectCanvas()
        fx=Effects(cv)
        totals=[]
        for i in range(4):
            fx.derez(100+i*80,200,T.CYAN,(1,0),1.4)
            totals.append(sum(p.active for p in fx.voxels.pools["cube"]))
        emitted=[totals[0],*(b-a for a,b in zip(totals,totals[1:]))]
        self.assertTrue(all(count>100 for count in emitted))
        self.assertEqual(len(set(emitted)),1)
        self.assertEqual(sum(p.active for p in fx.voxels.pools["ring"]),8)

    def test_gravity_acts_after_upward_directional_launch(self):
        cv=EffectCanvas()
        fx=Derez(cv)
        with patch("derez.random.random", return_value=.5):
            fx.spawn(400,300,heading=-math.pi/2,gravity=900,power=1.4)
        cube=next(p for p in fx.pools["cube"] if p.active)
        self.assertLess(cube.vy,0)
        fx.update(.9)
        self.assertGreater(cube.vy,0)

    def test_wall_bursts_are_redirected_inward_and_offset_from_the_edge(self):
        for wall, origin, expected in (
            ("left", (28, 200), (1, -1)),
            ("right", (772, 200), (-1, -1)),
            ("top", (400, 28), (1, 1)),
            ("bottom", (400, 572), (1, -1)),
        ):
            with self.subTest(wall=wall):
                cv=EffectCanvas()
                fx=Derez(cv)
                fx.spawn(*origin, heading=0, wall=wall)
                particles = [
                    p for p in fx._all
                    if p.active and p.kind in ("cube", "shard", "spark")
                ]
                self.assertTrue(all(
                    p.vx * expected[0] + p.vy * expected[1] > 0
                    for p in particles
                ))
                scan = next(p for p in fx.pools["scan"] if p.active)
                if wall == "left":
                    self.assertGreater(scan.x, origin[0])
                elif wall == "right":
                    self.assertLess(scan.x, origin[0])
                elif wall == "top":
                    self.assertGreater(scan.y, origin[1])
                else:
                    self.assertLess(scan.y, origin[1])

    def test_simultaneous_deaths_and_pool_survives_round_reset(self):
        cv=EffectCanvas()
        fx=Effects(cv)
        count=cv.count
        for i,color in enumerate((T.CYAN,T.ORANGE,T.PURPLE,T.GREEN)):
            fx.derez(100+i*80,200,color,(1,0),1.4)
        self.assertEqual(cv.count,count)
        self.assertEqual(sum(p.active for p in fx.voxels.pools["scan"]),4)
        for _ in range(40):
            fx.update(.05)
        self.assertFalse(fx.voxels.busy)
        fx.reset()
        fx.derez(100,200,T.PURPLE,(0,-1))
        self.assertTrue(fx.voxels.busy)
        self.assertEqual(cv.count,count)
        self.assertTrue(all(p.kind in ("cube","shard","spark","ring","scan","flash")
                            for p in fx.voxels._all))

    def test_elapsed_time_is_preserved_after_a_slow_frame(self):
        cv=EffectCanvas()
        fx=Derez(cv)
        fx.spawn(100,200)
        fx.update(2)
        self.assertFalse(fx.busy)

    def test_head_to_tail_dissolve_keeps_portal_pieces_separate(self):
        cv=EffectCanvas()
        fx=Effects(cv)
        old=cv.create_line(0,0,40,0,40,60,fill=T.CYAN)
        new=cv.create_line(400,0,500,0,fill=T.CYAN)
        done=[]
        fx.dissolve_trail([([0,0,40,0,40,60],[(old,T.CYAN)]),
                           ([400,0,500,0],[(new,T.CYAN)])],1,
                          on_done=lambda:done.append(True))
        fx.update(.25)
        self.assertEqual(cv.items[new][0],(400,0,450.0,0.0))
        self.assertEqual(cv.items[old][0],(0,0,40,0,40,60))
        self.assertEqual(done,[])
        fx.update(.5)
        self.assertEqual(cv.items[new][1]["state"],"hidden")
        self.assertEqual(cv.items[old][0],(0,0,40,0,40.0,10.0))
        fx.update(.25)
        self.assertNotIn(old,cv.items)
        self.assertNotIn(new,cv.items)
        self.assertEqual(done,[True])


if __name__=="__main__":
    unittest.main()
