import unreal,json
from pathlib import Path
result={"take_high_res_screenshot":unreal.AutomationLibrary.take_high_res_screenshot.__doc__,
        "get_player_camera_manager":unreal.GameplayStatics.get_player_camera_manager.__doc__}
Path(r'D:\game design\experiment\Docs\Gameplay\EncounterRecovery_v01\CaptureAPI.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
