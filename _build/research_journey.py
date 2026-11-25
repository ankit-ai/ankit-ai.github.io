"""Accessible, progressively enhanced introduction to the 2026 research journey."""
from html import escape
from datetime import date

CSS = """
.research-index .journey-hero{display:grid;grid-template-columns:1.08fr .92fr;
 gap:28px;padding:32px;margin-bottom:36px;background:var(--navy);color:#fff;
 border-radius:18px;box-shadow:0 14px 45px rgba(10,34,55,.12)}
.journey-hero .eyebrow{color:#bdabff;font-size:11px;margin-bottom:14px}
.journey-hero h1{font-size:40px;line-height:1.15;color:#fff;letter-spacing:-.03em;
 text-wrap:normal;margin-bottom:20px}
.journey-hero h1 span{display:block}
.journey-hero .journey-intro{font-size:16.5px;line-height:1.6;color:#d7e3ed;margin:0 0 16px}
.journey-hero .journey-stakes{color:#fff;font-size:16px;line-height:1.6;font-weight:600;
 margin:0 0 22px}
.journey-hero .journey-actions{display:flex;flex-wrap:wrap;gap:10px;font-size:13px}
.journey-actions a{display:inline-flex;align-items:center;gap:6px;border-radius:999px;
 padding:9px 13px;text-decoration:none;border:1px solid #96cbd0;color:#e3f6f5;
 font-weight:600;min-height:44px}
.journey-actions a:first-child{background:#d7f79a;border-color:#d7f79a;color:#17324f}
.journey-actions a:hover{background:#fff;color:#17324f}
.journey-actions a:focus-visible,.journey-tabs a:focus-visible,.journey-controls button:focus-visible{
 outline-color:#bdabff;outline-offset:4px}
.journey-hero figure{margin:0;min-width:0;display:flex;flex-direction:column}
.journey-hero figure img{width:100%;height:100%;min-height:265px;flex:1;object-fit:cover;
 border-radius:12px;border:0;background:#153e58}
.journey-hero figcaption{font-size:10.5px;color:#b8c8d3;margin-top:10px}
.journey-hero figcaption a{color:inherit}
.research-index .journey-byline{font-size:14px;color:var(--mut);margin:0 0 30px}
.research-journey{scroll-margin-top:100px}
.research-journey>h2{margin-top:0}
.journey-tabs{list-style:none;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));
 padding:0;margin:26px 0 20px;gap:8px}
.journey-tabs li{margin:0;min-width:0}
.journey-tabs a{display:flex;flex-direction:column;gap:7px;padding:13px 10px;
 border:1px solid var(--line);border-radius:10px;text-decoration:none;
 color:var(--ink2);font-size:13px;font-weight:650;min-height:77px}
.journey-tabs .step-number{font-size:11px;font-weight:600;color:var(--mut)}
.journey-tabs a:hover{border-color:var(--acc2);background:var(--tint)}
.journey-tabs a[aria-selected="true"]{background:var(--navy);color:#fff;border-color:var(--navy);
 box-shadow:inset 0 3px 0 var(--step-color)}
.journey-tabs a[aria-selected="true"] .step-number{color:var(--step-color)}
.journey-panel{padding:27px;border:1px solid var(--line);border-radius:14px;
 background:#fff;margin:0 0 24px;scroll-margin-top:105px}
.journey-panel .lab{color:var(--acc);margin-bottom:8px}
.journey-panel h3{font-size:27px;line-height:1.22;font-weight:680;
 text-transform:none;letter-spacing:-.025em;color:var(--ink);margin:0 0 12px}
.journey-problem{color:var(--ink2);font-size:16px;line-height:1.65;max-width:70ch;margin-bottom:24px}
.journey-stage{display:grid;grid-template-columns:1.05fr 1fr;gap:26px;align-items:center}
.journey-stage figure{margin:0;min-width:0}
.journey-stage img{width:100%;height:auto;border:0;border-radius:10px;background:#0b1325}
.journey-idea p{font-size:15.5px;line-height:1.65;color:var(--ink2);margin-bottom:14px}
.journey-idea .journey-example{font-size:13.5px;line-height:1.6;color:var(--mut);
 border-left:2px solid var(--tintline);padding-left:13px;margin:0}
.journey-paper{border-top:1px solid var(--hair);margin-top:24px;padding-top:17px}
.journey-paper .paper-title{font-size:14.5px;line-height:1.5;color:var(--ink);font-weight:600;
 display:block;text-decoration-color:var(--rule)}
.journey-paper .venue{font-size:12px;margin:6px 0 14px}
.journey-paper .actions{padding-bottom:0;border:0;font-size:12.5px}
.journey-controls{display:flex;align-items:center;justify-content:space-between;
 gap:15px;margin:0 0 17px}
.journey-controls button{font:inherit;font-size:13px;font-weight:600;cursor:pointer;
 padding:10px 15px;border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--acc);
 min-height:44px}
.journey-controls button:hover:not(:disabled){border-color:var(--acc2);background:var(--tint)}
.journey-controls button:disabled{opacity:.4;cursor:default}
.journey-controls .journey-progress{font-size:12.5px;color:var(--mut);text-align:center}
.journey-scope{font-size:12px;line-height:1.65;color:var(--mut);max-width:80ch}
.journey-scope time{white-space:nowrap}
.journey-end{margin:23px 0 0;padding:18px 20px;background:var(--tint);border:1px solid var(--tintline);
 border-radius:10px;font-size:16px;font-weight:600;color:var(--ink)}
.research-guides{margin-top:48px}
.research-guides>h2{margin-bottom:10px}
.research-guides .guide-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
 gap:16px;margin:22px 0}
.research-guides .guide-card{border:1px solid var(--line);border-radius:10px;padding:21px;
 min-width:0}
.research-guides .guide-card h3{font-size:17px;line-height:1.35;letter-spacing:-.015em;
 text-transform:none;color:var(--ink);margin:0 0 10px}
.research-guides .guide-card p{font-size:13.5px;line-height:1.65;color:var(--mut)}
.research-guides .guide-card>a{font-size:13px;font-weight:600}
@media(max-width:760px){
 .research-index .journey-hero{grid-template-columns:1fr;padding:25px;gap:22px}
 .journey-hero h1{font-size:36px;max-width:23ch}
 .journey-hero figure{grid-row:1}
 .journey-hero figure img{height:190px;min-height:190px;flex:none;object-position:50% 46%}
 .journey-hero figcaption{font-size:10px;margin-top:6px}
 .journey-tabs{grid-template-columns:repeat(3,minmax(0,1fr))}
 .journey-tabs a{min-height:67px;padding:11px 13px;gap:4px}
 .journey-panel{padding:22px}
 .journey-stage{grid-template-columns:1fr;gap:22px}
 .journey-panel h3{font-size:25px}
 .research-guides .guide-grid{grid-template-columns:1fr}
}
@media(max-width:410px){
 .research-index .journey-hero{padding:21px}
 .journey-hero h1{font-size:32px}
 .journey-hero .journey-intro,.journey-hero .journey-stakes{font-size:15px}
 .journey-controls{gap:8px}
 .journey-controls button{padding:10px 11px;font-size:12px}
 .journey-controls .journey-progress{font-size:11px}
}
"""

