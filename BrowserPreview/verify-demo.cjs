'use strict';
// Node-only automated simulation and input integration checks. No real browser is used.
const fs=require('fs'),path=require('path'),vm=require('vm');
const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
const checks=[];
function check(name,pass,detail=''){checks.push({name,pass:!!pass,detail});}
function harness(){
 const events={},elements={},drawCalls=[];let nextFrame,now=0;
 const ctx=new Proxy({measureText:t=>({width:t.length*17}),fillText:(t,x,y)=>{drawCalls.push({t,x,y});if(drawCalls.length>2500)drawCalls.shift();}}, {get:(o,k)=>k in o?o[k]:(()=>{}),set:(o,k,v)=>(o[k]=v,true)});
 class Element {
  constructor(id,hidden=false){this.id=id;this.hidden=hidden;this.style={};this.textContent='';this.dataset={};this.handlers={};this.width=1440;this.height=810;}
  addEventListener(type,fn){(this.handlers[type]??=[]).push(fn);}
  trigger(type,event={}){event.preventDefault??=()=>{};for(const fn of this.handlers[type]||[])fn(event);}
  focus(){} setPointerCapture(){} getContext(){return ctx;} getBoundingClientRect(){return {left:0,top:0,width:1440,height:810};}
 }
 for(const match of html.matchAll(/<[^>]+id="([^"]+)"[^>]*>/g))elements[match[1]]=new Element(match[1],/\shidden(?:\s|>)/.test(match[0]));
 const touch=['left','right'].map(x=>{const e=new Element('touch-'+x);e.dataset.hold=x;return e;});
 const sandbox={console,Math,Date,JSON,Set,devicePixelRatio:1,document:{hidden:false,getElementById:id=>elements[id],querySelectorAll:()=>touch,addEventListener:(t,f)=>(events['document:'+t]??=[]).push(f)},addEventListener:(t,f)=>(events[t]??=[]).push(f),requestAnimationFrame:f=>{nextFrame=f;}};
 sandbox.window=sandbox;vm.createContext(sandbox);for(const source of scripts)vm.runInContext(source,sandbox,{timeout:5000});
 return {sandbox,e:elements,drawCalls,touch,click:id=>elements[id].onclick(),key:(code,up=false)=>{for(const fn of events[up?'keyup':'keydown']||[])fn({code,repeat:false,preventDefault(){}});},advance:seconds=>{for(let i=0;i<Math.round(seconds*60);i++){now+=1000/60;nextFrame(now);}},emit:(type,e)=>{for(const fn of events[type]||[])fn(e||{});}};
}
const a=harness(),core=a.sandbox.Inkline.selfTest();
for(const c of core.results)check('模拟 / '+c.name,c.pass,c.detail);
check('离线单文件 / 无外部脚本样式资源',!/<(?:script[^>]+src|link[^>]+href|img[^>]+src)\s*=/i.test(html)&&!html.includes('/*__SIMULATION__*/'));
check('开始界面可见',!a.e.intro.hidden);
a.click('start');a.advance(.6);check('开始按钮进入玩法',a.e.intro.hidden&&a.e['web-status'].textContent.includes('屋顶上'));
a.key('KeyD');a.advance(1);check('D 键移动输入',Number(a.e['web-status'].textContent.match(/([\d.]+) m\/s/)?.[1])>5);
a.key('Space');a.key('Space',true);a.advance(.12);check('空格跳跃输入',a.e['web-status'].textContent.includes('腾空中'));
a.key('KeyE');a.key('KeyE',true);a.advance(.04);check('E 键挂丝输入',a.e['web-status'].textContent.includes('蛛丝已连接'));
a.key('KeyE');a.key('KeyE',true);a.advance(.04);check('E 键松丝输入',!a.e['web-status'].textContent.includes('蛛丝已连接'));
a.key('KeyD',true);a.click('restart');a.advance(.4);a.key('KeyD');a.advance(3);a.key('KeyD',true);check('实际走出屋顶后跌落重置',/重试 [1-9]/.test(a.e.stats.textContent),a.e.stats.textContent);
a.key('KeyR');a.key('KeyR',true);a.advance(.4);check('R 键重玩清空重试数',a.e.stats.textContent.includes('重试 0')&&!a.e.win.hidden===false);
a.click('pause');let time=a.e.stats.textContent;a.advance(1);check('暂停冻结模拟',a.e.stats.textContent===time);a.click('pause');
a.click('help');check('玩法说明按钮',!a.e['help-modal'].hidden);a.click('close-help');check('玩法说明关闭',a.e['help-modal'].hidden);
a.click('tests');check('自检按钮输出通过',a.e['test-result'].textContent.startsWith('PASS'));a.click('close-test');
const b=harness();b.click('demo');b.advance(7);check('可见示范按钮 → 连续摆荡 → 终点界面',!b.e.win.hidden,b.e['win-stat'].textContent);b.click('again');b.advance(.4);check('终点重玩按钮',b.e.win.hidden&&b.e.stats.textContent.includes('重试 0'));
const c=harness();c.click('start');c.advance(.5);c.key('KeyD');c.advance(1);c.key('Space');c.key('Space',true);c.advance(.15);
const hookLabel=[...c.drawCalls].reverse().find(x=>x.t==='E / 挂丝');
if(hookLabel){c.e.game.trigger('pointerdown',{button:0,clientX:hookLabel.x,clientY:hookLabel.y-50,pointerId:1});c.advance(.04);check('鼠标按住挂丝',c.e['web-status'].textContent.includes('蛛丝已连接'));c.e.game.trigger('pointerup',{});c.advance(.04);check('鼠标松开释放',!c.e['web-status'].textContent.includes('蛛丝已连接'));}else check('鼠标挂点可见',false);
c.key('KeyD',true);c.emit('blur');let before=c.e.stats.textContent;c.advance(1);check('窗口失焦暂停',c.e.stats.textContent===before&&c.e.pause.textContent==='继续');
const result={utc:new Date().toISOString(),status:checks.every(x=>x.pass)?'PASS':'FAIL',runtime:process.version,testMethod:'Node.js executes the exact inline scripts from index.html. Input integration uses a minimal DOM/canvas stub; this is NOT real browser rendering, OS keyboard input, or manual playtesting.',unity:'Blocked: no valid Unity Editor license',browserInteraction:'Not performed: browser tool denied file: protocol; no workaround attempted.',checks};
const output=path.join(__dirname,'..','Evidence','browser-demo-tests.json');fs.writeFileSync(output,JSON.stringify(result,null,2));
console.log(JSON.stringify(result,null,2));process.exitCode=result.status==='PASS'?0:1;
