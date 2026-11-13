"""Local, project-scoped live UE review worker. Own editor exits on QUIT job."""
import unreal, json, os, time, traceback
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v03'
COMMAND=os.path.join(OUT,'ReviewCommand.json')
STATUS=os.path.join(OUT,'ReviewStatus.json')
last_revision=None;busy=False;handle=None;started=time.monotonic()
def status(data):
    data['time']=time.time()
    with open(STATUS,'w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
def tick(delta):
    global last_revision,busy
    if busy or time.monotonic()-started<5:return
    busy=True
    try:
        if not os.path.exists(COMMAND):return
        with open(COMMAND,encoding='utf-8-sig') as f:job=json.load(f)
        if job['revision']==last_revision:return
        last_revision=job['revision']
        status({'revision':last_revision,'state':'running','job':job})
        if job['action']=='quit':
            status({'revision':last_revision,'state':'closed'})
            unreal.unregister_slate_post_tick_callback(handle)
            unreal.SystemLibrary.quit_editor();return
        filename=job['script']
        path=os.path.abspath(os.path.join(BASE,filename))
        if not path.startswith(BASE+os.sep) or not path.endswith('.py'):raise RuntimeError('Job must be a local whitebox Python source')
        context={'__name__':'__main__','review_delta':delta}
        with open(path,encoding='utf-8') as f:exec(compile(f.read(),path,'exec'),context)
        status({'revision':last_revision,'state':'done','job':job})
    except Exception:
        status({'revision':last_revision,'state':'error','error':traceback.format_exc()})
        unreal.log_error(traceback.format_exc())
    finally:busy=False
handle=unreal.register_slate_post_tick_callback(tick)
status({'state':'ready'})

