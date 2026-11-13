"""Capture the saved R01 jade-talisman cast from two observer viewpoints."""

import json
from pathlib import Path

import unreal


PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUTPUT = PROJECT / "Docs/Gameplay/JadeTalismanCast1104"
SOURCE = PROJECT / "Scripts/Editor/RangedDemo1104/capture_ranged_demo.py"
context = {"__name__": "jade_cast_ranged_helper", "__file__": str(SOURCE)}
source = SOURCE.read_text(encoding="utf-8-sig")
assert "demo = RangedDemo()" in source
exec(compile(source.replace("demo = RangedDemo()", ""), str(SOURCE), "exec"), context)
context["output"] = OUTPUT


def asset_path(asset):
    return asset.get_path_name() if asset else None


def vector(value):
    return [value.x, value.y, value.z]


def visual_snapshot(component):
    if component is None:
        return None
    transform = component.get_world_transform()
    return {
        "position_cm": vector(transform.translation),
        "scale": vector(transform.scale3d),
        "mesh": asset_path(component.get_editor_property("static_mesh")),
        "materials": [asset_path(component.get_material(i)) for i in range(component.get_num_materials())],
        "visible": component.is_visible() and not component.get_editor_property("hidden_in_game"),
    }


def socket_snapshot(mesh, name):
    if not mesh.does_socket_exist(name):
        return None
    transform = mesh.get_socket_transform(name, unreal.RelativeTransformSpace.RTS_WORLD)
    q = transform.rotation
    return {
        "name": str(name),
        "position_cm": vector(transform.translation),
        "rotation_xyzw": [q.x, q.y, q.z, q.w],
        "scale": vector(transform.scale3d),
    }


