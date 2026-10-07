"""Exercise the complete pass UI in Aion's actual WebKit with native item icons.

The isolated fixture simulates state and purchases; it never touches a real
account, game process or player database. PNG screenshots are QA artifacts only.
"""
import argparse
import copy
import ctypes as c
import http.server
import json
import os
from pathlib import Path
import threading
import time
import statistics
import xml.etree.ElementTree as ET
from functools import lru_cache
from urllib.parse import parse_qs,urlparse
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
MEDIA=ROOT/'game-server/config/season-pass/media'

@lru_cache(maxsize=1)
def native_catalog():
    # Match the running 4.8 data. The development checkout can also contain a
    # different decomposable schema; never reinterpret that as live box contents.
    catalog=ROOT/'target-deploy/game-server/data/static_data'
    items={int(e.get('id')):e.attrib for e in ET.parse(catalog/'items/item_templates.xml').getroot()}
    boxes={int(e.get('item_id')):e for e in ET.parse(catalog/'decomposable_items/decomposable_items.xml').getroot()}
    return items,boxes

def fixture():
    now=int(time.time()*1000)
    state=dict(character='Astra',tier=0,kinah=4200000,level=7,xp=7600,active=True,claimable=True,now=now,starts=now-86400000,
        ends=1796076000000,claimsEnd=1796680800000,request='fixture-only-0',notice='',history=[],
        season=dict(id='2026-autumn',serverName='Aetherfall',name='Ascendant Dawn',subtitle='Rise through the ranks. Leave your mark on the skies.',levels=30,xpPerLevel=1000,premiumKinah=1500000,advancedKinah=3000000,advancedLevels=10),rewards=[],missions=[])
    items,boxes=native_catalog()
    for line in (ROOT/'game-server/config/season-pass/rewards.tsv').read_text(encoding='utf-8').splitlines():
        if line.startswith('#'):continue
        level,track,item,qty,name,description,bundle=line.split('\t')
        item=int(item)
        if bundle!='NONE':item={'NORMAL':188053750,'GREATER':188053761,'MAJOR':188053772}[bundle]+10 # Bard fixture
        box=boxes.get(item);contents=[]
        if box is not None:
            for entry in box.findall('items/item'):
                if entry.get('race','PC_ALL') not in ['PC_ALL','ELYOS']:continue
                iid=int(entry.get('id'));t=items[iid]
                contents.append(dict(item=iid,name=t['name'],min=int(entry.get('min_count','1')),max=int(entry.get('max_count',entry.get('min_count','1'))),requiredLevel=int(t['level'])))
        mode='choice' if box is not None and box.get('selectable')=='true' else 'random' if box is not None and len(box.findall('items'))>1 else 'contents'
        state['rewards'].append(dict(level=int(level),track=int(track),item=item,quantity=int(qty),name=items[item]['name'],description=description,requiredLevel=int(items[item]['level']),claimed=False,needsClass=False,box=dict(mode=mode,items=contents),available=int(track)==0 and int(level)<=7))
    for i,line in enumerate((ROOT/'game-server/config/season-pass/missions.tsv').read_text(encoding='utf-8').splitlines()):
        if line.startswith('#'):continue
        mid,cadence,event,target,xp,name,description=line.split('\t',6);target=int(target)
        progress=target if event=='LOGIN' else int(target*.4)
        state['missions'].append(dict(id=mid,cadence=cadence,name=name,description=description,target=target,xp=int(xp),progress=progress,complete=progress==target,reset=now+3600000*(5 if cadence=='DAILY' else 53)))
    return state

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--browser-bin',type=Path,required=True);parser.add_argument('--viewport',help='Focused rerender, e.g. 1920x1052');parser.add_argument('--profile',action='store_true',help='Measure input-to-paint latency with isolated visual probes instead of purchases');parser.add_argument('--baseline-only',action='store_true',help='Measure production styles without diagnostic overrides');parser.add_argument('--flash-check',action='store_true',help='Sample every rendered frame through a real automatic refresh in transparent mode');parser.add_argument('--report',type=Path,help='Save profile measurements as JSON');args=parser.parse_args()
    state=fixture();posts=[];receipts={};sequence=[0];gets=[]
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*unused):pass
        def send(self,data,content='application/json'):
            if isinstance(data,dict):
                sequence[0]+=1;state['request']='fixture-only-'+str(sequence[0]);state['now']=int(time.time()*1000);data=json.dumps(state)
            data=data if isinstance(data,bytes) else data.encode();self.send_response(200);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_GET(self):
            path=urlparse(self.path).path;gets.append(path)
            if path=='/market/pass':
                html=(MEDIA/'pass.html').read_bytes()
                if args.profile:html=html.replace(b'<script src=',b'<script>window.__profileIntervals=[];window.setInterval=function(fn,ms){window.__profileIntervals.push({fn:fn,ms:ms});return window.__profileIntervals.length;};</script><script src=',1)
                self.send(html,'text/html; charset=utf-8')
            elif path.startswith('/market/pass/media/'):
                f=MEDIA/path.rsplit('/',1)[1]
                optimized=MEDIA/'optimized'/f.name
                if f.suffix=='.png' and optimized.is_file():f=optimized
                self.send(f.read_bytes(),{'.css':'text/css','.js':'application/javascript','.png':'image/png'}[f.suffix])
            elif path=='/market/pass/state':self.send(state)
            else:self.send_error(404)
        def do_POST(self):
            form={k:v[0] for k,v in parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode()).items()}
            assert form['session_id']=='fixture' and form['request'].startswith('fixture-only-')
            posts.append(form)
            if form['request'] in receipts:self.send(state);return
            action=form['action']
            if action=='purchase':
                target=int(form['tier']);assert target>state['tier'];cost=(3000000 if target==2 else 1500000)-(1500000 if state['tier']==1 else 0)
                assert state['kinah']>=cost;state['kinah']-=cost;state['tier']=target
                if target==2:state['xp']=min(30000,state['xp']+10000);state['level']=state['xp']//1000
                state['notice']='Premium track unlocked.'
            else:
                selected=[r for r in state['rewards'] if r['available'] and (action=='claimAll' or (int(form['level'])==r['level'] and int(form['track'])==r['track']))]
                assert selected
                for r in selected:
                    r['claimed']=True;state['history'].insert(0,dict(reward_level=r['level'],track=r['track'],item_id=r['item'],quantity=r['quantity'],claimed_at=int(time.time()*1000)))
                state['notice']='Claimed rewards. Collect them from Black Cloud mail.'
            for r in state['rewards']:r['available']=not r['claimed'] and r['level']<=state['level'] and r['track']<=state['tier']
            receipts[form['request']]=True;self.send(state)
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    directory=os.add_dll_directory(str(args.browser_bin.resolve()));lib=c.CDLL(str(args.browser_bin/'Awesomium.dll'));ptr=c.c_void_p
    def api(name,result,*parameters):f=getattr(lib,name);f.restype=result;f.argtypes=list(parameters);return f
    initialize=api('awe_webcore_initialize_default',None);update=api('awe_webcore_update',None);shutdown=api('awe_webcore_shutdown',None)
    create=api('awe_webcore_create_webview',ptr,c.c_int,c.c_int,c.c_bool);destroy=api('awe_webview_destroy',None,ptr)
    make=api('awe_string_create_from_wide',ptr,c.c_wchar_p,c.c_size_t);free=api('awe_string_destroy',None,ptr)
    load=api('awe_webview_load_url',None,ptr,ptr,ptr,ptr,ptr);evaluate=api('awe_webview_execute_javascript_with_result',ptr,ptr,ptr,ptr,c.c_int)
    text=api('awe_jsvalue_to_string',ptr,ptr);utf8=api('awe_string_to_utf8',c.c_size_t,ptr,ptr,c.c_size_t);jsfree=api('awe_jsvalue_destroy',None,ptr)
    render=api('awe_webview_render',ptr,ptr);pixels=api('awe_renderbuffer_get_buffer',ptr,ptr);rowspan=api('awe_renderbuffer_get_rowspan',c.c_int,ptr)
    move=api('awe_webview_inject_mouse_move',None,ptr,c.c_int,c.c_int);down=api('awe_webview_inject_mouse_down',None,ptr,c.c_int);up=api('awe_webview_inject_mouse_up',None,ptr,c.c_int)
    dirty=api('awe_webview_is_dirty',c.c_bool,ptr)
    transparent=api('awe_webview_set_transparent',None,ptr,c.c_bool)
    tip_events=[]
    tip_callback=c.CFUNCTYPE(None,ptr,ptr)
    def on_tooltip(webview,value):
        buf=c.create_string_buffer(4096);utf8(value,buf,len(buf));tip_events.append(buf.value.decode())
    tip_listener=tip_callback(on_tooltip)
    set_tooltip=api('awe_webview_set_callback_change_tooltip',None,ptr,tip_callback)
    initialize();bridge=c.CDLL(str(args.browser_bin/'AionIconBridge.dll'));start=bridge.AionIconBridgeInitialize;start.restype=c.c_int;start.argtypes=[];assert start()==1
    empty=make('',0);views=[];out=ROOT/'output/playwright/season-pass';out.mkdir(parents=True,exist_ok=True)
    def js(view,code):
        code='String('+code+')'
        s=make(code,len(code));value=evaluate(view,s,empty,1000);free(s)
        if not value:return ''
        string=text(value);buf=c.create_string_buffer(65536);utf8(string,buf,len(buf));free(string);jsfree(value);return buf.value.decode()
    def pump(seconds=.2):
        until=time.monotonic()+seconds
        while time.monotonic()<until:update();time.sleep(.015)
    def wait(view,code,expected,seconds=12):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            pump(.1)
            if js(view,code)==expected:return
        raise AssertionError('Browser did not reach '+expected+': '+js(view,code)+'; status='+js(view,"document.getElementById('status')&&document.getElementById('status').textContent"))
    def click(view,selector):
        js(view,'(function(){var n=document.querySelector('+json.dumps(selector)+');n.scrollIntoView(false);for(var p=n.parentNode;p&&p.getBoundingClientRect;p=p.parentNode){var s=getComputedStyle(p),r=n.getBoundingClientRect(),b=p.getBoundingClientRect();if(s.overflowX==="auto"||s.overflowX==="scroll"){if(r.right>b.right)p.scrollLeft+=r.right-b.right+8;if(r.left<b.left)p.scrollLeft-=b.left-r.left+8;}}return "ok";}())');pump(.03)
        point=json.loads(js(view,"(function(){var r=document.querySelector("+json.dumps(selector)+").getBoundingClientRect();return JSON.stringify([Math.round((r.left+r.right)/2),Math.round((r.top+r.bottom)/2)]);}())"))
        move(view,*point);pump(.03);down(view,0);up(view,0);pump(.15)
    def screenshot(view,name,width,height):
        pump(.2);buf=render(view);assert buf;Image.frombytes('RGBA',(width,height),c.string_at(pixels(buf),rowspan(buf)*height),'raw','BGRA',rowspan(buf)).save(out/name)
    def check_frames(view,width,height):
        samples=0;blank=0;null=0;minimum=255;paints=0;start=time.monotonic();before=gets.count('/market/pass/state')
        while time.monotonic()-start<36:
            update();was_dirty=dirty(view);buf=render(view)
            if not buf:null+=1
            else:
                samples+=1;paints+=int(was_dirty);pointer=pixels(buf);stride=rowspan(buf)
                alpha=[c.c_ubyte.from_address(pointer+int(height*y)*stride+int(width*x)*4+3).value for x,y in [(0.01,0.01),(.5,.01),(.99,.01),(.01,.5),(.5,.5),(.99,.5),(.01,.99),(.5,.99),(.99,.99)]]
                minimum=min(minimum,min(alpha))
                if max(alpha)==0:blank+=1
            time.sleep(.008)
        report=dict(viewport=[width,height],transparent_view=True,seconds=round(time.monotonic()-start,2),sampled_frames=samples,dirty_frames=paints,null_buffers=null,fully_transparent_sampled_frames=blank,minimum_sampled_alpha=minimum,automatic_refreshes=gets.count('/market/pass/state')-before)
        print(json.dumps(report),flush=True)
        if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
        assert not blank,'Browser delivered a fully transparent frame after the page loaded'
        assert report['automatic_refreshes']>0,'Automatic refresh did not execute'
    def profile(view,width,height):
        def measure(action):
            pump(.06);render(view)
            start=time.perf_counter();action()
            deadline=start+2
            while time.perf_counter()<deadline:
                update()
                if dirty(view):render(view);return (time.perf_counter()-start)*1000
                time.sleep(.001)
            return None
        def summary(values):
            valid=sorted(v for v in values if v is not None)
            return dict(samples=len(values),painted=len(valid),median_ms=round(statistics.median(valid),2) if valid else None,p95_ms=round(valid[max(0,int(len(valid)*.95)-1)],2) if valid else None)
        cases=[('baseline',''),('no-blur','*,*:before,*:after{-webkit-box-shadow:none!important;box-shadow:none!important;text-shadow:none!important;}'),('fast-images','img{image-rendering:-webkit-optimize-contrast!important;}'),('cached-layers','.art-frame,.track-crest,.level-crest,.world-scene{-webkit-transform:translateZ(0);}'),('nine-slice','.art-frame{border:solid transparent;border-width:22px 18px 18px;-webkit-border-image:url(/market/pass/media/aether-frame.png) 230 170 150 170 stretch;}.pass-shell>.art-frame{border-width:26px 35px 25px;-webkit-border-image:url(/market/pass/media/pass-panel.png) 180 130 140 130 stretch;}')]
        if args.baseline_only:cases=cases[:1]
        results=[]
        for name,css in cases:
            if name=='nine-slice':js(view,"(function(){window.__originalFrames=[];var a=document.querySelectorAll('img.art-frame');for(var i=0;i<a.length;i++){var n=document.createElement('span');n.className=a[i].className;window.__originalFrames.push([a[i],n]);a[i].parentNode.replaceChild(n,a[i]);}return true;}())")
            js(view,"(function(){var n=document.getElementById('profile-style');if(n)n.parentNode.removeChild(n);n=document.createElement('style');n.id='profile-style';n.textContent="+json.dumps(css)+";document.head.appendChild(n);document.querySelector('[data-view=\"rewards\"]').click();document.getElementById('rewards-view').scrollTop=0;return true;}())")
            move(view,0,0);pump(.5);render(view)
            points=json.loads(js(view,"(function(){var n=document.querySelectorAll('.reward-cell'),a=[];for(var i=0;i<2;i++){var r=n[i].getBoundingClientRect();a.push([Math.round((r.left+r.right)/2),Math.round(r.top+100)]);}return JSON.stringify(a);}())"))
            hovers=[measure(lambda i=i:move(view,*points[i%2])) for i in range(16)]
            scrolls=[measure(lambda i=i:js(view,"(function(){document.getElementById('rewards-view').scrollTop="+str(120 if i%2==0 else 0)+";return true;}())")) for i in range(16)]
            tabs=[measure(lambda i=i:js(view,"(function(){document.querySelector('[data-view=\""+['missions','rewards','passes','rewards'][i%4]+"\"]').click();return true;}())")) for i in range(12)]
            result=dict(case=name,hover=summary(hovers),scroll=summary(scrolls),tabs=summary(tabs));results.append(result);print(json.dumps(result),flush=True)
            if name=='nine-slice':js(view,"(function(){for(var i=0;i<window.__originalFrames.length;i++){var a=window.__originalFrames[i];a[1].parentNode.replaceChild(a[0],a[1]);}return true;}())")
        report=dict(viewport=[width,height],engine='Installed Aion Awesomium/WebKit, isolated fixture, input-to-dirty-render latency; includes browser IPC, excludes game texture upload',results=results)
        if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
        return report
    try:
        sizes=[tuple(map(int,args.viewport.split('x')))] if args.viewport else [(1024,740),(1366,740),(1920,1052),(3440,1412),(768,600)]
        for width,height in sizes:
            state.clear();state.update(fixture());receipts.clear();posts.clear()
            view=create(width,height,False);views.append(view);set_tooltip(view,tip_listener)
            if args.flash_check:transparent(view,True)
            url=f'http://127.0.0.1:{server.server_port}/market/pass?session_id=fixture'
            s=make(url,len(url));load(view,s,empty,empty,empty);free(s)
            wait(view,"document.getElementById('character')&&document.getElementById('character').textContent",'Astra')
            wait(view,"(function(){var a=document.querySelectorAll('.world-scene>img,.level-crest,.art-frame,.track-crest');for(var i=0;i<a.length;i++)if(!a[i].complete||!a[i].naturalWidth)return 'loading';return 'ready';}())",'ready')
            assert js(view,"document.getElementById('server-name').textContent")=='AETHERFALL'
            assert js(view,"(function(){var panel=document.querySelector('.hero-copy'),r=panel.getBoundingClientRect(),art=document.querySelector('.season-art').getBoundingClientRect(),crest=document.querySelector('.level-crest').getBoundingClientRect(),frame=panel.querySelector('.hero-frame'),content=panel.querySelector('.hero-content'),n=content.children,b=content.getBoundingClientRect();if(!frame||getComputedStyle(frame).webkitBorderImage.indexOf('aether-frame.png')<0||getComputedStyle(content).textAlign!=='center'||Math.abs((b.top+b.bottom-r.top-r.bottom)/2)>1||Math.abs((b.left+b.right-r.left-r.right)/2)>1||r.top<art.top||r.bottom>art.bottom||r.right>crest.left)return false;for(var i=0;i<n.length;i++){if(getComputedStyle(n[i]).display==='none')continue;var c=n[i].getBoundingClientRect();if(c.top<r.top+24||c.bottom>r.bottom-18||c.left<r.left+28||c.right>r.right-28)return false;}return true;}())")=='true','season summary must be centered inside its artwork without clipping or overlapping the level crest'
            wait(view,"(function(){var i=document.querySelector('.item-icon');return i&&i.naturalWidth>0?'yes':'no';}())",'yes')
            if args.flash_check:check_frames(view,width,height);destroy(view);views.remove(view);continue
            if args.profile:profile(view,width,height);destroy(view);views.remove(view);continue
            geometry=json.loads(js(view,"(function(){var a=[],n=document.querySelectorAll('.reward-cell');for(var i=0;i<n.length;i++){var r=n[i].getBoundingClientRect(),title=n[i].querySelector('strong').getBoundingClientRect(),status=n[i].querySelector('.reward-state').getBoundingClientRect(),icon=n[i].querySelector('.icon-well').getBoundingClientRect();a.push([r.left,r.right,icon.bottom,title.top,title.bottom,status.top,parseFloat(getComputedStyle(n[i].querySelector('strong')).fontSize)]);}return JSON.stringify(a);}())"));assert all(icon_bottom<title_top and title_bottom<status_top and size>=15 for a,b,icon_bottom,title_top,title_bottom,status_top,size in geometry),geometry
            assert width<1100 or all(a>=0 and b<=width for a,b,*unused in geometry),geometry
            assert js(view,"document.querySelector('.item-icon').title.indexOf('nc://aion.ItemInfo/ItemTooltip?item=')===0")=='true'
            assert js(view,"document.querySelector('.reward-cell').title.indexOf('nc://aion.ItemInfo/ItemTooltip?item=')===0")=='true'
            if height<650:js(view,"(function(){document.querySelector('.item-icon').scrollIntoView(false);return 'ok';}())");pump(.05)
            hover_point=json.loads(js(view,"(function(){var r=document.querySelector('.item-icon').getBoundingClientRect();return JSON.stringify([Math.round((r.left+r.right)/2),Math.round((r.top+r.bottom)/2)]);}())"))
            move(view,0,0);pump(.08);tip_events.clear();move(view,*hover_point);pump(.8);assert any(t.startswith('nc://aion.ItemInfo/ItemTooltip?item=') for t in tip_events),tip_events
            assert js(view,"document.querySelector('main').scrollWidth>document.querySelector('main').clientWidth")=='false'
            screenshot(view,f'rewards-{width}x{height}.png',width,height)
            assert js(view,"document.querySelectorAll('.mission-row,.pass-shell,.history-row').length")=='0','hidden pages must render only when opened'
            js(view,"(function(){window.__qaTrack=document.querySelector('.reward-cell');window.__qaTitle=document.getElementById('season-name').firstChild;return true;}())")
            state['notice']='Fixture refresh complete.';click(view,'#refresh');wait(view,"document.getElementById('status').textContent",'Fixture refresh complete.')
            assert js(view,"window.__qaTrack===document.querySelector('.reward-cell')&&window.__qaTitle===document.getElementById('season-name').firstChild")=='true','unchanged refresh must preserve reward and header DOM'
            state['notice']=''
            click(view,'#previous');click(view,'.reward-cell.available');assert not posts,'inspection must not deliver a reward'
            click(view,'#dialog-confirm');wait(view,"document.querySelector('[data-reward=\"1:0\"]').className.indexOf('claimed')>=0",'true')
            assert len(posts)==1 and posts[-1]['action']=='claim'
            click(view,'[data-view="passes"]')
            wait(view,"(function(){var a=document.querySelectorAll('.pass-shell .art-frame,.pass-crest');for(var i=0;i<a.length;i++)if(!a[i].complete||!a[i].naturalWidth)return 'loading';return 'ready';}())",'ready')
            assert js(view,"(function(){var a=document.querySelector('.pass-shell .art-frame').getBoundingClientRect(),b=document.querySelector('.pass-shell').getBoundingClientRect();return Math.abs(a.left-b.left)<2&&Math.abs(a.right-b.right)<2;}())")=='true','artwork must belong to each purchase card'
            screenshot(view,f'passes-{width}x{height}.png',width,height)
            click(view,'[data-buy="1"]');assert len(posts)==1,'opening purchase must not charge'
            assert '1,500,000' in js(view,"document.getElementById('dialog-body').textContent")
            screenshot(view,f'purchase-{width}x{height}.png',width,height)
            click(view,'#dialog-confirm');wait(view,"document.getElementById('owned-tier').textContent",'Premium Pass');assert state['kinah']==2700000
            click(view,'[data-buy="2"]');assert '1,500,000' in js(view,"document.getElementById('dialog-body').textContent")
            click(view,'#dialog-confirm');wait(view,"document.getElementById('owned-tier').textContent",'Advanced Premium');assert state['level']==17 and state['kinah']==1200000
            click(view,'[data-view="rewards"]');click(view,'[data-chapter="5"]');click(view,'[data-reward="30:2"]')
            assert int(js(view,"document.querySelectorAll('.box-item').length"))==14,'Advanced finale must preview all native weapon/shield choices; title='+js(view,"document.getElementById('dialog-title').textContent")
            assert js(view,"document.querySelector('.dialog-item').title.indexOf('nc://aion.ItemInfo/ItemTooltip?item=188053646&count=1')===0")=='true'
            assert js(view,"(function(){var a=document.querySelectorAll('.box-icon');for(var i=0;i<a.length;i++)if(a[i].title.indexOf('nc://aion.ItemInfo/ItemTooltip?item=')!==0)return false;return true;}())")=='true'
            for selector in ['.dialog-item','.box-icon']:
                hover_point=json.loads(js(view,"(function(){var r=document.querySelector("+json.dumps(selector)+").getBoundingClientRect();return JSON.stringify([Math.round((r.left+r.right)/2),Math.round((r.top+r.bottom)/2)]);}())"))
                move(view,0,0);pump(.08);tip_events.clear();move(view,*hover_point);pump(.8);assert any(t.startswith('nc://aion.ItemInfo/ItemTooltip?item=') for t in tip_events),(selector,tip_events,hover_point)
            assert js(view,"(function(){var h=document.getElementById('dialog-title').getBoundingClientRect(),d=document.querySelector('.dialog').getBoundingClientRect();return h.top>=d.top&&h.bottom<=d.bottom;}())")=='true','reward title remains visible when the dialog opens'
            wait(view,"(function(){var a=document.querySelectorAll('.box-icon');for(var i=0;i<a.length;i++)if(!a[i].naturalWidth)return 'loading';return 'ready';}())",'ready')
            screenshot(view,f'weapon-choice-{width}x{height}.png',width,height)
            click(view,'#dialog-cancel')
            click(view,'[data-view="missions"]');assert int(js(view,"document.querySelectorAll('.mission-row').length"))==5
            screenshot(view,f'missions-{width}x{height}.png',width,height)
            click(view,'[data-cadence="WEEKLY"]');assert int(js(view,"document.querySelectorAll('.mission-row').length"))==6
            js(view,"(function(){window.__qaMission=document.querySelector('.mission-row');return true;}())")
            state['notice']='Mission refresh complete.';click(view,'#refresh');wait(view,"document.getElementById('status').textContent",'Mission refresh complete.')
            assert js(view,"window.__qaMission===document.querySelector('.mission-row')")=='true','unchanged refresh must preserve mission DOM'
            next(m for m in state['missions'] if m['cadence']=='WEEKLY')['progress']+=1
            state['notice']='Mission progress updated.';click(view,'#refresh');wait(view,"document.getElementById('status').textContent",'Mission progress updated.')
            assert js(view,"window.__qaMission!==document.querySelector('.mission-row')")=='true','changed mission progress must update the visible page'
            state['notice']=''
            click(view,'[data-view="rewards"]');click(view,'#claim-all');before=len(posts);click(view,'#dialog-confirm');pump(.5)
            assert len(posts)==before+1 and len(state['history'])==51
            click(view,'[data-view="history"]');assert int(js(view,"document.querySelectorAll('.history-row').length"))==51
            print(f'OK: actual Aion WebKit {width}x{height}: native icons, non-overlapping 15px reward labels, native hover events on grid/detail/box contents, track bounds, free claim, purchases, differential upgrade, boost, mission filters, claim-all and history.')
            destroy(view);views.remove(view)
        assert not any('/media/icons/' in path for path in gets),'native icons must not download from fixture HTTP'
        print('OK: original client artwork served by native icon bridge; zero item-image HTTP downloads. Screenshots:',out)
    finally:
        for view in views:destroy(view)
        free(empty);shutdown();directory.close();server.shutdown()
if __name__=='__main__':
    try:main()
    except Exception as e:print('FAIL:',e);raise
