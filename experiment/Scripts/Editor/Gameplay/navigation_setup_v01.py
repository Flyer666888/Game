"""Bounded local navigation for L_NilinGameplayV01, using verified UE 5.8 editor APIs.

This module does nothing on import. ``install_navigation(areas)`` creates factory-
built brush volumes and schedules the remaining work on Slate ticks. Inspect
``get_navigation_install_report()`` until state is ``ready_for_validation`` or
``failed``; then independently verify floor projection and actual enemy paths.
The caller owns saving the new map after this helper finishes.

Local UE source checks behind the implementation:
* UnrealEd/Private/Subsystems/EditorActorSubsystem.cpp, SpawnActor: editor placement
  goes through TryPlacingActorFromObject and the actor factory.
* UnrealEd/Private/Factories/ActorFactory.cpp, UActorFactoryBoxVolume::PostSpawnActor
  and CreateBrushForVolumeActor: the volume factory builds a real UCubeBuilder box.
* UnrealEd/Private/EditorBrushBuilder.cpp, UCubeBuilder constructor: 200 cm box.
  CubeBuilder.Build itself is NOT a UFUNCTION, so this helper never calls a guessed
  Python ``CubeBuilder.build`` method.
* NavigationSystem/Public/NavMesh/RecastNavMesh.h: UE 5.8 uses the fixed array
  NavMeshResolutionParams; the old CellSize/CellHeight properties are deprecated.
* PythonScriptPlugin/Private/PyWrapperFixedArray.cpp: use a list to preserve all
  three fixed-array resolutions in this build.
* UnrealEd/Private/UnrealEdSrv.cpp: the official command is BUILDPATHS, no space.
  It reaches FEditorBuildUtils::BuildAIPaths. NavigationSystemV1::Build currently
  calls EnsureBuildCompletion, so this explicit command can briefly block its tick.
  Slate polling also waits for subsequent dirty-area/dynamic work to settle.
* NavigationSystem.h: GetNavigationSystem, OnNavigationBoundsUpdated,
  IsNavigationBeingBuiltOrLocked, ProjectPointToNavigation and synchronous path
  finding are reflected UFUNCTIONs.
"""

from __future__ import annotations

import copy
import math
import re
import time
import traceback


EXPECTED_MAP = "/Game/ReversedScale/Maps/L_NilinGameplayV01"
MANAGED_TAG = "NLGameplay.NavigationV01"
HORIZONTAL_MARGIN_M = 4.0
VERTICAL_MARGIN_M = 10.0
_SESSION = None
_TICK_HANDLE = None


