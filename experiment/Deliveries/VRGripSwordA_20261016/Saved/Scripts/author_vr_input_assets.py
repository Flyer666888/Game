"""Author Nilin's OpenXR Enhanced Input assets without starting gameplay.

Run in the UE 5.8 Python commandlet before the first VR session. The default
context is registered in Config/DefaultInput.ini, so OpenXR can build its action
set before attaching the XR session. The VR pawn activates it at runtime.
"""
import json
from pathlib import Path
import unreal


ROOT = '/Game/ReversedScale/Player/VR/Input'
PROJECT = Path(unreal.Paths.project_dir())
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
ASSETS = unreal.EditorAssetLibrary

# Every asset this script may modify is explicitly listed here.
ACTION_SPECS = {
    'IA_VRMove': ('AXIS2D', 'Nilin left stick movement'),
    'IA_VRTurn': ('AXIS1D', 'Nilin right stick snap turn'),
    'IA_VRGuard': ('BOOLEAN', 'Nilin left trigger shield guard'),
    'IA_VRBladeQi': ('BOOLEAN', 'Nilin right trigger blade qi'),
    'IA_VRStart': ('BOOLEAN', 'Nilin start encounter'),
    'IA_VRReset': ('BOOLEAN', 'Nilin restore checkpoint'),
    'IA_VRPause': ('BOOLEAN', 'Nilin pause or resume encounter'),
    'IA_VRTrackpadMove': ('AXIS2D', 'Nilin pressed left trackpad movement'),
    'IA_VRTrackpadTurn': ('AXIS1D', 'Nilin pressed right trackpad snap turn'),
    'IA_VRTrackpadMoveClick': ('BOOLEAN', 'Nilin left trackpad press gate'),
    'IA_VRTrackpadTurnClick': ('BOOLEAN', 'Nilin right trackpad press gate'),
    # HP's built-in controller plugin exports scalar stick keys, no paired 2D
    # key. Separate float actions keep the OpenXR binding types compatible.
    'IA_VRMoveRight': ('AXIS1D', 'Nilin HP left stick strafe'),
    'IA_VRMoveForward': ('AXIS1D', 'Nilin HP left stick forward'),
}
EXPECTED = set(ACTION_SPECS) | {'IMC_NilinVR'}
created = []
skipped = []
records = []


def own_asset(name, cls):
    if name not in EXPECTED:
        raise RuntimeError('Refusing to modify an unowned input asset: ' + name)
    destination = ROOT + '/' + name
    value = ASSETS.load_asset(destination) if ASSETS.does_asset_exist(destination) else None
    if value and not isinstance(value, cls):
        raise RuntimeError('Unexpected existing asset class at ' + destination)
    if not value:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property('data_asset_class', cls)
        value = TOOLS.create_asset(name, ROOT, cls, factory)
        if not value:
            raise RuntimeError('Could not create ' + destination)
        created.append(destination)
    return value


def dead_zone(outer, threshold):
    modifier = unreal.new_object(unreal.InputModifierDeadZone, outer=outer)
    modifier.set_editor_property('lower_threshold', threshold)
    modifier.set_editor_property('upper_threshold', 1.0)
    modifier.set_editor_property('type', unreal.DeadZoneType.RADIAL)
    return modifier


ASSETS.make_directory(ROOT)
actions = {}
for name, (value_type, description) in ACTION_SPECS.items():
    action = own_asset(name, unreal.InputAction)
    action.set_editor_property('value_type', getattr(unreal.InputActionValueType, value_type))
    action.set_editor_property('action_description', description)
    action.set_editor_property('trigger_when_paused', name in ('IA_VRPause', 'IA_VRReset'))
    action.set_editor_property('consume_input', not name.endswith('Click'))
    action.set_editor_property('consumes_action_and_axis_mappings', False)
    action.set_editor_property('triggers', [])
    modifiers = []
    if name in ('IA_VRMove', 'IA_VRTrackpadMove'):
        modifiers.append(dead_zone(action, 0.18))
    elif name in ('IA_VRTurn', 'IA_VRTrackpadTurn'):
        modifiers.append(dead_zone(action, 0.15))
    elif name in ('IA_VRMoveRight', 'IA_VRMoveForward'):
        modifiers.append(dead_zone(action, 0.18))
    action.set_editor_property('modifiers', modifiers)
    actions[name] = action


context = own_asset('IMC_NilinVR', unreal.InputMappingContext)
context.set_editor_property('context_description', 'Nilin VR combat controls')
context.set_editor_property('input_mode_filter_options',
                            unreal.MappingContextInputModeFilterOptions.DO_NOT_FILTER)
mappings = []


def map_key(action_name, key_name, chord=None):
    key = unreal.Key()
    key.set_editor_property('key_name', unreal.Name(key_name))
    if not unreal.InputLibrary.key_is_valid(key):
        skipped.append({'action': action_name, 'key': key_name,
                        'reason': 'Input key is not registered by an enabled engine plugin.'})
        return
    mapping = unreal.EnhancedActionKeyMapping()
    mapping.set_editor_property('action', actions[action_name])
    mapping.set_editor_property('key', key)
    if chord:
        trigger = unreal.new_object(unreal.InputTriggerChordAction, outer=context)
        trigger.set_editor_property('chord_action', actions[chord])
        mapping.set_editor_property('triggers', [trigger])
    mappings.append(mapping)
    records.append({'action': action_name, 'key': key_name, 'chord_action': chord})


