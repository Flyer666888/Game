import sys,json,os,importlib
BASE=r'D:\game design\experiment\Scripts\Editor\Gameplay'
OUT=r'D:\game design\experiment\Docs\Gameplay\EncounterRecovery_v01'
sys.path.insert(0,BASE)
import navigation_setup_v01
importlib.reload(navigation_setup_v01)
previous=json.load(open(os.path.join(OUT,'NavigationBuild.json'),encoding='utf-8'))
areas=[{k:item[k] for k in ('name','center_m','size_m')} for item in previous['volumes']]
navigation_setup_v01.install_navigation(areas)
