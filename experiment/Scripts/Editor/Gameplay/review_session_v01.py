"""Project-scoped editor worker for encounter/recovery authoring and validation."""
import unreal,json,os,time,traceback
BASE=r'D:\game design\experiment\Scripts\Editor\Gameplay'
OUT=r'D:\game design\experiment\Docs\Gameplay\EncounterRecovery_v01'
last_revision=None;busy=False;handle=None;started=time.monotonic()
def status(data):
    data['time']=time.time()
    json.dump(data,open(os.path.join(OUT,'ReviewStatus.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=2)
def tick(delta):
    global last_revision,busy
    if busy or time.monotonic()-started<5:return
    busy=True
    try:
        path=os.path.join(OUT,'ReviewCommand.json')
        if not os.path.exists(path):return
        job=json.load(open(path,encoding='utf-8-sig'))
        if job['revision']==last_revision:return
        last_revision=job['revision'];status({'revision':last_revision,'state':'running','job':job})
        if job['action']=='quit':
            status({'revision':last_revision,'state':'closed'});unreal.unregister_slate_post_tick_callback(handle);unreal.SystemLibrary.quit_editor();return
        source=os.path.abspath(os.path.join(BASE,job['script']))
        assert source.startswith(BASE+os.sep) and source.endswith('.py')
        context={'__name__':'__main__','__file__':source}
        exec(compile(open(source,encoding='utf-8').read(),source,'exec'),context)
        status({'revision':last_revision,'state':'done','job':job})
    except Exception:status({'revision':last_revision,'state':'error','error':traceback.format_exc()});unreal.log_error(traceback.format_exc())
    finally:busy=False
handle=unreal.register_slate_post_tick_callback(tick)
status({'state':'ready'})