# Paired 2D keys produce OpenXR vector2 actions bound to /input/thumbstick.
# Binding a vector2 action to separate /x and /y float paths is deliberately
# avoided: the runtime must receive a type-compatible suggested binding.
for profile in ('ValveIndex', 'OculusTouch', 'MixedReality', 'PICO'):
    map_key('IA_VRMove', profile + '_Left_Thumbstick_2D')
    map_key('IA_VRTurn', profile + '_Right_Thumbstick_X')
    map_key('IA_VRGuard', profile + '_Left_Trigger_Click')
    map_key('IA_VRBladeQi', profile + '_Right_Trigger_Click')

for profile in ('OculusTouch', 'PICO', 'HPMixedRealityController'):
    map_key('IA_VRStart', profile + '_Right_A_Click')
    map_key('IA_VRStart', profile + '_Left_X_Click')
    map_key('IA_VRReset', profile + '_Right_B_Click')
    map_key('IA_VRPause', profile + '_Left_Y_Click')

map_key('IA_VRStart', 'ValveIndex_Right_A_Click')
map_key('IA_VRStart', 'ValveIndex_Left_A_Click')
map_key('IA_VRReset', 'ValveIndex_Right_B_Click')
map_key('IA_VRPause', 'ValveIndex_Left_B_Click')

# WMR wands have no face buttons: use menu for start, grip for reset and left
# menu for pause. None of these keys is the controller's reserved system key.
for profile in ('Vive', 'MixedReality'):
    map_key('IA_VRStart', profile + '_Right_Menu_Click')
    map_key('IA_VRReset', profile + '_Right_Grip_Click')
    map_key('IA_VRPause', profile + '_Left_Menu_Click')
    map_key('IA_VRTrackpadMoveClick', profile + '_Left_Trackpad_Click')
    map_key('IA_VRTrackpadTurnClick', profile + '_Right_Trackpad_Click')
    map_key('IA_VRTrackpadMove', profile + '_Left_Trackpad_2D', 'IA_VRTrackpadMoveClick')
    map_key('IA_VRTrackpadTurn', profile + '_Right_Trackpad_X', 'IA_VRTrackpadTurnClick')

map_key('IA_VRGuard', 'Vive_Left_Trigger_Click')
map_key('IA_VRBladeQi', 'Vive_Right_Trigger_Click')
map_key('IA_VRMoveRight', 'HPMixedRealityController_Left_Thumbstick_X')
map_key('IA_VRMoveForward', 'HPMixedRealityController_Left_Thumbstick_Y')
map_key('IA_VRTurn', 'HPMixedRealityController_Right_Thumbstick_X')
map_key('IA_VRGuard', 'HPMixedRealityController_Left_Trigger_Click')
map_key('IA_VRBladeQi', 'HPMixedRealityController_Right_Trigger_Click')

# In UE5.8, UInputMappingContext::Mappings is deprecated. Author its supported
# DefaultKeyMappings struct, replacing only this dedicated context's mappings.
mapping_data = unreal.InputMappingContextMappingData()
mapping_data.set_editor_property('mappings', mappings)
context.set_editor_property('default_key_mappings', mapping_data)

for value in list(actions.values()) + [context]:
    if not ASSETS.save_loaded_asset(value, False):
        raise RuntimeError('Could not save ' + value.get_path_name())

report = {
    'task': 'SteamVR through OpenXR Enhanced Input',
    'date': '2026-10-15',
    'authoring_only': True,
    'runtime_hardware_validation': 'Pending user VR play',
    'context': context.get_path_name(),
    'native_action_paths': {name: value.get_path_name() for name, value in actions.items()},
    'actions': {name: {'value_type': spec[0], 'description': spec[1],
                       'trigger_when_paused': name in ('IA_VRPause', 'IA_VRReset')}
                for name, spec in ACTION_SPECS.items()},
    'mappings': records,
    'mapping_count': len(records),
    'optional_keys_skipped': skipped,
    'created_assets': created,
    'openxr_registration': {
        'config': 'Config/DefaultInput.ini',
        'section': '/Script/EnhancedInput.EnhancedInputDeveloperSettings',
        'property': 'DefaultMappingContexts',
        'priority': 100,
        'bAddImmediately': False,
        'activation': 'ANLVRPlayerCharacter adds the context when possessed',
        'engine_source': 'OpenXRInput.cpp BuildActions loads the default contexts before BuildEnhancedActions',
    },
    'input_type_notes': {
        'move': '2D paired XR keys; X is strafe right, Y is forward; no axis inversion',
        'hp_move': 'Separate float actions; built-in HP plugin does not register a paired 2D key',
        'vive_trackpad': 'Trackpad movement and turn require their hand trackpad click action',
        'turn': 'Axis1D right thumbstick X or pressed right trackpad X, native pawn applies snap turn',
        'system_button': 'Unmapped; SteamVR reserved system controls stay with the runtime',
    },
    'engine_sources_reviewed': [
        'Plugins/Runtime/OpenXR/Source/OpenXRInput/Private/OpenXRInput.cpp',
        'Plugins/EnhancedInput/Source/EnhancedInput/Public/EnhancedInputDeveloperSettings.h',
        'Plugins/EnhancedInput/Source/EnhancedInput/Public/InputMappingContext.h',
        'Plugins/EnhancedInput/Source/EnhancedInput/Public/InputAction.h',
        'Plugins/EnhancedInput/Source/EnhancedInput/Public/InputModifiers.h',
        'Plugins/EnhancedInput/Source/EnhancedInput/Public/InputTriggers.h',
        'Source/Runtime/InputCore/Private/InputCoreTypes.cpp',
        'Plugins/Runtime/PICOController/Source/PICOController/Private/PICOController.cpp',
        'Plugins/Runtime/HPMotionController/Source/HPMotionController/Private/HPMotionController.cpp',
    ],
}
destination = PROJECT / 'Docs' / 'AI' / 'VRInputAssets-2026-10-15.json'
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('Nilin VR input assets saved: ' + str(destination))