SCRIPT = r"""<script>
(()=>{
 const root=document.querySelector('[data-research-journey]');
 if(!root)return;
 const list=root.querySelector('[data-journey-tabs]');
 const tabs=Array.from(list.querySelectorAll('[data-step]'));
 const panels=Array.from(root.querySelectorAll('[data-journey-panel]'));
 const controls=root.querySelector('.journey-controls');
 const previous=controls.querySelector('[data-previous]');
 const next=controls.querySelector('[data-next]');
 const progress=controls.querySelector('[data-progress]');
 let current=0;
 list.setAttribute('role','tablist');
 list.setAttribute('aria-label','Six research questions');
 tabs.forEach((tab,i)=>{
   tab.parentElement.setAttribute('role','presentation');
   tab.setAttribute('role','tab');
   tab.setAttribute('aria-controls',panels[i].id);
   panels[i].setAttribute('role','tabpanel');
   panels[i].setAttribute('aria-labelledby',tab.id);
   panels[i].tabIndex=0;
 });
 function show(index,updateHash=false){
   current=Math.max(0,Math.min(panels.length-1,index));
   tabs.forEach((tab,i)=>{
     const selected=i===current;
     tab.setAttribute('aria-selected',String(selected));
     tab.tabIndex=selected?0:-1;
     panels[i].hidden=!selected;
   });
   previous.disabled=current===0;
   next.disabled=current===panels.length-1;
   previous.textContent=current===0?'← Previous':'← '+tabs[current-1].dataset.verb;
   next.textContent=current===panels.length-1?'Journey complete':tabs[current+1].dataset.verb+' →';
   progress.textContent=(current+1)+' of '+panels.length+' · '+tabs[current].dataset.verb;
   if(updateHash)history.replaceState(null,'','#'+panels[current].id);
 }
 function fromHash(){
   const id=location.hash.slice(1);
   const match=panels.findIndex(panel=>panel.id===id);
   if(match>=0)show(match);
 }
 tabs.forEach((tab,i)=>{
   tab.addEventListener('click',event=>{event.preventDefault();show(i,true)});
   tab.addEventListener('keydown',event=>{
     if(event.key===' '){event.preventDefault();show(i,true);return;}
     let target;
     if(event.key==='ArrowRight')target=(current+1)%tabs.length;
     if(event.key==='ArrowLeft')target=(current-1+tabs.length)%tabs.length;
     if(event.key==='Home')target=0;
     if(event.key==='End')target=tabs.length-1;
     if(target!==undefined){event.preventDefault();show(target,true);tabs[target].focus();}
   });
 });
 function advance(delta,focus=false){
   show(current+delta,true);
   panels[current].scrollIntoView({block:'start'});
   if(focus)panels[current].focus({preventScroll:true});
 }
 previous.addEventListener('click',()=>advance(-1,true));
 next.addEventListener('click',()=>advance(1,true));
 panels.forEach(panel=>{
   let start;
   const art=panel.querySelector('figure');
   art.addEventListener('touchstart',event=>{
     const point=event.changedTouches[0];start=[point.clientX,point.clientY];
   },{passive:true});
   art.addEventListener('touchend',event=>{
     if(!start)return;
     const point=event.changedTouches[0],dx=point.clientX-start[0],dy=point.clientY-start[1];
     if(Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy)*1.3)advance(dx<0?1:-1);
     start=null;
   },{passive:true});
 });
 window.addEventListener('hashchange',fromHash);
 controls.hidden=false;
 show(0);
 fromHash();
})();
</script>"""


