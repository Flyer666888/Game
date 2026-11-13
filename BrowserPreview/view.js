(function(){
'use strict';
const {Simulation,Pilot,HOOKS,ROOFS,clamp}=Inkline;
const $=id=>document.getElementById(id),canvas=$('game'),ctx=canvas.getContext('2d');
const C={paper:'#faf0d6',ink:'#26163e',pink:'#ff347f',cyan:'#22edd3',lavender:'#a492af',peach:'#d9adac'};
const sim=new Simulation(),keys=new Set(),holds=new Set();
let running=false,paused=false,pilot=null,mode='intro',last=0,acc=0,cameraX=2,cameraY=4.4,zoom=47;
let eventIndex=0,pops=[],shards=[],trail=[],audio=null,muted=false,wasWon=false;
let W=1440,H=810,uiClock=0;
const DPR=Math.min(window.devicePixelRatio||1,2);
function resize(){const r=canvas.getBoundingClientRect();canvas.width=Math.round(r.width*DPR);canvas.height=Math.round(r.height*DPR);W=1440;H=W*r.height/r.width;ctx.setTransform(canvas.width/W,0,0,canvas.height/H,0,0);}
window.addEventListener('resize',resize);resize();
function point(x,y,z=0){return {x:W/2+(x-cameraX)*zoom+z*8,y:H*.53-(y-cameraY)*zoom-z*5};}
function poly(points,fill,stroke=C.ink,width=2){ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.closePath();ctx.fillStyle=fill;ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=width;ctx.stroke();}}
function line(x,y,x2,y2,c,w){ctx.strokeStyle=c;ctx.lineWidth=w;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x2,y2);ctx.stroke();}
function text(txt,x,y,size=20,c=C.ink,align='left',italic=false){ctx.fillStyle=c;ctx.font=`${italic?'italic ':''}900 ${size}px "Segoe UI","Microsoft YaHei",sans-serif`;ctx.textAlign=align;ctx.fillText(txt,x,y);}
function rect(x,y,w,h,c){ctx.fillStyle=c;ctx.fillRect(x,y,w,h);}
function dotFill(x,y,w,h,c,spacing=10,r=1.5){ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();ctx.fillStyle=c;for(let a=x;a<x+w;a+=spacing)for(let b=y;b<y+h;b+=spacing){ctx.beginPath();ctx.arc(a,b,r,0,7);ctx.fill();}ctx.restore();}
function worldText(t,x,y,size,c=C.ink){const p=point(x,y);text(t,p.x,p.y,size,c);}
function block(l,r,top,bottom,color,depth=3){
 const a=point(l,top),b=point(r,top),c=point(r,bottom),d=point(l,bottom),a2=point(l,top,depth),b2=point(r,top,depth),c2=point(r,bottom,depth);
 poly([b,b2,c2,c],C.ink);poly([a,a2,b2,b],C.paper);poly([a,b,c,d],color);
 return {a,b,c,d};
}
const skyline=Array.from({length:55},(_,i)=>({x:-70+i*4.1,h:3+((i*17)%13)*.52,w:2.6+(i%3)*.4,layer:i%2}));
function drawCity(){
 rect(0,0,W,H,C.paper);
 const sun=point(cameraX*.65+13,13,0);ctx.fillStyle='#f3c58c';ctx.beginPath();ctx.arc(sun.x,sun.y,130,0,7);ctx.fill();dotFill(sun.x-110,sun.y-110,220,220,'#dfaf91',9,1);
 for(let layer=1;layer>=0;layer--)for(const b of skyline){if(b.layer!==layer)continue;
   let px=(b.x-cameraX*(layer?.22:.38))*zoom+W/2,py=H*.76-b.h*zoom*.6;
   if(px<-250||px>W+120)continue;
   rect(px,py,b.w*zoom*.65,H-py,layer?'#e2d0cd':'#c8b7c9');
   line(px+b.w*zoom*.33,py,px+b.w*zoom*.33,py-23,layer?'#d2bbcb':'#b4a1bb',2);
   if(!layer)for(let y=py+20;y<H;y+=32)for(let x=px+12;x<px+b.w*zoom*.6;x+=23)rect(x,y,7,12,'#f5e7cd');
 }
 // A drifting print texture and page grain are drawn, never loaded from the network.
 ctx.globalAlpha=.06;for(let i=0;i<130;i++){let x=(i*337)%W,y=(i*173)%H;line(x,y,x+7,y+.8,C.ink,1);}ctx.globalAlpha=1;
}
function drawRoofs(){
 ROOFS.forEach((r,i)=>{
  if(point(r.r,0).x<-120||point(r.l,0).x>W+120)return;
  const q=block(r.l,r.r,r.y,-11,i%2?C.peach:C.lavender,3.2);
  dotFill(q.a.x,q.a.y+5,q.b.x-q.a.x,H-q.a.y,C.ink,12,1.2);
  const cap=point(r.l,r.y);line(cap.x,cap.y,point(r.r,r.y).x,cap.y,C.ink,6);line(cap.x,cap.y-3,point(r.r,r.y).x,cap.y-3,C.paper,3);
  for(let x=r.l+1;x<r.r-.3;x+=2.1)for(let y=r.y-1.8;y>-10;y-=2){
    const p=point(x,y);rect(p.x-18,p.y-22,34,49,C.ink);rect(p.x-11,p.y-16,21,32,C.paper);line(p.x-9,p.y-1,p.x+10,p.y-1,C.ink,3);
  }
  // Roof equipment adds depth without colliders.
  if(i<3){const p=point(r.l+2,r.y,.7);poly([{x:p.x,y:p.y-5},{x:p.x+40,y:p.y-5},{x:p.x+40,y:p.y-27},{x:p.x,y:p.y-27}],C.paper);line(p.x+5,p.y-15,p.x+35,p.y-15,C.ink,2);}
 });
 worldText('INKLINE',-8,5.4,66,C.ink);worldText('ROOFTOPS / ISSUE 001',-7.8,4.4,17,C.ink);
 worldText('RUN. LEAP. THWIP.',-7.7,3.55,17,C.pink);
 worldText('01 / 起跳',6.7,1.0,15,C.ink);
 worldText('02 / RELAY',22.2,3.6,26,C.ink);worldText('落地保存检查点',22.2,2.8,13,C.ink);
 worldText('03 / KEEP GOING',46,5.0,24,C.ink);worldText('把速度带过去 →',46,4.2,14,C.pink);
 worldText('FINISH',75,4.5,49,C.ink);worldText('END OF THIS ISSUE',75,3.5,14,C.ink);
 [[25,.75,1],[50,1.4,2],[77.5,.6,3]].forEach(([x,y,n])=>{
  const p=point(x,y),t=point(x,y+2.0);line(p.x,p.y,t.x,t.y,C.ink,4);
  poly([t,{x:t.x+48,y:t.y+5},{x:t.x+48,y:t.y+32},{x:t.x,y:t.y+27}],n===3?C.pink:C.cyan);
  text(n===3?'END':sim.checkpoint>=n?'✓':'CP',t.x+8,t.y+23,14,C.ink);
 });
 if(!sim.broken){const a=point(71,.6),b=point(73,4.3);ctx.save();ctx.setLineDash([7,4]);ctx.strokeStyle=C.pink;ctx.lineWidth=3;ctx.strokeRect(a.x,b.y,b.x-a.x,a.y-b.y);ctx.restore();worldText('高速冲破框线',69.8,5.1,13,C.pink);}
}
function drawHooks(){
 const target=sim.pick();
 HOOKS.forEach(h=>{
  const p=point(h.x,h.y),reachable=sim.canHook(h);
  if(p.x<-80||p.x>W+80)return;
  line(p.x,0,p.x,p.y-20,'#6a506f',1.4);
  if(reachable){ctx.globalAlpha=.17;ctx.fillStyle=C.cyan;ctx.beginPath();ctx.arc(p.x,p.y,37,0,7);ctx.fill();ctx.globalAlpha=1;}
  ctx.strokeStyle=C.ink;ctx.lineWidth=3;ctx.fillStyle=C.cyan;ctx.beginPath();ctx.arc(p.x,p.y,14,0,7);ctx.fill();ctx.stroke();
  ctx.beginPath();ctx.arc(p.x,p.y,23,0,7);ctx.stroke();
  text(String(h.id+1).padStart(2,'0'),p.x,p.y+5,12,C.ink,'center');
  text('FIXED HOOK',p.x,p.y-37,10,C.ink,'center');
  if(target===h&&!sim.anchor&&running){rect(p.x-45,p.y+32,90,25,C.ink);text('E / 挂丝',p.x,p.y+50,13,C.cyan,'center');}
  // The release zone makes the useful timing legible without automating the player.
  const release=point(h.x+4.5,3.1);
  ctx.globalAlpha=sim.anchor===h?.95:.45;
  line(release.x-31,release.y+18,release.x+31,release.y+18,C.pink,3);
  poly([{x:release.x-7,y:release.y},{x:release.x,y:release.y-7},{x:release.x+7,y:release.y},{x:release.x,y:release.y+7}],C.pink,null);
  text('松丝区 →',release.x,release.y+41,13,C.pink,'center');ctx.globalAlpha=1;
 });
}
function drawRunner(){
 const p=point(sim.p.x,sim.p.y),v=sim.p,speed=Math.hypot(v.vx,v.vy);
 if(speed>12){trail.push({x:p.x,y:p.y,t:uiClock});if(trail.length>13)trail.shift();}else trail=[];
 for(let i=1;i<trail.length;i++){const a=trail[i-1],b=trail[i];line(a.x,a.y,b.x,b.y,`rgba(255,52,127,${i/trail.length*.17})`,i*.65);}
 if(sim.anchor){const h=point(sim.anchor.x,sim.anchor.y);line(p.x+v.facing*5,p.y-17,h.x,h.y,C.ink,4);line(p.x+v.facing*5,p.y-17,h.x,h.y,C.cyan,2.3);}
 // Human silhouette built from a jacket, masked head and jointed limbs.
 ctx.save();ctx.translate(p.x,p.y);ctx.scale(v.facing,1);ctx.rotate(clamp(-v.vx*.018,-.36,.36));
 const run=Math.sin(sim.clock*18),air=!sim.grounded;
 const legA=air?.4:run*.5,legB=air?-.5:-run*.5;
 const limb=(x,y,angle,len,width,col)=>{ctx.save();ctx.translate(x,y);ctx.rotate(angle);ctx.lineCap='round';line(0,0,0,len,C.ink,width+4);line(0,0,0,len,col,width);ctx.restore();};
 limb(-6,8,legA,28,7,C.ink);limb(6,8,legB,28,7,C.ink);
 limb(-12,-15,sim.anchor?2.9:air?-1:run*.7,24,6,C.ink);
 poly([{x:-10,y:-22},{x:9,y:-22},{x:12,y:7},{x:-9,y:10}],C.pink,C.ink,3);
 poly([{x:-4,y:-13},{x:4,y:-16},{x:5,y:0},{x:-3,y:1}],C.ink,null);
 limb(11,-15,sim.anchor?-2.5:air?.7:-run*.7,24,6,C.ink);
 ctx.fillStyle=C.ink;ctx.beginPath();ctx.ellipse(1,-34,11,13,0,0,7);ctx.fill();
 poly([{x:-1,y:-38},{x:10,y:-41},{x:10,y:-35},{x:0,y:-33}],C.cyan,null);
 ctx.restore();
 // Ground contact shadow is tied to the actual roof under the player.
 const roof=ROOFS.find(r=>v.x>r.l&&v.x<r.r);if(roof){const q=point(v.x,roof.y);ctx.globalAlpha=clamp(1-(v.y-roof.y)/9,0,.3);ctx.fillStyle=C.ink;ctx.beginPath();ctx.ellipse(q.x,q.y+3,20,4,0,0,7);ctx.fill();ctx.globalAlpha=1;}
}
function drawEffects(dt){
 for(const pop of pops){const p=point(pop.x,pop.y),age=uiClock-pop.born,alpha=clamp(1-age/.75,0,1);ctx.save();ctx.translate(p.x,p.y-age*60);ctx.rotate(-.09);ctx.globalAlpha=alpha;ctx.font='italic 1000 31px "Segoe UI",sans-serif';const w=ctx.measureText(pop.text).width;poly([{x:-w/2-14,y:-32},{x:w/2+18,y:-38},{x:w/2+12,y:8},{x:-w/2-20,y:13}],C.ink,null);text(pop.text,0,0,30,pop.type==='hook'||pop.type==='checkpoint'?C.cyan:C.pink,'center',true);ctx.restore();}
 pops=pops.filter(p=>uiClock-p.born<.75);
 for(const s of shards){s.x+=s.vx*dt;s.y+=s.vy*dt;s.vy-=12*dt;s.a+=dt*s.spin;const p=point(s.x,s.y);ctx.save();ctx.translate(p.x,p.y);ctx.rotate(s.a);rect(-3,-10,6,20,s.color);ctx.restore();}shards=shards.filter(s=>uiClock-s.t<1.2);
 if(Math.abs(sim.p.vx)>17){ctx.globalAlpha=.2;for(let i=0;i<13;i++){const y=(i*67+uiClock*13)%H;line(i%2?0:W,y,i%2?65:W-70,y-8,C.pink,2);}ctx.globalAlpha=1;}
 if(paused&&running){ctx.fillStyle='#26163e55';ctx.fillRect(0,0,W,H);rect(W/2-120,H/2-38,240,76,C.ink);text('已暂停 / ESC',W/2,H/2+7,24,C.paper,'center');}
}
function cue(type){
 if(!audio||muted)return;
 try{let osc=audio.createOscillator(),gain=audio.createGain();osc.connect(gain);gain.connect(audio.destination);let now=audio.currentTime;let f=type==='hook'?720:type==='jump'?330:type==='win'?880:210;
 osc.type='triangle';osc.frequency.setValueAtTime(f,now);osc.frequency.exponentialRampToValueAtTime(type==='release'?500:f*.5,now+.12);gain.gain.setValueAtTime(.035,now);gain.gain.exponentialRampToValueAtTime(.0001,now+.16);osc.start(now);osc.stop(now+.17);}catch(e){}
}
function consumeEvents(){
 if(eventIndex>sim.events.length)eventIndex=0;
 for(;eventIndex<sim.events.length;eventIndex++){
  const ev=sim.events[eventIndex];if(ev.text)pops.push({...ev,born:uiClock});
  if(['hook','jump','release','win','checkpoint'].includes(ev.type))cue(ev.type);
  if(ev.type==='reset'){cameraX=sim.p.x+5;cameraY=4.4;trail=[];}
  if(ev.type==='break')for(let i=0;i<18;i++){let a=i*2.4;shards.push({x:72,y:2.2,vx:Math.cos(a)*7+5,vy:Math.sin(a)*7,a:0,spin:i*.3+2,t:uiClock,color:i%3?C.ink:C.pink});}
 }
}
function updateHUD(){
 const p=sim.p;
 $('stats').textContent=sim.elapsed.toFixed(1).padStart(4,'0')+' 秒 / 重试 '+sim.deaths;
 $('web-status').textContent=sim.won?'本期完结':sim.anchor?'蛛丝已连接 · '+sim.rope.toFixed(1)+' m':sim.grounded?'屋顶上 · '+Math.abs(p.vx).toFixed(1)+' m/s':'腾空中 · '+Math.hypot(p.vx,p.vy).toFixed(1)+' m/s';
 $('web-status').style.color=sim.anchor?C.cyan:C.paper;
 $('progress-label').textContent=sim.won?'终点 · ISSUE COMPLETE':sim.checkpoint===2?'检查点 02 · 最后一跃':sim.checkpoint===1?'检查点 01 · 继续向右':'起点 · 向右前进';
 $('progress-bar').style.width=(clamp((sim.bestX+3)/79,0,1)*100)+'%';
 let tip=sim.messageEnd>sim.clock?sim.message:'跑向边缘 → 跳跃 → E 挂丝 → 越过挂点 → E 松丝';
 if(sim.anchor)tip=p.x>sim.anchor.x+3.6?'现在按 E / Q 松丝！保持向右，落上屋顶。':'继续按 D 增加速度，越过挂点后在粉色区域松丝。';
 else if(!sim.grounded&&sim.pick())tip='按 E 连接青色挂点；也可鼠标按住左键。';
 if(paused&&running)tip='已暂停。按 Esc 或点击继续。';
 $('tip').textContent=tip;
 $('pause').textContent=paused?'继续':'暂停';
 if(sim.won&&!wasWon){
  $('win-stat').textContent=sim.elapsed.toFixed(1)+' 秒　/　'+sim.deaths+' 次重试　/　'+sim.hooks+' 次挂丝';
  $('win-extra').textContent=sim.broken?'你还高速冲破了最后一格边框！':'试着保留更多松丝速度，下次冲破最后一格边框。';
  $('win').hidden=false;$('demo-badge').hidden=true;keys.clear();holds.clear();
 }
 wasWon=sim.won;
}
function start(demo=false){
 sim.resetRun();eventIndex=0;pops=[];shards=[];trail=[];wasWon=false;keys.clear();holds.clear();
 running=true;paused=false;mode=demo?'demo':'play';pilot=demo?new Pilot(sim):null;
 cameraX=2;cameraY=4.4;zoom=47;acc=0;
 $('intro').hidden=true;$('win').hidden=true;$('help-modal').hidden=true;$('test-modal').hidden=true;$('demo-badge').hidden=!demo;
 try{if(!audio&&window.AudioContext)audio=new AudioContext();if(audio&&audio.state==='suspended')audio.resume();}catch(e){}
 $('stage').focus();updateHUD();
}
function takeOver(){if(pilot){pilot=null;mode='play';$('demo-badge').hidden=true;sim.notify('现在由你接管！');}}
function web(){takeOver();if(sim.anchor)sim.releaseQueued=true;else sim.attachQueued=sim.pick();}
function doJump(){takeOver();sim.jump();}
function restart(){start(false);}
function togglePause(){if(!running||sim.won)return;paused=!paused;keys.clear();holds.clear();acc=0;updateHUD();}
const handled=new Set(['KeyA','KeyD','ArrowLeft','ArrowRight','Space','KeyE','KeyQ','KeyW','KeyS','ArrowUp','ArrowDown','KeyR','Backspace','Escape']);
window.addEventListener('keydown',e=>{
 if(!handled.has(e.code))return;e.preventDefault();
 if(e.code==='Escape'){if(!$('help-modal').hidden){$('help-modal').hidden=true;paused=false;}else if(!$('test-modal').hidden){$('test-modal').hidden=true;paused=false;}else togglePause();return;}
 if(e.code==='KeyR'&&!e.repeat){restart();return;}
 if(!running||paused||sim.won)return;
 takeOver();keys.add(e.code);
 if(e.repeat)return;
 if(e.code==='Space')doJump();if(e.code==='KeyE')web();if(e.code==='KeyQ')sim.releaseQueued=true;
 if(e.code==='Backspace'){sim.respawn(false);eventIndex=0;}
});
window.addEventListener('keyup',e=>keys.delete(e.code));
window.addEventListener('blur',()=>{keys.clear();holds.clear();if(running&&!sim.won){paused=true;updateHUD();}});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&running&&!sim.won){paused=true;keys.clear();holds.clear();updateHUD();}});
canvas.addEventListener('pointerdown',e=>{
 if(!running||paused||sim.won||e.button!==0)return;e.preventDefault();takeOver();
 const r=canvas.getBoundingClientRect(),x=(e.clientX-r.left)*W/r.width,y=(e.clientY-r.top)*H/r.height;
 const aim={x:(x-W/2)/zoom+cameraX,y:cameraY+(H*.53-y)/zoom};
 sim.attachQueued=sim.pick(aim);canvas.setPointerCapture(e.pointerId);
});
canvas.addEventListener('pointerup',e=>{if(running&&!paused)sim.releaseQueued=true;});
canvas.addEventListener('pointercancel',()=>{sim.releaseQueued=true;});
$('start').onclick=()=>start(false);$('demo').onclick=()=>start(true);$('again').onclick=()=>start(false);$('replay').onclick=()=>start(true);$('restart').onclick=restart;$('pause').onclick=togglePause;
$('help').onclick=()=>{paused=true;keys.clear();holds.clear();$('help-modal').hidden=false;updateHUD();};$('close-help').onclick=()=>{$('help-modal').hidden=true;paused=false;$('stage').focus();};
$('tests').onclick=()=>{paused=true;keys.clear();holds.clear();$('test-modal').hidden=false;const r=Inkline.selfTest();$('test-result').textContent=(r.pass?'PASS / 全部通过':'FAIL / 有未通过项')+'\n\n'+r.results.map(x=>(x.pass?'✓ ':'✗ ')+x.name+(x.detail?'\n  '+x.detail:'')).join('\n')+'\n\n'+r.engine+'\n'+r.utc;updateHUD();};$('close-test').onclick=()=>{$('test-modal').hidden=true;paused=false;$('stage').focus();};
$('touch-jump').onclick=()=>{if(running&&!paused)doJump();};$('touch-web').onclick=()=>{if(running&&!paused)web();};
document.querySelectorAll('[data-hold]').forEach(b=>{b.addEventListener('pointerdown',e=>{e.preventDefault();if(running&&!paused){takeOver();holds.add(b.dataset.hold);b.setPointerCapture(e.pointerId);}});['pointerup','pointercancel','lostpointercapture'].forEach(type=>b.addEventListener(type,()=>holds.delete(b.dataset.hold)));});
function frame(timestamp){
 let dt=Math.min((timestamp-last)/1000||0,1/15);last=timestamp;uiClock+=dt;
 if(running&&!paused){
   acc+=dt;let count=0;
   while(acc>=1/120&&count++<10){
    if(pilot){pilot.step(1/120);if(pilot.done&&!sim.won){pilot=null;mode='play';$('demo-badge').hidden=true;sim.notify('示范结束，现在由你操作。');}}
    else{sim.move=(keys.has('KeyD')||keys.has('ArrowRight')||holds.has('right')?1:0)-(keys.has('KeyA')||keys.has('ArrowLeft')||holds.has('left')?1:0);sim.reel=(keys.has('KeyW')||keys.has('ArrowUp')?1:0)-(keys.has('KeyS')||keys.has('ArrowDown')?1:0);}
    sim.step(1/120);acc-=1/120;
   }
   consumeEvents();
 }
 const targetX=Math.max(2,sim.p.x+5),targetY=clamp(sim.p.y+2.5,4.4,9);
 cameraX+=(targetX-cameraX)*(1-Math.exp(-dt*5));cameraY+=(targetY-cameraY)*(1-Math.exp(-dt*3));
 zoom+=(47-clamp((Math.abs(sim.p.vx)-13),0,10)*.35-zoom)*(1-Math.exp(-dt*2));
 ctx.setTransform(canvas.width/W,0,0,canvas.height/H,0,0);ctx.clearRect(0,0,W,H);
 drawCity();drawRoofs();drawHooks();drawRunner();drawEffects(paused?0:dt);updateHUD();
 requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
})();
