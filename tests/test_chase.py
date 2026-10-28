import unittest
from unittest.mock import Mock
from types import SimpleNamespace

from chase_sim import ChaseSimulation, Controls, LightWall, Obstacle, MAX_SPEED, BOOST_SPEED, clamp
from chase_mode import ChaseAudio, ChaseRenderer
from gamepad import GamepadManager, _XBOX_MAP


class SimulationTests(unittest.TestCase):
    def test_motion_matches_across_frame_rates(self):
        sims=[]
        for fps in (30,60,144):
            sim=ChaseSimulation()
            for _ in range(fps*5):
                sim.advance(1/fps,Controls(steer=.08,throttle=1))
            sims.append(sim)
        for sim in sims[1:]:
            for name in ("s","x","speed","energy"):
                self.assertAlmostEqual(getattr(sim.player,name),getattr(sims[0].player,name),places=7)
            self.assertAlmostEqual(sim.time,5,places=7)

    def test_pause_freezes_every_timer_and_does_not_catch_up(self):
        sim=ChaseSimulation()
        sim.advance(.1,Controls(throttle=1))
        before=(sim.time,sim.player.s,sim.accumulator,sim.next_rival_boost)
        sim.advance(60,Controls(throttle=1),paused=True)
        self.assertEqual(before,(sim.time,sim.player.s,sim.accumulator,sim.next_rival_boost))
        sim.advance(.1,Controls(throttle=1))
        self.assertAlmostEqual(sim.time,.2)

    def test_shared_acceleration_and_boost_caps(self):
        sim=ChaseSimulation()
        sim.player.speed=sim.rival.speed=90
        sim.player.x=sim.rival.x=0
        sim.player.s=sim.rival.s=0
        for bike in (sim.player,sim.rival):
            sim._drive(bike,Controls(throttle=1),1)
            self.assertEqual(bike.speed,MAX_SPEED)
            sim._boost(bike,"test")
            sim._drive(bike,Controls(throttle=1),1)
            self.assertEqual(bike.speed,BOOST_SPEED)

    def test_boost_requires_new_press_and_cooldown(self):
        sim=ChaseSimulation()
        sim.advance(.1,Controls(boost=True))
        deadline=sim.player.boost_ready
        sim.advance(.1,Controls(boost=True))
        self.assertEqual(sim.player.boost_ready,deadline)
        sim.advance(.1,Controls())
        sim.advance(.1,Controls(boost=True))
        self.assertEqual(sim.player.boost_ready,deadline)

    def test_cut_hits_once_and_opening_is_safe(self):
        for x,hit in ((-.6,False),(.6,True)):
            sim=ChaseSimulation()
            sim.player.x=x
            sim.walls=[LightWall(.5,-.6,"rival",0,5)]
            sim.advance(.02,Controls(throttle=1))
            self.assertEqual(sim.player.energy<100,hit)
            self.assertEqual(sim.walls[0].hit,hit)

    def test_warning_does_not_collide_before_activation(self):
        sim=ChaseSimulation()
        sim.walls=[LightWall(.5,.6,"rival",.9,5)]
        sim.advance(.02,Controls(throttle=1))
        self.assertEqual(sim.player.energy,100)

    def test_player_wall_can_catch_rinzler(self):
        sim=ChaseSimulation()
        sim.player.s=100
        sim.rival.s=94.5
        sim.rival.x=-.3
        sim.player.x=-.3
        sim.advance(.02,Controls(wall=True,throttle=1))
        self.assertLess(sim.rival.energy,100)
        self.assertGreater(sim.pressure,0)
        self.assertEqual(len(sim.walls),1)
        sim.advance(.1,Controls(wall=True))
        self.assertEqual(len(sim.walls),1)

    def test_crossing_400_meters_ends_the_chase(self):
        sim=ChaseSimulation()
        sim.rival.s=399
        sim.advance(.01)
        self.assertIsNone(sim.result)
        sim.rival.s=sim.player.s+401
        sim.advance(.01)
        self.assertEqual(sim.result,"lost")
        self.assertIn("escapou",sim.reason)

    def test_hit_loss_and_new_session_has_clean_state(self):
        sim=ChaseSimulation()
        sim.player.energy=10
        sim.walls=[LightWall(.5,.6,"rival",0,5)]
        sim.advance(.02)
        self.assertEqual(sim.result,"lost")
        before=sim.time
        sim.advance(1)
        self.assertEqual(sim.time,before)
        fresh=ChaseSimulation()
        self.assertEqual(fresh.walls,[])
        self.assertEqual(fresh.player.energy,100)
        self.assertIsNone(fresh.result)

    def test_ai_only_changes_direction_after_reaction(self):
        sim=ChaseSimulation()
        sim.advance(.01)
        previous=sim.ai_steer
        sim.player.x=.9
        sim.advance(.05)
        self.assertEqual(sim.ai_steer,previous)
        sim.advance(.15)
        self.assertNotEqual(sim.ai_steer,previous)

    def test_obstacle_collision_uses_track_coordinates(self):
        sim=ChaseSimulation()
        sim.obstacles=[Obstacle(.5,sim.player.x)]
        sim.advance(.02)
        self.assertEqual(sim.player.energy,86)

    def test_win_is_reachable_with_ordinary_controls(self):
        sim=ChaseSimulation()
        for i in range(120*100):
            target=sim.rival.x if sim.gap<100 else 0
            walls=[w for w in sim.walls if w.owner=="rival" and 0<w.s-sim.player.s<120]
            if walls:
                target=min(walls,key=lambda w:w.s).gap_x
            if sim.phase=="finale":
                target=sim.target_lane
            desired=sim.rival.speed+(sim.gap-22)*.8
            throttle=clamp((desired-sim.player.speed)*.2+.15625,0,1)
            brake=.3 if sim.player.speed>desired+4 else 0
            drift=sim.road.curvature(sim.player.s)*sim.player.speed**2*.035
            steer=((target-sim.player.x)*5+drift)/(.30+.95*sim.player.speed/MAX_SPEED)
            wall=sim.phase=="finale" and abs(sim.player.x-sim.target_lane)<.10 and not sim.cut_deployed
            sim.advance(1/120,Controls(steer,throttle,brake,boost=i%1000==0 and sim.gap>65,wall=wall))
            if sim.result:
                break
        self.assertEqual(sim.result,"won")
        self.assertGreater(sim.player.energy,0)
        self.assertGreater(sim.score,0)
        self.assertGreaterEqual(sim.attempts,1)

    def close_chase(self):
        sim=ChaseSimulation()
        sim.player.x=sim.rival.x=0
        sim.player.speed=sim.rival.speed=90
        sim.rival.s=30
        sim.next_rival_boost=sim.next_rival_wall=1000
        sim.obstacles=[]
        return sim

    def test_pressure_requires_slipstream_and_rewards_proximity(self):
        values=[]
        for gap,lateral in ((10,0),(35,0),(30,.6),(-10,0)):
            sim=self.close_chase()
            sim.pressure=.2
            sim.rival.s=gap
            sim.player.x=lateral
            sim.advance(.1,Controls(throttle=.15625))
            values.append(sim.pressure)
        self.assertGreater(values[0],values[1])
        self.assertGreater(values[1],.2)
        self.assertLess(values[2],.2)
        self.assertLess(values[3],.2)

    def test_full_pressure_opens_four_second_window_without_winning(self):
        sim=self.close_chase()
        sim.pressure=.999
        sim.advance(.02,Controls(throttle=.15625))
        self.assertEqual(sim.phase,"finale")
        self.assertTrue(sim.telegraphing)
        self.assertIsNone(sim.result)
        self.assertAlmostEqual(sim.finale_until-sim.time,4,delta=.02)
        self.assertEqual(sim.attempts,1)

    def test_wrong_lane_and_timeout_recover_pressure_and_shorten_next_signal(self):
        for timeout in (False,True):
            sim=self.close_chase()
            sim._open_finale()
            first_signal=sim.telegraph_until-sim.time
            if timeout:
                sim.finale_until=sim.time+.005
            else:
                sim.walls=[LightWall(30.5,0,"player",0,5,cut_x=.6)]
            sim.advance(.02,Controls(throttle=.15625))
            self.assertEqual(sim.phase,"pressure")
            self.assertAlmostEqual(sim.pressure,.60,delta=.003)
            self.assertIsNone(sim.result)
            self.assertIn("finale_miss",sim.events)
            sim._open_finale()
            self.assertLess(sim.telegraph_until-sim.time,first_signal)
            self.assertEqual(sim.attempts,2)

    def test_held_wall_does_not_fire_when_finale_opens(self):
        sim=self.close_chase()
        sim.advance(.02,Controls(wall=True))
        sim._open_finale()
        sim.advance(.02,Controls(wall=True))
        self.assertFalse(sim.cut_deployed)
        sim.advance(.01,Controls())
        sim.advance(.02,Controls(wall=True))
        self.assertTrue(sim.cut_deployed)
        self.assertEqual(len([w for w in sim.walls if w.cut_x is not None]),1)

    def test_cut_plays_all_stages_before_result_and_pause_freezes_cinematic(self):
        sim=self.close_chase()
        sim._open_finale()
        sim.walls=[LightWall(30.5,0,"player",0,5,cut_x=0)]
        sim.advance(.01,Controls(throttle=.15625))
        self.assertEqual(sim.phase,"derez")
        self.assertIsNone(sim.result)
        frozen=(sim.time,sim.player.s,sim.rival.s,sim.derez_time,sim.hit_stop)
        sim.advance(10,paused=True)
        self.assertEqual(frozen,(sim.time,sim.player.s,sim.rival.s,sim.derez_time,sim.hit_stop))
        sim.advance(.05)
        self.assertAlmostEqual(sim.time,frozen[0])
        for _ in range(120):
            sim.advance(1/60)
        self.assertIsNone(sim.result)
        for _ in range(130):
            sim.advance(1/60)
        self.assertEqual(sim.result,"won")
        stages=[e for e in sim.events if e.startswith("rival_")]
        self.assertEqual(stages,["rival_impact","rival_skid","rival_overload","rival_derez","rival_tail"])
        self.assertGreater(sim.score,0)


