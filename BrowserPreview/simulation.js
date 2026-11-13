/* Original deterministic browser companion. It does not execute Unity physics. */
(function(root){
'use strict';
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const toward=(x,y,d)=>x<y?Math.min(x+d,y):Math.max(x-d,y);
const ROOFS=[{l:-10,r:10,y:0},{l:21,r:33,y:.75},{l:45,r:56,y:1.4},{l:68,r:86,y:.6}];
const HOOKS=[{x:15.5,y:9,id:0},{x:38.5,y:10.2,id:1},{x:61.5,y:10,id:2}];
const SPAWNS=[{x:-3,y:1.0},{x:25,y:1.75},{x:50,y:2.4}];
class Simulation {
  constructor(){this.events=[];this.resetRun();}
  emit(type,text,x=this.p.x,y=this.p.y){this.events.push({type,text,x,y,t:this.clock});if(this.events.length>80)this.events.shift();}
  resetRun(){
    this.clock=0;this.elapsed=0;this.deaths=0;this.checkpoint=0;this.won=false;this.broken=false;
    this.bestX=-3;this.hooks=0;this.jumps=0;this.maxSpeed=0;this.resets=0;this.events=[];
    this.move=0;this.reel=0;this.coyote=0;this.jumpBuffer=0;this.anchor=null;this.grounded=false;
    this.p={x:-3,y:1,vx:0,vy:0,facing:1};this.message='屋顶是你的跑道。向右出发！';
    this.messageEnd=3;this.attachQueued=null;this.releaseQueued=false;
  }
  warp(x,y){Object.assign(this.p,{x,y,vx:0,vy:0});this.anchor=null;this.move=this.reel=0;this.coyote=this.jumpBuffer=0;this.grounded=false;this.attachQueued=null;this.releaseQueued=false;}
  respawn(failed=true){
    if(failed)this.deaths++;
    const s=SPAWNS[this.checkpoint];this.warp(s.x,s.y);this.won=false;this.resets++;
    this.emit('reset',failed?'再来一格！':'检查点重开');this.notify(failed?'换一格，再试一次。':'已回到检查点');
  }
  notify(text,seconds=2){this.message=text;this.messageEnd=this.clock+seconds;}
  jump(){if(!this.won)this.jumpBuffer=.14;}
  release(){
    if(this.anchor){this.emit('release','ZIP!');this.anchor=null;}
  }
  canHook(h){
    const p=this.p;if(Math.hypot(h.x-p.x,h.y-p.y)>16||h.y<p.y-.5)return false;
    for(const r of ROOFS){
      for(let t=.06;t<1;t+=.06){let x=p.x+(h.x-p.x)*t,y=p.y+.2+(h.y-p.y-.2)*t;
        if(x>r.l&&x<r.r&&y<r.y-.03&&y>r.y-10)return false;
      }
    }
    return true;
  }
  pick(aim){
    let best=null,score=Infinity;const p=this.p;
    for(const h of HOOKS){if(!this.canHook(h))continue;
      const s=aim?Math.hypot(h.x-aim.x,h.y-aim.y):Math.hypot(h.x-p.x,h.y-p.y)+(h.x<p.x-1?8:0);
      if(s<score){score=s;best=h;}
    }return best;
  }
  attach(h){
    if(!h||!this.canHook(h)){this.notify('范围内没有可用挂点',.8);return false;}
    this.anchor=h;this.rope=Math.max(2.4,Math.hypot(h.x-this.p.x,h.y-this.p.y));this.hooks++;
    this.emit('hook','THWIP!',h.x,h.y);return true;
  }
  step(dt=1/120){
    this.clock+=dt;if(!this.won)this.elapsed+=dt;
    const p=this.p,hw=.31,hh=.825;
    this.grounded=false;
    for(const r of ROOFS)if(p.x+hw>r.l&&p.x-hw<r.r&&Math.abs(p.y-hh-r.y)<.095&&p.vy<1.5)this.grounded=true;
    this.coyote=this.grounded?.13:this.coyote-dt;this.jumpBuffer-=dt;
    if(this.releaseQueued){this.release();this.releaseQueued=false;}
    if(this.attachQueued){this.attach(this.attachQueued);this.attachQueued=null;}
    let move=this.won?0:this.move;
    if(move)p.facing=Math.sign(move);
    if(this.jumpBuffer>0&&this.coyote>0&&!this.won){p.vy=12.8;this.jumpBuffer=0;this.coyote=0;this.grounded=false;this.jumps++;this.emit('jump','LEAP!');}
    if(this.anchor){
      let dx=p.x-this.anchor.x,dy=p.y-this.anchor.y,d=Math.hypot(dx,dy)||1;
      let tx=-dy/d,ty=dx/d;if(tx<0){tx=-tx;ty=-ty;}
      p.vx+=tx*move*20*dt;p.vy+=ty*move*20*dt;
      this.rope=clamp(this.rope-this.reel*4*dt,2.4,16);
      p.vx*=Math.pow(.999,dt*60);p.vy*=Math.pow(.999,dt*60);
    }else if(this.grounded)p.vx=toward(p.vx,move*9.5,(move?62:48)*dt);
    else{
      if(move&&(Math.abs(p.vx)<15||Math.sign(p.vx)!==Math.sign(move)))p.vx+=move*15*dt;
      p.vx*=Math.pow(.999,dt*60);
    }
    p.vy-=9.81*2.6*dt;
    let speed=Math.hypot(p.vx,p.vy);if(speed>26){p.vx*=26/speed;p.vy*=26/speed;}
    const ox=p.x,oy=p.y;
    p.x+=p.vx*dt;p.y+=p.vy*dt;
    if(this.anchor){
      const dx=p.x-this.anchor.x,dy=p.y-this.anchor.y,d=Math.hypot(dx,dy);
      if(d>this.rope){let nx=dx/d,ny=dy/d;p.x=this.anchor.x+nx*this.rope;p.y=this.anchor.y+ny*this.rope;
        const radial=p.vx*nx+p.vy*ny;if(radial>0){p.vx-=radial*nx;p.vy-=radial*ny;}}
    }
    for(const r of ROOFS){
      if(p.x+hw>r.l&&p.x-hw<r.r&&p.y-hh<r.y&&p.y+hh>r.y-10){
        if(oy-hh>=r.y-.035){p.y=r.y+hh;if(p.vy<0){p.vy=0;if(!this.grounded)this.emit('land','');}this.grounded=true;}
        else if(ox+hw<=r.l+.03){p.x=r.l-hw;if(p.vx>0)p.vx=0;}
        else if(ox-hw>=r.r-.03){p.x=r.r+hw;if(p.vx<0)p.vx=0;}
        else if(oy+hh<=r.y-10){p.y=r.y-10-hh;p.vy=Math.min(p.vy,0);}
        else {p.y=r.y+hh;p.vy=Math.max(0,p.vy);this.grounded=true;}
      }
    }
    this.bestX=Math.max(this.bestX,p.x);this.maxSpeed=Math.max(this.maxSpeed,Math.hypot(p.vx,p.vy));
    if(p.y<-8||p.x<-15){this.respawn();return;}
    if(!this.won&&this.grounded&&p.x>24&&p.x<32&&this.checkpoint<1){this.checkpoint=1;this.emit('checkpoint','SAVED!');this.notify('检查点 01 已保存');}
    if(!this.won&&this.grounded&&p.x>49&&p.x<55&&this.checkpoint<2){this.checkpoint=2;this.emit('checkpoint','SAVED!');this.notify('检查点 02 已保存');}
    if(!this.broken&&p.x>71&&p.x<74&&p.y>.4&&p.y<4.5&&p.vx>12){this.broken=true;this.emit('break','KRAK!',72,2.2);this.notify('高速破框！');}
    if(!this.won&&p.x>76&&p.y>0&&p.y<6){this.won=true;this.release();this.emit('win','ISSUE COMPLETE!');this.notify('本期完结。按 R 再来一局。',99);}
  }
}

// Uses the exact same input path as a player; never teleports during the route.
class Pilot{
  constructor(sim){this.s=sim;this.gap=0;this.phase='run';this.t=0;this.done=false;this.reason='';}
  step(dt){
    const s=this.s,p=s.p;s.move=1;s.reel=0;this.t+=dt;
    if(s.deaths){this.done=true;this.reason='fell during route';s.move=0;return;}
    if(s.won){this.done=true;s.move=0;return;}
    if(this.gap>=3)return;
    const edge=[8.2,31.2,54.2][this.gap],h=HOOKS[this.gap];
    if(this.phase==='run'&&p.x>=edge&&s.grounded){s.jump();this.phase='jump';this.t=0;}
    else if(this.phase==='jump'&&this.t>=.18){s.attachQueued=h;this.phase='swing';this.t=0;}
    else if(this.phase==='swing'&&s.anchor&&p.x>h.x+4.5){s.releaseQueued=true;this.phase='land';this.t=0;}
    else if(this.phase==='land'&&s.grounded&&p.x>[21.5,45.5,68.5][this.gap]){this.gap++;this.phase='run';this.t=0;}
    if(this.t>8){this.done=true;this.reason='route timeout '+this.gap+' '+this.phase;s.move=0;}
  }
}

function selfTest(){
  const results=[],s=new Simulation(),dt=1/120;
  const test=(name,ok,detail='')=>results.push({name,pass:!!ok,detail});
  const advance=(t,fn)=>{for(let i=0;i<Math.round(t/dt);i++){if(fn)fn(i);s.step(dt);}};
  advance(.6);test('落地 / 起点碰撞',s.grounded);
  let x=s.p.x;s.move=1;advance(.4);test('移动输入',s.p.x>x+1);
  let y=s.p.y;s.jump();advance(.2);test('跳跃输入',s.p.y>y+1&&s.jumps===1);
  s.warp(9,3);s.move=1;s.attach(HOOKS[0]);advance(.6);test('固定点摆荡',!!s.anchor&&Math.hypot(s.p.x-9,s.p.y-3)>1);
  let rope=s.rope;s.reel=1;advance(.3);test('收丝',s.rope<rope-.8);
  s.release();test('松丝保留动量',!s.anchor&&Math.hypot(s.p.vx,s.p.vy)>1);
  test('挂点距离限制',!s.attach(HOOKS[2]));
  s.warp(15,-9);advance(.02);test('失败重置',s.deaths===1&&s.p.y>0);
  s.warp(26,2);advance(.7);test('检查点落地激活',s.checkpoint===1);
  s.warp(40,-9);advance(.02);test('检查点复活',Math.abs(s.p.x-25)<.1);
  s.resetRun();let pilot=new Pilot(s);let frames=0;
  while(!pilot.done&&frames<120*40){pilot.step(dt);s.step(dt);frames++;}
  test('连续三段摆荡 → 实际通关（无传送）',s.won&&s.deaths===0&&s.hooks===3,JSON.stringify({time:s.elapsed,hooks:s.hooks,deaths:s.deaths,x:s.p.x,reason:pilot.reason}));
  test('速度上限与有限数值',Number.isFinite(s.p.x)&&s.maxSpeed<=26.01);
  let achieved=s.won;s.resetRun();test('通关后新一局',achieved&&!s.won&&s.checkpoint===0&&s.p.x===-3);
  return {engine:'Browser companion / custom deterministic XY physics, NOT Unity',utc:new Date().toISOString(),pass:results.every(r=>r.pass),results};
}
root.Inkline={Simulation,Pilot,selfTest,ROOFS,HOOKS,SPAWNS,clamp};
})(typeof window!=='undefined'?window:globalThis);