def render(data, papers):
    e = lambda value: escape(str(value), quote=True)
    photo = data["photo"]
    lead, separator, rest = data["title"].partition(". ")
    headline = ('<span>%s.</span>%s' % (e(lead), e(rest))
                if separator else e(data["title"]))
    checked = date.fromisoformat(data["checked"])
    checked_label = "%s %d, %d" % (checked.strftime("%B"), checked.day, checked.year)
    out = [
        '<div class="research-index">\n',
        '<section class="journey-hero" aria-labelledby="journey-title">\n<div>',
        '<p class="eyebrow">Research / 2026</p>',
        '<h1 id="journey-title">%s</h1>' % headline,
        '<p class="journey-intro">%s</p>' % e(data["intro"]),
        '<p class="journey-stakes">%s</p>' % e(data["stakes"]),
        '<div class="journey-actions"><a href="#research-journey">Follow the six questions ↓</a>'
        '<a href="%s">Open the 8-slide PDF ↗</a></div></div>' % e(data["pdf"]),
        '<figure><img src="%s" width="900" height="900" fetchpriority="high" '
        'decoding="async" alt="%s"><figcaption><a href="%s" rel="noopener">%s</a>'
        '</figcaption></figure></section>\n'
        % (e(data["hero_image"]), e(data["hero_alt"]), e(photo["profile"]), e(photo["credit"])),
        '<p class="journey-byline">%s</p>\n' % e(data["byline"]),
        '<section class="research-journey" id="research-journey" data-research-journey '
        'aria-labelledby="journey-heading">\n',
        '<h2 id="journey-heading">Six problems. Six research questions.</h2>',
        '<p class="small mut">Follow the trip, then open the paper on the part you care about.</p>',
        '<nav aria-label="Research journey"><ol class="journey-tabs" data-journey-tabs>',
    ]
    for i, step in enumerate(data["steps"]):
        out.append(
            '<li><a href="#journey-step-%d" id="journey-tab-%d" data-step="%d" data-verb="%s" '
            'style="--step-color:%s"><span class="step-number">%02d</span>%s</a></li>'
            % (i+1, i+1, i, e(step["verb"]), e(step["color"]), i+1, e(step["verb"]))
        )
    out.append('</ol></nav>')
    for i, step in enumerate(data["steps"]):
        p = papers[step["slug"]]
        path = "/papers/%s/" % p["slug"]
        primary = p.get("anthology_url") or p.get("publisher_url") or (
            "https://arxiv.org/abs/" + p["arxiv_id"])
        out += [
            '<section class="journey-panel" id="journey-step-%d" data-journey-panel>\n' % (i+1),
            '<span class="lab">%02d / %s</span><h3>%s</h3><p class="journey-problem">%s</p>'
            % (i+1, e(step["verb"]), e(step["question"]), e(step["problem"])),
            '<div class="journey-stage"><figure><img src="%s" width="960" height="508" '
            'loading="lazy" decoding="async" alt="%s"></figure><div class="journey-idea">'
            % (e(step["image"]), e(step["alt"])),
            '<span class="lab">The research idea</span><p>%s</p>'
            '<p class="journey-example"><strong>Trip example:</strong> %s</p></div></div>'
            % (e(step["idea"]), e(step["example"])),
            '<div class="journey-paper"><a class="paper-title" href="%s">%s</a>'
            '<p class="venue">%s%s</p>'
            % (e(path), e(p["title"]), e(p["venue_short"]),
               " · Acceptance reported by the authors; proceedings forthcoming."
               if p.get("status") == "accepted" else ""),
            '<p class="actions"><a href="%s">Read the paper + results</a>'
            '<a href="%s%s">Paper PDF</a><a href="%s" rel="noopener">Primary source ↗</a></p>'
            '</div></section>\n' % (e(path), e(path), e(p["pdf_filename"]), e(primary)),
        ]
    out += [
        '<div class="journey-controls" hidden><button type="button" data-previous>← Previous</button>'
        '<span class="journey-progress" data-progress aria-live="polite" aria-atomic="true"></span>'
        '<button type="button" data-next>Next →</button></div>',
        '<p class="journey-scope">%s Public records checked <time datetime="%s">%s</time>.</p>'
        % (e(data["scope"]), e(data["checked"]), e(checked_label)),
        '<p class="journey-end">From remembering a user to keeping a task moving.<br>'
        'Which of these breaks first in your agents?</p>',
        '</section>\n',
    ]
    return "".join(out)
