"""Metre-scale, editable enemy staging prototype for the martial court only."""
import math

def make_pressure():
    data={'court':'B_MartialCourt','ground_z':28,'display_only':True,
          'combat_disk':{'center':[0,140,28],'radius':14},
          'central_clear_width':15,'terraces':[],'stairs':[],'enemies':[],
          'walk_detours':[], 'views':[
              {'name':'CAM_10_PressureEntry','position':[0,126,29.62],'target':[0,157,31.0],'fov':78},
              {'name':'CAM_11_PressureCombat','position':[0,137,29.62],'target':[0,158,31.1],'fov':86},
              {'name':'CAM_12_PressurePlan','position':[0,140,100],'target':[0,140,28],'fov':62},
              {'name':'CAM_13_PressureOblique','position':[-49,103,65],'target':[0,149,29],'fov':58}]}
    for sign,side in ((-1,'R'),(1,'L')):
        x=sign*18.8
        for rank,(y0,y1,h,ey) in enumerate(((154.8,157.6,1.6,155.65),(157.6,160.4,3.2,158.75),(160.4,163.8,4.8,162.0)),1):
            data['terraces'].append({'name':side+'_Tier'+str(rank),'center':[sign*12.5,(y0+y1)/2,28+h], 'size':[10.2,y1-y0],'height':h,'rank':rank,'side':side})
            for i in range(5):
                xx=sign*(8.5+i*2+(.28 if rank==2 else 0))
                data['enemies'].append({'id':'B_%s_%d_%02d'%(side,rank,i+1),'foot':[xx,ey+(i%2)*.12,28+h],'rank':rank,'role':'reserve' if rank<3 else 'officer_reserve'})
        for i,(xx,yy) in enumerate(((4,134),(10,148.8),(15,150))):
            data['enemies'].append({'id':'B_%s_0_%02d'%(side,i+1),'foot':[sign*xx,yy,28],'rank':0,'role':'front_melee'})
        detour=[[0,140,28],[x,145,28],[x,151.6,28]]
        for rank,(start,end,base,top) in enumerate(((151.8,155,28,29.6),(155.9,159.1,29.6,31.2),(160,163.2,31.2,32.8)),1):
            steps=[]
            for j in range(10):steps.append([x,start+(j+.5)*(end-start)/10,base+(j+1)*(top-base)/10])
            landing_end=(155.9,160,163.8)[rank-1]
            data['stairs'].append({'name':side+'_Access'+str(rank),'x':x,'width':2.4,'start_y':start,'end_y':end,'base':base,'top':top,'riser':.16,'tread':.32,'steps':steps,'landing_end_y':landing_end})
            detour.extend(steps[::2]);detour.append([x,end,top])
            if rank<3:detour.append([x,(end+landing_end)/2,top])
        detour.extend([[x,163.0,32.8],[sign*16,163.0,32.8],[sign*11,163.0,32.8]])
        # Return by the same safe access; no jump down from the display ledges.
        data['walk_detours'].append(detour+list(reversed(detour[:-1])))
    return data

if __name__=='__main__':
    import json
    print(json.dumps(make_pressure(),ensure_ascii=False,indent=2))