class JadeCastDemo(context["RangedDemo"]):
    def bootstrap(self):
        super().bootstrap()
        if self.phase != "stage_active":
            return
        options = OUTPUT / "Camera.json"
        self.camera_options = json.loads(options.read_text(encoding="utf-8-sig")) if options.exists() else {}
        assert self.camera_options.get("mode", "two_phase") in ("wide", "close", "two_phase")
        self.duration = float(self.camera_options.get("duration_seconds", 9.0))
        assert 8.0 <= self.duration <= 12.0
        self.report["scope"] = (
            "Saved main level, two native R01 talisman casters. Prior encounters cleared with a test hit fixture. "
            "Stationary player on the authored route. Observer cameras and capture pacing only."
        )
        self.projectile_records = {}
        self.focus_enemy = None
        self.focus_locked = False
        self.began_flight = False

    def prepare_camera(self, enemies):
        super().prepare_camera(enemies)
        self.wide_position = unreal.Vector(*self.camera_options.get("wide_position_cm", [-450, 3900, 1225]))
        self.wide_target = unreal.Vector(*self.camera_options.get("wide_target_cm", [-570, 4630, 920]))
        self.focus_enemy = min(enemies, key=lambda enemy: (
            enemy.get_actor_location() - self.pawn.get_actor_location()).length())
        self.report["caster_settings"] = [self.caster_settings(enemy) for enemy in enemies]
        self.report["camera_options"] = self.camera_options

    def caster_settings(self, enemy):
        attack = enemy.get_editor_property("talisman_attack")
        return {
            "id": self.guid(enemy.combat_identity.get_runtime_id()),
            "class": enemy.get_class().get_name(),
            "float_before_hand": attack.get_editor_property("float_before_hand"),
            "talisman_mesh": asset_path(attack.get_editor_property("talisman_mesh")),
            "floating_hand_distance_cm": attack.get_editor_property("floating_hand_distance_cm"),
            "floating_orb_distance_cm": attack.get_editor_property("floating_orb_distance_cm"),
            "muzzle_socket": str(attack.get_editor_property("muzzle_socket_name")),
            "cast_glow_material": asset_path(attack.get_editor_property("cast_glow_material")),
            "projectile_material": asset_path(attack.get_editor_property("projectile_material")),
            "cast_animation": asset_path(enemy.get_editor_property("cast_animation")),
        }

    def caster_snapshot(self, enemy):
        attack = enemy.get_editor_property("talisman_attack")
        mesh = enemy.get_component_by_class(unreal.SkeletalMeshComponent)
        return {
            "id": self.guid(enemy.combat_identity.get_runtime_id()),
            "actor_position_cm": vector(enemy.get_actor_location()),
            "right_hand": socket_snapshot(mesh, "RightHand") or socket_snapshot(mesh, "hand_r"),
            "muzzle_socket": socket_snapshot(mesh, attack.get_editor_property("muzzle_socket_name")),
            "muzzle_position_cm": vector(attack.get_muzzle_position()),
            "talisman_visual": visual_snapshot(attack.get_editor_property("talisman_visual")),
            "cast_glow": visual_snapshot(attack.get_editor_property("cast_glow")),
        }

    def observe_projectiles(self, enemies, elapsed):
        rows = []
        for projectile in unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.NLCombatProjectile):
            if not self.valid(projectile):
                continue
            source = projectile.get_source_actor()
            if source not in enemies:
                continue
            key = self.guid(projectile.get_attack_instance_id())
            self.projectile_ids.add(key)
            row = {
                "id": key,
                "source_id": self.guid(source.combat_identity.get_runtime_id()),
                "source_actor": source.get_name(),
                "position_cm": vector(projectile.get_actor_location()),
                "assigned_material": asset_path(projectile.get_editor_property("visual_material")),
                "visual": visual_snapshot(projectile.get_editor_property("visual")),
            }
            self.projectile_records.setdefault(key, {**row, "first_observed_t": elapsed})
            rows.append(row)
        return rows

    def update_camera(self, enemies, states):
        mode = self.camera_options.get("mode", "two_phase")
        if mode == "wide" or (mode == "two_phase" and self.began_flight):
            position, target = self.wide_position, self.wide_target
            self.pawn.player_camera.set_field_of_view(float(self.camera_options.get("wide_fov", 86)))
            shot = "flight_wide"
        else:
            if not self.focus_locked:
                first_caster = next((enemy for enemy, state in zip(enemies, states) if "TELEGRAPH" in state), None)
                if first_caster:
                    self.focus_enemy = first_caster
                    self.focus_locked = True
            enemy = self.focus_enemy
            actor_position = enemy.get_actor_location()
            forward = self.pawn.get_actor_location() - actor_position
            forward.z = 0.0
            forward = forward * (1.0 / max(forward.length(), 1.0))
            right = unreal.Vector(-forward.y, forward.x, 0)
            attack = enemy.get_editor_property("talisman_attack")
            talisman = attack.get_editor_property("talisman_visual")
            center = talisman.get_world_location() if talisman else attack.get_muzzle_position()
            target = center * .65 + (actor_position + unreal.Vector(0, 0, 50)) * .35
            position = (
                target
                + forward * float(self.camera_options.get("close_forward_cm", 210))
                + right * float(self.camera_options.get("close_right_cm", 150))
                + unreal.Vector(0, 0, float(self.camera_options.get("close_height_cm", 80)))
            )
            self.pawn.player_camera.set_field_of_view(float(self.camera_options.get("close_fov", 50)))
            shot = "charge_close"
        self.camera_position = position
        self.camera_rotation = unreal.MathLibrary.find_look_at_rotation(position, target)
        self.apply_camera()
        return shot, vector(position), vector(target)

    def end_recording(self):
        hits = [
            row for row in self.report["combat_results"]
            if row["origin"] == "engine_physical" and row["source_id"] in self.caster_ids
            and row["target_id"] == self.player_id and row["damage"] > 0
        ]
        hit_sources = {row["source_id"] for row in hits}
        settings = {row["id"]: row for row in self.report["caster_settings"]}
        charged_sources = set()
        for frame in self.frames:
            for row in frame["caster_visuals"]:
                talisman, glow = row["talisman_visual"], row["cast_glow"]
                if talisman and talisman["visible"] and talisman["mesh"] == settings[row["id"]]["talisman_mesh"] \
                        and glow and glow["visible"]:
                    charged_sources.add(row["id"])
        self.report["hit_caster_count"] = len(hit_sources)
        self.report["hit_caster_ids"] = sorted(hit_sources)
        self.report["projectile_count"] = len(self.projectile_ids)
        self.report["native_projectiles"] = list(self.projectile_records.values())
        self.report["health_after"] = self.vitals.get_health()
        self.report["checks"] = {
            "both_live_casters": len(self.caster_ids) == 2,
            "both_use_floating_jade_talismans": all(
                row["float_before_hand"] and row["talisman_mesh"] and row["floating_hand_distance_cm"] > 0
                and row["floating_orb_distance_cm"] > 0 for row in settings.values()),
            "both_charge_with_visible_authored_talisman": charged_sources == self.caster_ids,
            "both_native_casters_hit_player": hit_sources == self.caster_ids,
            "native_orb_uses_configured_material": bool(self.projectile_records) and all(
                row["assigned_material"] and row["assigned_material"] == settings[row["source_id"]]["projectile_material"]
                and row["visual"] and row["assigned_material"] in row["visual"]["materials"]
                for row in self.projectile_records.values()),
            "projectile_in_capture": any(frame["projectiles"] for frame in self.frames),
            "recorded_frames": len(self.frames) >= 60,
        }
        unreal.GameplayStatics.set_global_time_dilation(self.world, 1.0)
        self.skip_damage = None
        self.focus_enemy = None
        self.finish()

    def record(self, enemies):
        elapsed = self.now() - self.record_start
        assert len(enemies) == 2 and not self.vitals.is_dead(), "Unexpected R01 outcome during recording"
        states = [str(enemy.get_enemy_brain().get_state()) for enemy in enemies]
        projectile_rows = self.observe_projectiles(enemies, elapsed)
        self.began_flight = self.began_flight or bool(projectile_rows)
        shot, camera_position, camera_target = self.update_camera(enemies, states)
        if self.pending_frame:
            if not Path(self.pending_frame["file"]).is_file():
                return
            self.frames.append(self.pending_frame)
            self.pending_frame = None
        if elapsed >= self.duration:
            self.end_recording()
            return
        if self.frames and elapsed - self.frames[-1]["t"] < 1 / 20:
            return
        path = self.record_dir / f"frame_{len(self.frames):04d}.png"
        self.pending_frame = {
            "file": str(path),
            "t": elapsed,
            "shot": shot,
            "camera_position_cm": camera_position,
            "camera_target_cm": camera_target,
            "states": states,
            "hp": self.vitals.get_health(),
            "projectiles": [row["position_cm"] for row in projectile_rows],
            "projectile_visuals": projectile_rows,
            "caster_visuals": [self.caster_snapshot(enemy) for enemy in enemies],
        }
        self.screenshot_tasks.append(unreal.AutomationLibrary.take_high_res_screenshot(1280, 720, str(path)))


demo = JadeCastDemo()