def _vector_list(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def _checked_areas(areas):
    result = []
    names = set()
    for source in areas:
        name = str(source["name"])
        if not name or name in names:
            raise ValueError("Navigation area names must be nonempty and unique")
        names.add(name)
        center = [float(value) for value in source["center_m"]]
        size = [float(value) for value in source["size_m"]]
        if len(center) != 3 or len(size) != 3 or not all(math.isfinite(value) for value in center + size):
            raise ValueError(f"{name}: center_m and size_m must have three finite components")
        if min(size[:2]) <= 0.0 or size[2] < 0.0:
            raise ValueError(f"{name}: XY size must be positive and Z size nonnegative")
        if max(size[:2]) > 250.0:
            raise ValueError(f"{name}: split this area into local encounter bounds; XY size exceeds 250 m")
        padded_size = [size[0] + 2.0 * HORIZONTAL_MARGIN_M,
                       size[1] + 2.0 * HORIZONTAL_MARGIN_M,
                       size[2] + 2.0 * VERTICAL_MARGIN_M]
        result.append({"name": name, "center_m": center, "size_m": size, "padded_size_m": padded_size})
    if not result or len(result) > 32:
        raise ValueError("Provide between 1 and 32 local navigation regions")
    if sum(area["padded_size_m"][0] * area["padded_size_m"][1] for area in result) > 150000.0:
        raise ValueError("Navigation coverage exceeds the bounded encounter-area budget")
    return result


def _current_editor_world(unreal):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world():
        raise RuntimeError("Stop PIE before installing navigation")
    world = editor.get_editor_world()
    if world is None:
        raise RuntimeError("No editor world is loaded")
    package = world.get_path_name().split(".", 1)[0]
    if package != EXPECTED_MAP:
        raise RuntimeError(f"Refusing to change {package}; expected independent map {EXPECTED_MAP}")
    return world


def _recast_actors(unreal, actor_subsystem):
    return [actor for actor in actor_subsystem.get_all_level_actors() if isinstance(actor, unreal.RecastNavMesh)]


def _configure_recast(unreal, navmesh):
    values = {
        "runtime_generation": unreal.RuntimeGenerationType.STATIC,
        "force_rebuild_on_load": False,
        "fixed_tile_pool_size": True,
        "tile_pool_size": 2048,
        "tile_number_hard_limit": 4096,
        "tile_size_uu": 1000.0,
        "agent_radius": 28.0,
        "agent_height": 176.0,
        "agent_max_slope": 45.0,
        # Raised sentry rocks are valid small, disconnected islands.
        "min_region_area": 0.0,
        "max_simultaneous_tile_generation_jobs_count": 2,
    }
    for name, value in values.items():
        if name == "runtime_generation":
            # Recast's RuntimeGeneration editor notification writes DefaultEngine.ini.
            # Keep this policy local to the independent static blockout map.
            navmesh.set_editor_property(name, value, unreal.PropertyAccessChangeNotifyMode.NEVER)
        else:
            navmesh.set_editor_property(name, value)
    # FixedArray.copy loses ArrayDim in this UE Python build. A list preserves all three resolutions.
    resolutions = list(navmesh.get_editor_property("nav_mesh_resolution_params"))
    if len(resolutions)!=3:
        raise RuntimeError("Expected Low, Default and High navigation resolutions")
    for index in range(len(resolutions)):
        resolution = resolutions[index]
        resolution.set_editor_property("cell_size", 20.0)
        resolution.set_editor_property("cell_height", 5.0)
        resolution.set_editor_property("agent_max_step_height", 35.0)
        resolutions[index] = resolution
    navmesh.set_editor_property("nav_mesh_resolution_params", resolutions)
    readback = []
    for resolution in navmesh.get_editor_property("nav_mesh_resolution_params"):
        readback.append({"cell_size_cm": float(resolution.get_editor_property("cell_size")),
                         "cell_height_cm": float(resolution.get_editor_property("cell_height")),
                         "max_step_height_cm": float(resolution.get_editor_property("agent_max_step_height"))})
    if any(abs(item["cell_size_cm"] - 20.0) > 0.01 or abs(item["cell_height_cm"] - 5.0) > 0.01 for item in readback):
        raise RuntimeError(f"NavMesh resolution readback mismatch: {readback}")
    return {"actor": navmesh.get_path_name(),
            "runtime_generation": str(navmesh.get_editor_property("runtime_generation")),
            "tile_size_cm": float(navmesh.get_editor_property("tile_size_uu")),
            "tile_pool_size": int(navmesh.get_editor_property("tile_pool_size")),
            "agent_radius_cm": float(navmesh.get_editor_property("agent_radius")),
            "agent_height_cm": float(navmesh.get_editor_property("agent_height")),
            "resolutions": readback}


def get_navigation_install_report():
    """JSON-compatible snapshot. ``ready_for_validation`` means building settled, not proven path coverage."""
    return copy.deepcopy(_SESSION["report"]) if _SESSION else {"state": "not_started"}


def _stop_tick(unreal):
    global _TICK_HANDLE
    if _TICK_HANDLE is not None:
        unreal.unregister_slate_post_tick_callback(_TICK_HANDLE)
        _TICK_HANDLE = None


def _navigation_tick(delta_seconds):
    import unreal

    if _SESSION is None:
        _stop_tick(unreal)
        return
    report = _SESSION["report"]
    try:
        world = _current_editor_world(unreal)
        elapsed = time.monotonic() - _SESSION["started"]
        report["elapsed_seconds"] = round(elapsed, 3)
        if elapsed > 120.0:
            raise TimeoutError("Navigation did not settle within 120 seconds")
        nav_system = unreal.NavigationSystemV1.get_navigation_system(world)
        if nav_system is None:
            raise RuntimeError("This world has no NavigationSystemV1; no build can be claimed")
        if report["state"] == "waiting_for_nav_data":
            recasts = _recast_actors(unreal, _SESSION["actors"])
            if not recasts:
                # Volume-bound update processing creates the default nav data on an editor tick.
                if elapsed > 15.0:
                    raise RuntimeError("No RecastNavMesh was auto-created after valid navigation bounds")
                return
            report["navmeshes"] = [_configure_recast(unreal, navmesh) for navmesh in recasts]
            nav_system.set_max_simultaneous_tile_generation_jobs_count(2)
            report["state"] = "building"
            report["commands"].append("BUILDPATHS")
            # Official BuildAIPaths command, scoped to the editor world guarded above.
            unreal.SystemLibrary.execute_console_command(world, "BUILDPATHS")
            _SESSION["stable_ticks"] = 0
            return
        busy = bool(unreal.NavigationSystemV1.is_navigation_being_built_or_locked(world))
        report["navigation_being_built_or_locked"] = busy
        _SESSION["stable_ticks"] = 0 if busy else _SESSION["stable_ticks"] + 1
        if _SESSION["stable_ticks"] >= 3:
            report["state"] = "ready_for_validation"
            report["requires_floor_and_path_validation"] = True
            report["requires_map_save"] = True
            _stop_tick(unreal)
    except Exception as exc:
        report["state"] = "failed"
        report["error"] = str(exc)
        report["traceback"] = traceback.format_exc()
        unreal.log_error(f"Navigation setup failed: {exc}")
        _stop_tick(unreal)


def install_navigation(areas):
    """Install local volumes around supplied encounter footprints, then build on editor ticks.

    Input: ``[{"name": "GM01", "center_m": [x,y,z], "size_m": [width,depth,height]}, ...]``.
    Size is a full extent; horizontal padding is 4 m per side, vertical padding
    10 m above and below the supplied footprint. No global enclosing box is added.
    Existing untagged volumes are preserved and reported; only this helper's tagged
    volumes are replaced on repeat installation in the independent gameplay map.
    """
    global _SESSION, _TICK_HANDLE
    import unreal

    checked = _checked_areas(areas)
    if _TICK_HANDLE is not None:
        raise RuntimeError("A navigation installation is already running")
    world = _current_editor_world(unreal)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    nav_system = unreal.NavigationSystemV1.get_navigation_system(world)
    if nav_system is None:
        raise RuntimeError("The gameplay world has no NavigationSystemV1")
    report = {"state": "installing_volumes", "map": EXPECTED_MAP, "volumes": [],
              "preserved_untagged_volumes": [], "commands": [],
              "coverage_area_m2_without_overlap_deduction": round(sum(
                  area["padded_size_m"][0] * area["padded_size_m"][1] for area in checked), 2),
              "limitations": ["No floor projection or pathfinding success is inferred from build completion.",
                              "BUILDPATHS calls EnsureBuildCompletion in this engine and can briefly block its tick.",
                              "The caller must save L_NilinGameplayV01 after ready_for_validation."]}
    _SESSION = {"actors": actors, "report": report, "started": time.monotonic(), "stable_ticks": 0}
    try:
        for actor in actors.get_all_level_actors():
            if not isinstance(actor, unreal.NavMeshBoundsVolume):
                continue
            if MANAGED_TAG in {str(tag) for tag in actor.tags}:
                if not actors.destroy_actor(actor):
                    raise RuntimeError(f"Could not replace managed volume {actor.get_path_name()}")
            else:
                report["preserved_untagged_volumes"].append(actor.get_path_name())
                _, extent = actor.get_actor_bounds(False)
                size_m = [component * 0.02 for component in _vector_list(extent)]
                if max(size_m[:2]) > 250.0:
                    raise RuntimeError(f"Existing untagged navigation bounds are too large for a local build: {actor.get_path_name()}")
        nav_system.set_editor_property("auto_create_navigation_data", True)
        if nav_system.get_editor_property("generate_navigation_only_around_navigation_invokers"):
            raise RuntimeError("This level requires full local bounds, but the navigation system is configured for invokers only")
        for area in checked:
            center_cm = [value * 100.0 for value in area["center_m"]]
            target_size_cm = [value * 100.0 for value in area["padded_size_m"]]
            volume = actors.spawn_actor_from_class(unreal.NavMeshBoundsVolume, unreal.Vector(*center_cm))
            if volume is None:
                raise RuntimeError(f"Volume factory failed for {area['name']}")
            volume.set_actor_label("NG_Nav_" + re.sub(r"[^A-Za-z0-9_]+", "_", area["name"]))
            volume.set_folder_path("Nilin_GameplayV01/Navigation")
            volume.tags = list(volume.tags) + [unreal.Name(MANAGED_TAG)]
            volume.set_actor_scale3d(unreal.Vector(1.0, 1.0, 1.0))
            default_origin, default_extent = volume.get_actor_bounds(False)
            default_size_cm = [value * 2.0 for value in _vector_list(default_extent)]
            if not all(math.isfinite(value) and value > 0.01 for value in default_size_cm):
                raise RuntimeError(f"{area['name']}: actor factory did not produce a nonzero brush: {default_size_cm}")
            volume.set_actor_scale3d(unreal.Vector(*[target_size_cm[index] / default_size_cm[index] for index in range(3)]))
            # Scale around the factory origin, then account for any brush-origin offset.
            scaled_origin, scaled_extent = volume.get_actor_bounds(False)
            correction = unreal.Vector(*center_cm) - scaled_origin
            volume.set_actor_location(volume.get_actor_location() + correction, False, False)
            final_origin, final_extent = volume.get_actor_bounds(False)
            final_size_cm = [value * 2.0 for value in _vector_list(final_extent)]
            if any(abs(final_size_cm[index] - target_size_cm[index]) > 2.0 for index in range(3)):
                raise RuntimeError(f"{area['name']}: scaled brush bounds do not match requested coverage")
            if any(abs(_vector_list(final_origin)[index] - center_cm[index]) > 2.0 for index in range(3)):
                raise RuntimeError(f"{area['name']}: brush world centre does not match requested coverage")
            nav_system.on_navigation_bounds_updated(volume)
            report["volumes"].append({**area, "actor": volume.get_path_name(),
                                      "factory_brush_size_cm": default_size_cm,
                                      "world_center_cm": _vector_list(final_origin),
                                      "world_size_cm": final_size_cm})
        # BSP rebuild is official but is not itself a navigation build.
        report["commands"].append("MAP REBUILD")
        unreal.SystemLibrary.execute_console_command(world, "MAP REBUILD")
        report["state"] = "waiting_for_nav_data"
        _TICK_HANDLE = unreal.register_slate_post_tick_callback(_navigation_tick)
    except Exception as exc:
        report["state"] = "failed"
        report["error"] = str(exc)
        report["traceback"] = traceback.format_exc()
        raise
    return get_navigation_install_report()
