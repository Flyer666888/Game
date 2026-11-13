"""Run V10 saved geometry audits and publish an explicit combined result."""
import datetime,json,os,traceback
BASE=r'D:\game design\experiment\Scripts\Editor\NilinBlockout'
OUT=r'D:\game design\experiment\Docs\LevelDesign\Blockout_v05'
os.makedirs(OUT,exist_ok=True)
summary={'map':'/Game/ReversedScale/Maps/L_NilinBlockoutV10',
         'checked_at':datetime.datetime.now().isoformat(),
         'state':'running','success':False,'checks':[],
         'scope':'Saved-map collision, sightlines, marker placement and readback. Runtime walking and rendered captures are separate reports.'}
def save_summary():
    with open(os.path.join(OUT,'CheckSceneReport.json'),'w',encoding='utf-8') as handle:
        json.dump(summary,handle,ensure_ascii=False,indent=2)
save_summary()
try:
    for name,output in (('validate_v05.py','Validation.json'),
                        ('audit_edges_v05.py','EdgeAudit.json'),
                        ('audit_pressure_v05.py','PressureAudit.json'),
                        ('readback_v05.py','Readback.json')):
        summary['active_check']=name;save_summary()
        path=os.path.join(BASE,name)
        exec(compile(open(path,encoding='utf-8').read(),path,'exec'),{'__name__':'__main__'})
        with open(os.path.join(OUT,output),encoding='utf-8') as handle:result=json.load(handle)
        passed=result.get('map')==summary['map'] and result.get('success') is True
        summary['checks'].append({'script':name,'report':output,'success':passed})
        save_summary()
    summary['success']=all(check['success'] for check in summary['checks'])
    summary['state']='passed' if summary['success'] else 'failed'
    summary.pop('active_check',None)
    save_summary()
except Exception:
    summary['state']='error';summary['success']=False
    summary['error']=traceback.format_exc();save_summary()
    raise
