"""Actual PIE integration checks for the authored encounter + recovery implementation.

Run from an idle Unreal Editor with the gameplay map saved and C++ compiled.
This asynchronous script never broadcasts combat/death/reward delegates, edits stage
state, directly changes enemy health, or destroys an enemy to complete an encounter.
All 109 counted defeats enter through the real combat resolver. R01 includes a short
real caster-AI firing/stationary-position observation; other AI is locally paused to
isolate orchestration/rewards. This does not certify combat difficulty or VR input.
"""

import json
import math
import os
from pathlib import Path
import re
import time
import traceback

import unreal


class EncounterRecoveryIntegration:
    MAP = "/Game/ReversedScale/Maps/L_NilinGameplayV01"
    PROJECT = Path(r"D:\game design\experiment")
    OUT = PROJECT / "Docs/Gameplay/EncounterRecovery_v01/RuntimeIntegration.json"
    LEDGER_DIR = PROJECT / "Saved/SaveGames/NilinMasterRewards"
    DEADLINE_SECONDS = 600
    EXPECTED_COUNTS = [2, 6, 2, 36, 6, 2, 2, 8, 10, 12, 14, 1, 3, 3, 1, 1]

    def __init__(self):
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.began = time.monotonic()
        self.phase = "start"
        self.phase_time = self.began
        self.handle = None
        self.busy = False
        self.owns_play = False
        self.pawn = self.director = self.resolver = self.run = self.rewards = None
        self.vitals = self.recovery = self.guard = self.barrier = self.identity = None
        self.movement = self.kill_definition = self.parry_definition = None
        self.stage_defs = []
        self.stage_index = 0
        self.current = None
        self.parry_index = 0
        self.guard_ready_at = 0.0
        self.seen_enemy_ids = set()
        self.killed_ids = set()
        self.pending_kill_times = {}
        self.completion_callbacks = {}
        self.completion_snapshots = {}
        self.live_ai_ids = set()
        self.ai_probe_started_at = None
        self.ai_probe_callbacks = []
        self.ledger_file = None
        self.fixture_paths = []
        self.screenshot_task = None
        self.existing_ledgers = {path.name for path in self.LEDGER_DIR.glob("*.nlmr")}
        self.last_save = self.began
        self.report = {
            "kind": "Real PIE resolver-driven encounter/recovery integration",
            "map": self.MAP,
            "state": "starting",
            "success": False,
            "deadline_seconds": self.DEADLINE_SECONDS,
            "stages": [],
            "perfect_parry": {"results": []},
            "retry": {},
            "master_rewards": [],
            "rock_r01_ai": {"state": "pending", "duration_game_seconds": 12.0},
            "total_counted_spawns": 0,
            "total_resolver_defeats": 0,
            "failures": [],
            "cleanup": {"state": "not_needed", "deleted_only_test_run": False},
            "scope": [
                "The actual saved gameplay map, possessed level player and finite encounter director run in PIE.",
                "Stage entries use explicit setup teleports; this is not a continuous traversal test.",
                "R01's two actual rock casters run live AI for 12 game seconds, observing Telegraph/Attack, emitted projectiles and stationary feet.",
                "Other enemy AI is locally paused for deterministic orchestration/reward checks; automatic health protection may assist the R01 observation.",
                "Defeats use Resolver.ResolveContact with a transient 999-damage test definition.",
                "Perfect parries use live spawned enemies and Resolver.ResolveGuardContact, with real release/rearm timing.",
                "No combat/death/reward delegates are broadcast manually and no stage-completion state is written.",
                "This does not verify human combat, AI attack readability, VR gestures, headset performance or difficulty balance.",
            ],
        }

    def save(self):
        self.OUT.parent.mkdir(parents=True, exist_ok=True)
        self.report["elapsed_seconds"] = time.monotonic() - self.began
        self.OUT.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8")
        self.last_save = time.monotonic()

    @staticmethod
    def valid(obj):
        return obj is not None and unreal.SystemLibrary.is_valid(obj)

    @staticmethod
    def name(value):
        return str(value)

    @staticmethod
    def vec_list(value):
        return [float(value.x), float(value.y), float(value.z)]

    @staticmethod
    def guid_text(value):
        # UKismetGuidLibrary exposes Conv_GuidToString as the Guid.ToString script method.
        text = value.to_string()
        digits = re.sub(r"[^0-9a-fA-F]", "", text)
        if not re.fullmatch(r"[0-9a-fA-F]{32}", digits):
            raise RuntimeError("Unexpected Guid representation: " + text)
        return digits.lower()

    def require(self, condition, message, **evidence):
        if not condition:
            raise RuntimeError(message + (": " + json.dumps(evidence, ensure_ascii=False) if evidence else ""))

    def world_time(self, world):
        return float(unreal.GameplayStatics.get_time_seconds(world))

    def move_player(self, location):
        self.pawn.set_actor_location(location, False, True)
        self.movement.stop_movement_immediately()
        self.movement.set_movement_mode(unreal.MovementMode.MOVE_WALKING)

    def stage_center_capsule(self, stage):
        center = stage.get_editor_property("trigger_center")
        return unreal.Vector(center.x, center.y, center.z + 88.0)

    def get_enemies(self, world, alive_only=True):
        enemies = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NLEnemyCharacter)
        result = []
        for enemy in enemies:
            if not self.valid(enemy):
                continue
            vitals = enemy.get_editor_property("vitals")
            if not vitals:
                continue
            if vitals.is_dead():
                # Permit normal death presentation/corpse retirement after the isolated hit.
                enemy.set_lab_paused(False)
                if alive_only:
                    continue
            else:
                runtime_id = self.guid_text(enemy.get_editor_property("combat_identity").get_runtime_id())
                enemy.set_lab_paused(runtime_id not in self.live_ai_ids)
            result.append(enemy)
        return result

    def make_contact(self, source, target, definition, projectile=False):
        contact = unreal.NLCombatContact()
        source_identity = source.get_component_by_class(unreal.NLCombatIdentityComponent)
        target_identity = target.get_component_by_class(unreal.NLCombatIdentityComponent)
        self.require(source_identity is not None and target_identity is not None, "Combat identity missing")
        contact.set_editor_property("attack_instance_id", unreal.GuidLibrary.new_guid())
        contact.set_editor_property("source_runtime_id", source_identity.ensure_runtime_id())
        contact.set_editor_property("target_runtime_id", target_identity.ensure_runtime_id())
        contact.set_editor_property("projectile_generation", 0 if projectile else -1)
        contact.set_editor_property("contact_time_seconds", self.world_time(target.get_world()))
        contact.set_editor_property("attack_definition_id", definition.get_editor_property("stable_id"))
        if projectile:
            contact.set_editor_property("hit_position", self.barrier.get_world_location())
            forward = self.barrier.get_forward_vector()
            contact.set_editor_property("incoming_velocity", unreal.Vector(-forward.x * 1000, -forward.y * 1000, -forward.z * 1000))
        else:
            contact.set_editor_property("hit_position", target.get_actor_location())
        return contact

    def prepare_services(self, world):
        self.pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
        if not self.pawn:
            return False
        self.require("NLLevelCombatCharacter" in self.pawn.get_class().get_path_name(), "Wrong possessed player class")
        directors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NLLevelEncounterDirector)
        self.require(len(directors) == 1, "Expected exactly one level encounter director", count=len(directors))
        self.director = directors[0]
        self.stage_defs = list(self.director.get_editor_property("stages"))
        self.require(len(self.stage_defs) == 16 and self.director.get_stage_count() == 16, "Expected 16 runtime stages")
        # BlueprintInternalUseOnly subsystem library is intentionally absent from this Python build.
        def existing_subsystem(cls, outer):
            return next((obj for obj in unreal.ObjectIterator(cls) if unreal.SystemLibrary.is_valid(obj) and obj.get_outer()==outer),None)
        self.resolver = existing_subsystem(unreal.NLCombatResolverSubsystem,world)
        self.rewards = existing_subsystem(unreal.NLMasterRewardSubsystem,world)
        self.run = existing_subsystem(unreal.NLRunStateSubsystem,unreal.GameplayStatics.get_game_instance(world))
        self.require(self.resolver and self.rewards and self.run, "Required gameplay subsystems unavailable")
        self.vitals = self.pawn.get_editor_property("vitals")
        self.recovery = self.pawn.get_editor_property("combat_recovery")
        self.guard = self.pawn.get_editor_property("guard")
        self.barrier = self.pawn.get_editor_property("guard_collision")
        self.identity = self.pawn.get_editor_property("combat_identity")
        self.movement = self.pawn.get_component_by_class(unreal.CharacterMovementComponent)
        self.require(all((self.vitals, self.recovery, self.guard, self.barrier, self.identity, self.movement)), "Player combat components missing")
        run_digits = self.guid_text(self.run.get_run_id())
        self.require(run_digits != "0" * 32, "Gameplay mode did not create a fresh RunId")
        self.ledger_file = self.LEDGER_DIR / (run_digits.upper() + ".nlmr")
        # Windows file names are case insensitive. Never authorize deleting a prior run.
        self.require(self.ledger_file.name.lower() not in {name.lower() for name in self.existing_ledgers}, "PIE inherited an existing run ledger")
        self.report["run_id_digits"] = run_digits
        self.report["cleanup"] = {"state": "pending", "file": str(self.ledger_file), "deleted_only_test_run": False}
        self.report["pawn_class"] = self.pawn.get_class().get_path_name()
        self.report["director_class"] = self.director.get_class().get_path_name()
        navs = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.RecastNavMesh)
        self.require(len(navs) == 1, "Expected one matching baked navigation data set")
        self.require(navs[0].get_editor_property("runtime_generation") == unreal.RuntimeGenerationType.STATIC
                     and not navs[0].get_editor_property("force_rebuild_on_load"), "Map lost its baked navigation policy")
        cfg = json.loads((self.OUT.parent / "EncounterConfig.json").read_text(encoding="utf-8"))
        checks = []
        for stage in cfg["stages"]:
            for point in stage["spawn_points"]:
                ground = unreal.Vector(*[value * 100.0 for value in point["ground_m"]])
                projected = unreal.NavigationSystemV1.project_point_to_navigation(world, ground, navs[0], None, unreal.Vector(60,60,180))
                valid = projected is not None and math.dist(self.vec_list(projected),self.vec_list(ground)) < 180.0
                checks.append({"stage":stage["id"],"point":point["id"],"passed":valid})
                self.require(valid, "Cold PIE navigation feet projection failed", stage=stage["id"],point=point["id"])
        self.report["cold_pie_navigation"]={"success":True,"checks":checks,"projection_extent_cm":[60,60,180],
                                            "nav_data":navs[0].get_path_name(),"game_time":self.world_time(world)}
        unreal.SystemLibrary.execute_console_command(world, "t.IdleWhenNotForeground 0")
        unreal.SystemLibrary.execute_console_command(world, "Slate.bAllowThrottling 0")
        unreal.GameplayStatics.set_game_paused(world, False)
        self.report["state"] = "perfect_parry_probe"
        return True

    def first_source(self, world):
        encounter = self.director.get_active_encounter()
        if not encounter:
            return None
        return next((enemy for enemy in self.get_enemies(world) if encounter.owns_enemy(enemy)), None)

    def guard_probe(self, world):
        source = self.first_source(world)
        if source is None:
            return
        if self.phase == "guard_setup":
            self.require(self.vitals.restore_resource_preset(70.0, 100.0), "Cannot set injured probe preset")
            self.recovery.reset_recovery()
            self.pawn.lower_mirror()
            self.guard_ready_at = self.world_time(world) + 0.42
            self.phase = "ordinary_wait"
            return
        if self.world_time(world) < self.guard_ready_at:
            return
        self.pawn.raise_mirror()
        contact = self.make_contact(source, self.pawn, self.parry_definition, True)
        perfect = self.phase == "perfect_wait"
        result = self.resolver.resolve_guard_contact(source, self.pawn, contact, self.parry_definition, self.guard, perfect)
        sample = {
            "kind": "perfect" if perfect else "ordinary",
            "outcome": str(result.get_editor_property("outcome")),
            "health": self.vitals.get_health(),
            "charges": self.recovery.get_recovery_charges(),
            "source_runtime_id": self.guid_text(source.get_editor_property("combat_identity").get_runtime_id()),
            "attack_id": self.guid_text(contact.get_editor_property("attack_instance_id")),
        }
        self.report["perfect_parry"]["results"].append(sample)
        if not perfect:
            self.require(result.get_editor_property("outcome") == unreal.NLCombatOutcome.BLOCKED, "Ordinary block failed", result=sample)
            self.require(sample["charges"] == 0 and sample["health"] == 70.0, "Ordinary block rewarded recovery", result=sample)
            self.phase = "perfect_wait"
        else:
            self.parry_index += 1
            self.require(result.get_editor_property("outcome") == unreal.NLCombatOutcome.PERFECT_PARRY, "Real perfect guard was not accepted", result=sample)
            expected = self.parry_index if self.parry_index < 3 else 0
            self.require(sample["charges"] == expected, "Recovery charge count mismatch", result=sample)
            duplicate = self.resolver.resolve_guard_contact(source, self.pawn, contact, self.parry_definition, self.guard, True)
            self.require(duplicate.get_editor_property("outcome") == unreal.NLCombatOutcome.IGNORED, "Duplicate guard contact was accepted")
            self.require(self.recovery.get_recovery_charges() == expected, "Duplicate guard contact accrued a charge")
            sample["duplicate_outcome"] = str(duplicate.get_editor_property("outcome"))
            if self.parry_index == 3:
                self.require(self.vitals.get_health() == 80.0 and self.recovery.get_last_recovered_health() == 10.0, "Three perfect guards did not heal exactly ten")
                self.report["perfect_parry"]["success"] = True
                self.report["perfect_parry"]["last_recovered_health"] = self.recovery.get_last_recovered_health()
                self.report["perfect_parry"]["release_wait_game_seconds"] = 0.42
                self.pawn.lower_mirror()
                self.probe_retry()
                return
        self.pawn.lower_mirror()
        self.guard_ready_at = self.world_time(world) + 0.42
        self.save()

    def probe_retry(self):
        before = self.director.get_completed_stage_count()
        stage_id = self.director.get_active_stage_id()
        self.director.fail_active_stage("Automation.RetryProbe")
        self.require(self.director.get_stage_status(stage_id) == unreal.NLLevelStageState.FAILED, "FailActiveStage did not enter failed state")
        expected_entry = self.director.get_retry_transform().translation
        self.pawn.reset_lab()
        location = self.pawn.get_actor_location()
        error = math.dist(self.vec_list(location), self.vec_list(expected_entry))
        self.require(error < 5.0, "Retry did not restore authored entry", error_cm=error)
        self.require(self.director.get_completed_stage_count() == before == 0, "Retry altered completed stages")
        self.require(self.director.get_stage_status(stage_id) == unreal.NLLevelStageState.WARNING, "Retry did not restart the stage warning")
        self.require(self.vitals.get_health() == self.vitals.get_max_health() and self.recovery.get_recovery_charges() == 0,
                     "Retry did not reset health/recovery")
        self.report["retry"] = {"success": True, "stage": str(stage_id), "entry_error_cm": error,
                                "completed_before": before, "completed_after": self.director.get_completed_stage_count(),
                                "probe_enemies": "Initial probe controller was retired only by the real retry cleanup; its spawns are excluded from 109 final-run counts."}
        self.phase = "stage_setup"
        self.report["state"] = "encounters"
        self.save()

    def start_stage_report(self):
        stage = self.stage_defs[self.stage_index]
        stage_id = stage.get_editor_property("stage_id")
        waves = list(stage.get_editor_property("waves"))
        self.require(self.director.get_completed_stage_count() == self.stage_index, "Prior-stage dependency count mismatch")
        if self.stage_index:
            previous = self.stage_defs[self.stage_index - 1].get_editor_property("stage_id")
            self.require(stage.get_editor_property("required_stage_id") == previous, "Authored dependency chain mismatch")
            self.require(self.director.get_stage_status(previous) == unreal.NLLevelStageState.COMPLETED, "Previous stage is not completed")
        self.current = {
            "id": str(stage_id), "index": self.stage_index, "state": "entering",
            "required": str(stage.get_editor_property("required_stage_id")),
            "expected_count": self.EXPECTED_COUNTS[self.stage_index],
            "warning_observed": False, "busy_rejection_verified": False,
            "waves": [], "resolver_defeats": 0,
        }
        for index, wave in enumerate(waves):
            planned = sum(entry.get_editor_property("count") for entry in wave.get_editor_property("spawn_entries"))
            self.current["waves"].append({
                "index": index, "id": str(wave.get_editor_property("wave_id")),
                "planned": planned, "max_alive_limit": wave.get_editor_property("max_alive"),
                "max_alive_observed": 0, "spawn_count": 0, "resolver_defeats": 0,
            })
        self.require(sum(wave["planned"] for wave in self.current["waves"]) == self.current["expected_count"], "Actual asset budget differs from 109 plan")
        self.report["stages"].append(self.current)
        if self.stage_index > 0:
            self.move_player(self.stage_center_capsule(stage))
        self.phase = "stage_wait"
        self.phase_time = time.monotonic()
        self.save()

    def verify_master_reward(self, master_id, location):
        if any(reward["master_id"] == str(master_id) for reward in self.report["master_rewards"]):
            return
        pickup = self.rewards.get_pending_reward(master_id)
        self.require(self.valid(pickup), "Master defeat did not create pending healing pickup", master_id=str(master_id))
        world = self.pawn.get_world()
        matches = [actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NLHealingPickup)
                   if self.valid(actor) and actor.get_master_id() == master_id]
        self.require(len(matches) == 1, "Master created other than one pending pickup", master_id=str(master_id), count=len(matches))
        self.require(self.vitals.restore_resource_preset(100.0, 100.0), "Cannot establish full-health reward probe")
        full_collect = pickup.try_collect(self.pawn)
        self.require(not full_collect and self.valid(self.rewards.get_pending_reward(master_id)), "Full health consumed master reward")
        self.require(self.vitals.restore_resource_preset(70.0, 100.0), "Cannot establish injured reward probe")
        collected = pickup.try_collect(self.pawn)
        self.require(collected and self.vitals.get_health() == 95.0, "Master pickup did not heal 70 to 95")
        health_before_second = self.vitals.get_health()
        second_result = False
        second_note = "Pickup already destroyed by its one-shot claim"
        if self.valid(pickup):
            second_result = pickup.try_collect(self.pawn)
            second_note = "Second TryCollect returned false"
        self.require(not second_result and self.vitals.get_health() == health_before_second, "Master pickup healed twice")
        duplicate_spawn = self.rewards.spawn_first_defeat_reward(master_id, location, self.pawn)
        self.require(not duplicate_spawn and not self.rewards.get_pending_reward(master_id), "Collected master reward respawned")
        self.require(self.run.has_defeated_master(master_id) and self.run.has_collected_master_reward(master_id), "Durable master ledger did not record normal collection")
        self.report["master_rewards"].append({
            "master_id": str(master_id), "success": True, "pending_pickup_count": 1,
            "full_health_collected": bool(full_collect), "injured_collected": bool(collected),
            "injured_health_before": 70.0, "health_after": 95.0,
            "second_collection": second_note, "duplicate_spawn_returned_none": True,
        })
        self.vitals.restore_resource_preset(100.0, 100.0)
        self.save()

    def bind_completion_snapshot(self, encounter, stage_id):
        key = str(stage_id)
        if key in self.completion_callbacks:
            return

        def snapshot():
            # C phases share one trigger: the director can start the next warning
            # and retire this controller before the next Slate sample. Observe its
            # real completion event synchronously rather than infer/modify state.
            try:
                self.completion_snapshots[key] = {
                    "spawned": encounter.get_spawned_count(), "defeated": encounter.get_defeated_count(),
                    "planned": encounter.get_planned_count(), "completed_waves": encounter.get_completed_wave_count(),
                    "failed_spawns": encounter.get_failed_spawn_count(),
                    "snapshot_source": "OnEncounterCompleted listener; the script never broadcasts this event",
                    "controller_state": str(encounter.get_state()),
                }
            except Exception:
                self.completion_snapshots[key] = {"error": traceback.format_exc()}

        encounter.get_editor_property("on_encounter_completed").add_callable(snapshot)
        self.completion_callbacks[key] = (encounter, snapshot)

    def unbind_completion(self, stage_id):
        binding = self.completion_callbacks.pop(str(stage_id), None)
        if binding:
            encounter, callback = binding
            if self.valid(encounter):
                encounter.get_editor_property("on_encounter_completed").remove_callable(callback)

    def note_ai_state(self, runtime_id, state, game_time):
        probe = self.report["rock_r01_ai"]
        item = probe.get("casters", {}).get(runtime_id)
        if item is None:
            return
        text = str(state)
        if not item["state_transitions"] or item["state_transitions"][-1]["state"] != text:
            item["state_transitions"].append({"state": text, "game_time": game_time})
        if state == unreal.NLEnemyState.TELEGRAPH:
            item["observed_telegraph"] = True
        if state == unreal.NLEnemyState.ATTACK:
            item["observed_attack"] = True
        if state == unreal.NLEnemyState.DESPAWN:
            item["observed_despawn"] = True

    def make_ai_state_listener(self, runtime_id):
        def listener(enemy_actor, previous_state, new_state):
            world = self.editor.get_game_world()
            if world:
                self.note_ai_state(runtime_id, new_state, self.world_time(world))
        return listener

    def stop_ai_probe_listeners(self):
        for brain, listener in self.ai_probe_callbacks:
            if self.valid(brain):
                brain.get_editor_property("on_state_changed").remove_callable(listener)
        self.ai_probe_callbacks = []

    def observe_rock_ai(self, world, encounter, owned):
        """Return true only after a real 12-second two-caster AI observation passes."""
        probe = self.report["rock_r01_ai"]
        if probe["state"] == "passed":
            return True
        if self.ai_probe_started_at is None:
            self.require(len(owned) == 2 and encounter.get_alive_count() == 2, "R01 AI probe requires both real spawned casters")
            spec = json.loads((self.PROJECT / "Docs/LevelDesign/Blockout_v05/LayoutSpec.json").read_text(encoding="utf-8-sig"))
            station = next(item for item in spec["ranged_encounters"]["stations"] if item["id"] == "R01")
            rest = station["route_rest"]
            self.move_player(unreal.Vector(rest[0] * 100, rest[1] * 100, rest[2] * 100 + 90))
            self.pawn.lower_mirror()
            self.require(self.vitals.restore_resource_preset(100.0, 100.0), "Cannot prepare safe full-health AI observation")
            self.ai_probe_started_at = self.world_time(world)
            probe.update({
                "state": "observing", "start_game_time": self.ai_probe_started_at,
                "player_route_rest_m": list(rest), "casters": {}, "protective_heals": [],
                "projectile_count": 0,
                "automation_protection": "If player health falls below 50, RestoreResourcePreset(90,100) keeps observation alive; no player skill is inferred.",
            })
            for enemy in owned:
                runtime_id = self.guid_text(enemy.get_editor_property("combat_identity").get_runtime_id())
                brain = enemy.get_enemy_brain()
                self.require(brain.get_editor_property("hold_ranged_position"), "R01 BP did not enable authored stationary caster behavior")
                self.require(brain.get_editor_property("role") == unreal.NLEnemyRole.TALISMAN_CASTER, "R01 spawned a non-caster enemy")
                position = enemy.get_actor_location()
                probe["casters"][runtime_id] = {
                    "actor": enemy.get_path_name(), "start_capsule_cm": self.vec_list(position),
                    "max_xy_displacement_cm": 0.0, "state_transitions": [],
                    "observed_telegraph": False, "observed_attack": False, "observed_despawn": False,
                    "projectile_ids": [],
                }
                self.live_ai_ids.add(runtime_id)
                listener = self.make_ai_state_listener(runtime_id)
                brain.get_editor_property("on_state_changed").add_callable(listener)
                self.ai_probe_callbacks.append((brain, listener))
                enemy.set_lab_paused(False)
                self.note_ai_state(runtime_id, brain.get_state(), self.world_time(world))
            self.save()
            return False

        self.require(len(owned) == 2 and encounter.get_alive_count() == 2, "A real R01 caster vanished/died during AI observation")
        for enemy in owned:
            runtime_id = self.guid_text(enemy.get_editor_property("combat_identity").get_runtime_id())
            self.require(runtime_id in self.live_ai_ids, "R01's live caster identity changed during observation")
            item = probe["casters"][runtime_id]
            state = enemy.get_enemy_brain().get_state()
            self.note_ai_state(runtime_id, state, self.world_time(world))
            position = enemy.get_actor_location()
            delta = math.hypot(position.x - item["start_capsule_cm"][0], position.y - item["start_capsule_cm"][1])
            item["max_xy_displacement_cm"] = max(item["max_xy_displacement_cm"], delta)
            self.require(delta < 50.0, "Rock caster moved more than half a metre off its starting foot", caster=runtime_id, delta_cm=delta)
            self.require(not item["observed_despawn"], "Rock caster entered Despawn during actual AI observation")
        for projectile in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.NLCombatProjectile):
            if not self.valid(projectile):
                continue
            source = projectile.get_source_actor()
            if not self.valid(source):
                continue
            identity = source.get_component_by_class(unreal.NLCombatIdentityComponent)
            if identity is None:
                continue
            source_id = self.guid_text(identity.get_runtime_id())
            if source_id not in self.live_ai_ids:
                continue
            attack_id = self.guid_text(projectile.get_attack_instance_id())
            ids = probe["casters"][source_id]["projectile_ids"]
            if attack_id not in ids:
                ids.append(attack_id)
                probe["projectile_count"] += 1
        if self.vitals.get_health() < 50.0:
            probe["protective_heals"].append({"game_time": self.world_time(world), "health_before": self.vitals.get_health(), "preset_after": 90.0})
            self.require(self.vitals.restore_resource_preset(90.0, 100.0), "AI observation health protection failed")
        elapsed = self.world_time(world) - self.ai_probe_started_at
        probe["observed_game_seconds"] = elapsed
        if elapsed > 2.0 and "screenshot" not in probe:
            camera = unreal.GameplayStatics.get_player_camera_manager(world, 0)
            focus = unreal.Vector(
                sum(enemy.get_actor_location().x for enemy in owned) / len(owned),
                sum(enemy.get_actor_location().y for enemy in owned) / len(owned),
                sum(enemy.get_actor_location().z for enemy in owned) / len(owned) + 40,
            )
            unreal.GameplayStatics.get_player_controller(world, 0).set_control_rotation(
                unreal.MathLibrary.find_look_at_rotation(camera.get_camera_location(), focus))
            path = self.OUT.parent / "Screenshots/Gameplay_R01.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            self.screenshot_task = unreal.AutomationLibrary.take_high_res_screenshot(1600, 900, str(path), delay=0.3)
            probe["screenshot"] = str(path)
        if elapsed < probe["duration_game_seconds"]:
            if time.monotonic() - self.last_save > 1:
                self.save()
            return False
        for runtime_id, item in probe["casters"].items():
            self.require(item["observed_telegraph"] and item["observed_attack"] and len(item["projectile_ids"]) > 0,
                         "A rock caster did not visibly telegraph, attack and emit a real projectile within the observation", caster=runtime_id, item=item)
        self.require(str(encounter.get_failure_reason()) in ("None", "", "NAME_None"), "Actual R01 encounter reported a failure")
        self.stop_ai_probe_listeners()
        self.live_ai_ids.clear()
        for enemy in owned:
            enemy.set_lab_paused(True)
        self.vitals.restore_resource_preset(100.0, 100.0)
        probe["state"] = "passed"
        probe["success"] = True
        probe["no_navigation_failure"] = True
        self.save()
        return True

    def encounter_step(self, world):
        stage = self.stage_defs[self.stage_index]
        stage_id = stage.get_editor_property("stage_id")
        status = self.director.get_stage_status(stage_id)
        self.require(status != unreal.NLLevelStageState.FAILED, "Stage failed during real runtime", stage=str(stage_id), reason=str(self.director.get_failure_reason()))
        if status == unreal.NLLevelStageState.WARNING:
            self.current["warning_observed"] = True
            self.current["warning_remaining_max"] = max(self.current.get("warning_remaining_max", 0), self.director.get_warning_remaining())
            return
        if status == unreal.NLLevelStageState.COMPLETED:
            counts = self.completion_snapshots.get(str(stage_id))
            self.require(counts is not None and "error" not in counts, "Actual controller completion snapshot missing", snapshot=counts)
            self.require(counts["spawned"] == counts["defeated"] == counts["planned"] == self.current["expected_count"], "Completed-stage totals mismatch", counts=counts)
            self.require(counts["completed_waves"] == len(self.current["waves"]), "Completed wave count mismatch")
            # Deterministic random candidates may repeat an occupied point; bounded
            # collision retries are intentional. Require full completion, record retries.
            self.require(self.current["resolver_defeats"] == self.current["expected_count"], "Counted resolver defeats differ from stage budget")
            for wave in self.current["waves"]:
                self.require(wave["spawn_count"] == wave["resolver_defeats"] == wave["planned"], "Per-wave population mismatch", wave=wave)
                self.require(wave["max_alive_observed"] <= wave["max_alive_limit"], "Per-wave concurrency exceeded", wave=wave)
            self.current["state"] = "passed"
            self.current["runtime_totals"] = counts
            self.report["total_counted_spawns"] += counts["spawned"]
            self.report["total_resolver_defeats"] += counts["defeated"]
            self.unbind_completion(stage_id)
            self.stage_index += 1
            self.current = None
            self.phase = "stage_setup"
            self.save()
            return
        if status != unreal.NLLevelStageState.ACTIVE:
            self.require(time.monotonic() - self.phase_time < 20, "Stage did not auto-activate after entering its region", stage=str(stage_id), status=str(status))
            return
        self.current["state"] = "active"
        self.require(str(self.director.get_active_stage_id()) == str(stage_id), "Director activated an unexpected region")
        encounter = self.director.get_active_encounter()
        self.require(encounter is not None, "Active stage has no finite encounter controller")
        self.bind_completion_snapshot(encounter, stage_id)
        self.require(self.director.is_busy(), "Active stage did not hold the busy gate")
        if not self.current["busy_rejection_verified"]:
            if self.stage_index + 1 < len(self.stage_defs):
                next_stage = self.stage_defs[self.stage_index + 1]
                next_id = next_stage.get_editor_property("stage_id")
                self.require(self.director.get_stage_status(next_id) == unreal.NLLevelStageState.LOCKED, "Next region unlocked before its predecessor completed")
                self.move_player(self.stage_center_capsule(next_stage))
                accepted = self.director.try_activate_stage(next_id, self.pawn)
                self.require(not accepted and self.director.get_active_stage_id() == stage_id, "Busy gate permitted a second region")
                self.move_player(self.stage_center_capsule(stage))
                self.current["busy_next_stage_accepted"] = bool(accepted)
            self.current["busy_rejection_verified"] = True
        wave_index = encounter.get_wave_index()
        if wave_index < 0:
            return
        wave = self.current["waves"][wave_index]
        alive = encounter.get_alive_count()
        wave["max_alive_observed"] = max(wave["max_alive_observed"], alive)
        self.require(alive <= wave["max_alive_limit"], "Runtime alive cap exceeded", stage=str(stage_id), wave=wave_index, alive=alive)
        owned = [enemy for enemy in self.get_enemies(world) if encounter.owns_enemy(enemy)]
        for enemy in owned:
            runtime_id = self.guid_text(enemy.get_editor_property("combat_identity").get_runtime_id())
            if runtime_id not in self.seen_enemy_ids:
                self.seen_enemy_ids.add(runtime_id)
                wave["spawn_count"] += 1
        # Fill the real controller's concurrent budget before resolving a burst of
        # legal hits, so the run actually exercises four-alive limits where authored.
        threshold = min(wave["max_alive_limit"], wave["planned"] - wave["resolver_defeats"])
        if alive < threshold and encounter.get_current_wave_spawned_count() < wave["planned"]:
            return
        if str(stage_id) == "R01" and not self.observe_rock_ai(world, encounter, owned):
            return
        for enemy in owned:
            runtime_id = self.guid_text(enemy.get_editor_property("combat_identity").get_runtime_id())
            if runtime_id in self.killed_ids:
                continue
            game_time = self.world_time(world)
            if game_time - self.pending_kill_times.get(runtime_id, -1000) < 0.75:
                continue
            self.pending_kill_times[runtime_id] = game_time
            contact = self.make_contact(self.pawn, enemy, self.kill_definition)
            result = self.resolver.resolve_contact(self.pawn, enemy, contact, self.kill_definition)
            if enemy.get_editor_property("vitals").is_dead():
                self.require(result.get_editor_property("outcome") == unreal.NLCombatOutcome.HIT, "Defeat did not originate in a resolved hit")
                self.killed_ids.add(runtime_id)
                wave["resolver_defeats"] += 1
                self.current["resolver_defeats"] += 1
                enemy.set_lab_paused(False)
                master_id = stage.get_editor_property("master_id")
                if str(master_id) not in ("None", "", "NAME_None") and wave_index == len(self.current["waves"]) - 1:
                    self.verify_master_reward(master_id, enemy.get_actor_location())
        if time.monotonic() - self.last_save > 2:
            self.save()

    def cleanup_ledger(self):
        if self.ledger_file is None:
            self.report["cleanup"]["state"] = "not_needed"
            return
        root = self.LEDGER_DIR.resolve()
        target = self.ledger_file.resolve()
        self.require(os.path.commonpath((str(root), str(target))) == str(root) and target.parent == root,
                     "Test ledger path escapes intended directory")
        self.require(re.fullmatch(r"[0-9a-fA-F]{32}\.nlmr", target.name) is not None, "Unexpected test ledger filename")
        self.require(target.name.lower() not in {name.lower() for name in self.existing_ledgers}, "Refusing to remove pre-existing ledger")
        existed = target.exists()
        if existed:
            target.unlink()
        # SaveMasterLedger stages an exact same-run .tmp file. Never enumerate/delete other runs.
        temporary = Path(str(target) + ".tmp")
        temporary_existed = temporary.exists()
        if temporary_existed:
            temporary.unlink()
        self.report["cleanup"].update({"state": "passed", "file_existed": existed,
                                       "deleted_only_test_run": True, "removed_same_run_tmp": temporary_existed})

    def finish(self, error=None):
        if self.phase in ("ending", "finished"):
            return
        if error:
            self.report["failures"].append(error)
        self.report["state"] = "ending_play"
        self.phase = "ending"
        self.phase_time = time.monotonic()
        if self.movement:
            self.movement.stop_movement_immediately()
        for stage_id in list(self.completion_callbacks):
            self.unbind_completion(stage_id)
        self.stop_ai_probe_listeners()
        self.live_ai_ids.clear()
        # Do not keep PIE UObject references alive through end play / garbage collection.
        self.pawn = self.director = self.resolver = self.run = self.rewards = None
        self.vitals = self.recovery = self.guard = self.barrier = self.identity = None
        self.movement = self.kill_definition = self.parry_definition = None
        self.stage_defs = []
        if self.owns_play:
            self.level.editor_request_end_play()
        self.save()

    def tick(self, delta):
        if self.busy or self.phase == "finished":
            return
        self.busy = True
        try:
            now = time.monotonic()
            if self.phase == "ending":
                if self.owns_play and self.editor.get_game_world() is not None:
                    self.require(now - self.phase_time < 30, "PIE did not end before ledger cleanup")
                    return
                self.cleanup_ledger()
                for path in self.fixture_paths:
                    self.require(unreal.EditorAssetLibrary.delete_asset(path), "Cannot remove temporary fixture", path=path)
                self.fixture_paths.clear()
                self.report["success"] = not self.report["failures"] and len(self.report["stages"]) == 16
                self.report["state"] = "passed" if self.report["success"] else "failed"
                self.phase = "finished"
                self.save()
                if self.handle is not None:
                    unreal.unregister_slate_post_tick_callback(self.handle)
                    self.handle = None
                return
            self.require(now - self.began < self.DEADLINE_SECONDS, "Integration deadline exceeded", phase=self.phase, stage_index=self.stage_index)
            if self.phase == "start":
                self.require(self.editor.get_game_world() is None, "Stop existing PIE before running integration")
                # EditDefaultsOnly attack data require real asset flags in this UE Python build.
                # These uniquely named unsaved fixtures are deleted after PIE, never shipped.
                tools = unreal.AssetToolsHelpers.get_asset_tools()
                factory = unreal.DataAssetFactory()
                factory.set_editor_property("data_asset_class", unreal.NLAttackDefinition)
                suffix = str(int(time.time() * 1000))
                for attr, label, damage, block, parry, reflect in (
                    ("kill_definition", "ResolveOnly", 999.0, False, False, False),
                    ("parry_definition", "ReflectableBolt", 20.0, True, True, True),
                ):
                    path = "/Game/ReversedScale/Tests/TransientIntegration/DA_" + label + suffix
                    self.require(not unreal.EditorAssetLibrary.does_asset_exist(path), "Fixture already exists")
                    definition = tools.create_asset(path.rsplit("/", 1)[-1], path.rsplit("/", 1)[0], unreal.NLAttackDefinition, factory)
                    self.require(definition is not None, "Cannot create temporary attack asset")
                    self.fixture_paths.append(path)
                    definition.set_editor_property("stable_id", "Automation.EncounterRecovery." + label)
                    definition.set_editor_property("damage", damage)
                    definition.set_editor_property("can_be_blocked", block)
                    definition.set_editor_property("can_be_parried", parry)
                    definition.set_editor_property("can_be_reflected", reflect)
                    setattr(self, attr, definition)
                if not self.editor.get_editor_world().get_path_name().startswith(self.MAP + "."):
                    self.require(self.level.load_level(self.MAP), "Cannot load saved gameplay map")
                self.level.editor_request_begin_play()
                self.owns_play = True
                self.phase = "world_wait"
                self.phase_time = now
                return
            world = self.editor.get_game_world()
            if self.phase == "world_wait":
                if world is None or now - self.phase_time < 1.0:
                    self.require(now - self.phase_time < 30, "PIE world failed to start")
                    return
                self.require(self.MAP.rsplit("/", 1)[-1] in world.get_path_name(), "Unexpected PIE map")
                if not self.prepare_services(world):
                    self.require(now - self.phase_time < 30, "Possessed level player did not spawn")
                    return
                self.phase = "guard_setup"
            self.require(world is not None, "PIE ended unexpectedly")
            self.get_enemies(world)  # Pause every fresh AI immediately after its spawn grace.
            self.require(self.vitals is not None and not self.vitals.is_dead(), "Automation player died despite isolated AI")
            if self.phase in ("guard_setup", "ordinary_wait", "perfect_wait"):
                self.guard_probe(world)
                return
            if self.phase == "stage_setup":
                if self.stage_index == len(self.stage_defs):
                    self.require(self.director.get_completed_stage_count() == 16, "Not all 16 stages completed")
                    self.require(self.report["total_counted_spawns"] == self.report["total_resolver_defeats"] == len(self.killed_ids) == 109,
                                 "Final total differs from 109 normal resolver defeats")
                    self.require(sum(len(stage["waves"]) for stage in self.report["stages"]) == 27, "Final wave count differs from 27")
                    self.require(len(self.report["master_rewards"]) == 4, "Not all four master rewards were checked")
                    self.require(self.report["rock_r01_ai"]["state"] == "passed", "The real R01 caster-AI observation did not pass")
                    self.finish()
                    return
                self.start_stage_report()
                return
            if self.phase == "stage_wait":
                self.encounter_step(world)
        except Exception:
            failure = {"error": traceback.format_exc(), "phase": self.phase, "stage_index": self.stage_index}
            if self.phase == "ending":
                self.report["failures"].append(failure)
                self.report["state"] = "failed"
                self.report["success"] = False
                self.phase = "finished"
                self.save()
                if self.handle is not None:
                    unreal.unregister_slate_post_tick_callback(self.handle)
                    self.handle = None
            else:
                self.finish(failure)
        finally:
            self.busy = False

    def start(self):
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.save()


encounter_recovery_integration = EncounterRecoveryIntegration()
encounter_recovery_integration.start()