class FakeCanvas:
    def __init__(self):
        self.count=0
    def __getattr__(self,name):
        if name.startswith("create_"):
            def create(*args,**kwargs):
                self.count+=1
                return self.count
            return create
        return lambda *args,**kwargs:None


class IntegrationTests(unittest.TestCase):
    def test_renderer_reuses_canvas_objects(self):
        canvas=FakeCanvas()
        renderer=ChaseRenderer(canvas,1280,720)
        sim=ChaseSimulation()
        renderer.render(sim)
        count=canvas.count
        for _ in range(5):
            renderer.render(sim)
        self.assertEqual(count,canvas.count)

    def test_missing_audio_is_optional(self):
        audio=ChaseAudio(SimpleNamespace(backend="none",sfx_on=True))
        audio.event("boost")
        audio.update(100,True)
        audio.close()

    def test_controller_reads_held_buttons_and_neutral(self):
        manager=GamepadManager.__new__(GamepadManager)
        js=Mock()
        js.get_instance_id.return_value=7
        js.get_numaxes.return_value=2
        js.get_axis.return_value=-.7
        js.get_numhats.return_value=1
        js.get_hat.return_value=(0,0)
        js.get_numbuttons.return_value=8
        js.get_button.side_effect=lambda number:number in (0,5)
        manager.ok=True
        manager.pads=[js]
        manager.info={7:{"map":_XBOX_MAP}}
        state=manager.driving_state()
        self.assertEqual(state["steer"],-.7)
        self.assertEqual(state["throttle"],1)
        self.assertTrue(state["boost"])
        js.get_axis.return_value=.05
        js.get_button.return_value=0
        js.get_button.side_effect=None
        self.assertEqual(manager.driving_state()["steer"],0)
        self.assertEqual(manager.driving_state()["throttle"],0)
        manager.pads=[]
        self.assertEqual(manager.driving_state()["steer"],0)

    def test_disconnected_controller_keeps_its_slot(self):
        manager=GamepadManager.__new__(GamepadManager)
        manager.ok,manager.pads,manager.slots,manager.info,manager.stick_dir,manager.sdl=True,[],[],{},{},None
        def pad(iid,name,guid):
            js=Mock()
            js.get_instance_id.return_value=iid
            js.get_name.return_value=name
            js.get_guid.return_value=guid
            js.get_numhats.return_value=1
            js.get_numbuttons.return_value=16
            return js
        ps4,xbox=pad(1,"PS4 Controller","ps4"),pad(2,"Xbox One Controller","xb")
        self.assertEqual(manager._attach(ps4),0)
        self.assertEqual(manager._attach(xbox),1)
        self.assertEqual(manager._detach(1),0)
        # a vaga 0 continua reservada: o Xbox segue sendo o controle 2
        self.assertEqual(manager.count,2)
        self.assertFalse(manager.is_connected(0))
        self.assertEqual(manager.name(0),"DualShock 4")
        self.assertTrue(manager.connected)
        # outro modelo não toma a vaga; o mesmo modelo volta para ela
        self.assertEqual(manager._attach(pad(3,"Generic Pad","gen")),2)
        self.assertEqual(manager._attach(pad(4,"PS4 Controller","ps4")),0)
        self.assertTrue(manager.is_connected(0))
        # vaga liberada: qualquer modelo pode ocupá-la
        manager._detach(2)
        manager.release(1)
        self.assertTrue(manager.is_released(1))
        self.assertEqual(manager._attach(pad(5,"Switch Pro","sw")),1)


if __name__=="__main__":
    unittest.main()
