
(function(){
  var el=document.getElementById('countdown');
  var target=new Date(document.body.dataset.meeting);
  var what=(document.body.dataset.meetingLabel||'standup').toLowerCase();
  function tick(){
    var d=Math.floor((target-new Date())/1000);
    if(d<=0){el.textContent=what+' started';el.classList.add('soon');return}
    var h=Math.floor(d/3600),m=Math.floor(d%3600/60);
    el.textContent=(h?h+'h ':'')+m+'m to '+what;
    if(d<1800)el.classList.add('soon');
  }
  if(el&&!isNaN(target)){tick();setInterval(tick,20000)}
  function putPlain(s){
    // Slack only turns `foo` into code when the clipboard carries plain text,
    // so never let a rich-text flavour reach it.
    if(navigator.clipboard&&navigator.clipboard.writeText){
      return navigator.clipboard.writeText(s).catch(function(){legacy(s)});
    }
    legacy(s);
  }
  function legacy(s){
    var a=document.createElement('textarea');
    a.value=s;a.setAttribute('readonly','');
    a.style.cssText='position:fixed;top:-1000px';
    document.body.appendChild(a);a.select();
    try{document.execCommand('copy')}finally{document.body.removeChild(a)}
  }
  document.querySelectorAll('.copy').forEach(function(b){
    b.addEventListener('click',function(){
      putPlain(b.dataset.copy);
      var o=b.textContent;b.textContent='copied';
      setTimeout(function(){b.textContent=o},1200);
    });
  });
  var t=document.getElementById('scriptonly');
  if(t)t.addEventListener('click',function(){
    document.body.classList.toggle('script-only');
    t.textContent=document.body.classList.contains('script-only')
      ?'Show everything':'Japanese only';
  });

  // The view lives on the body, so CSS does the switching and nothing reloads.
  // A hash link from one view to the other lands on the right ticket because we
  // switch first and let the browser scroll after.
  var tabs=[].slice.call(document.querySelectorAll('.views button'));
  var where={};
  function show(view,remember){
    if(!tabs.length)return;
    var from=document.body.dataset.view;
    if(from&&from!==view)where[from]=window.scrollY;
    document.body.dataset.view=view;
    tabs.forEach(function(b){b.setAttribute('aria-selected',b.dataset.view===view)});
    if(remember!==false)try{sessionStorage.setItem('desk-view',view)}catch(e){}
    // Coming back to a view lands where you left it. Arriving for the first
    // time starts at the top, not halfway down because the other view was.
    if(from&&from!==view&&!location.hash)window.scrollTo(0,where[view]||0);
  }
  tabs.forEach(function(b){
    b.addEventListener('click',function(){show(b.dataset.view)});
  });
  document.addEventListener('click',function(e){
    var a=e.target.closest('a[data-goto]');
    if(!a)return;
    show(a.dataset.goto);
    var target=document.querySelector(a.getAttribute('href'));
    if(target){e.preventDefault();target.scrollIntoView({behavior:'smooth',block:'start'});
      history.replaceState(null,'',a.getAttribute('href'))}
  });
  // The finder. Everything on the page is in one index, so a ticket tag, an
  // item number or a word out of a title all land in the same place.
  var pal=document.getElementById('pal');
  var palIn=pal&&pal.querySelector('input');
  var palList=pal&&pal.querySelector('ul');
  var index=[];
  try{index=JSON.parse(document.getElementById('desk-index').textContent)}catch(e){}
  var hits=[],at=0;

  function jump(row){
    closePal();
    if(row.view)show(row.view);
    var el=document.getElementById(row.id);
    if(el){el.scrollIntoView({behavior:'smooth',block:'start'});
      history.replaceState(null,'','#'+row.id)}
  }
  function draw(){
    if(!hits.length){palList.innerHTML='<li class="p-none">Nothing matches</li>';return}
    palList.innerHTML=hits.map(function(r,i){
      return '<li role="option" data-i="'+i+'" aria-selected="'+(i===at)+'">'+
        '<span class="p-tag">'+r.tag+'</span>'+
        '<span class="p-t">'+r.label+'</span>'+
        '<span class="p-s">'+(r.sub||'')+'</span></li>';
    }).join('');
  }
  function filter(q){
    q=(q||'').trim().toLowerCase();
    hits=q?index.filter(function(r){return r.hay.indexOf(q)>-1}).slice(0,12)
          :index.slice(0,12);
    at=0;draw();
  }
  function openPal(){
    if(!pal)return;
    pal.hidden=false;palIn.value='';filter('');palIn.focus();
  }
  function closePal(){if(pal)pal.hidden=true}
  if(pal){
    palIn.addEventListener('input',function(){filter(palIn.value)});
    palIn.addEventListener('keydown',function(e){
      if(e.key==='ArrowDown'){at=Math.min(at+1,hits.length-1);draw();e.preventDefault()}
      else if(e.key==='ArrowUp'){at=Math.max(at-1,0);draw();e.preventDefault()}
      else if(e.key==='Enter'&&hits[at]){jump(hits[at]);e.preventDefault()}
      else if(e.key==='Escape')closePal();
    });
    palList.addEventListener('click',function(e){
      var li=e.target.closest('li[data-i]');
      if(li&&hits[li.dataset.i])jump(hits[li.dataset.i]);
    });
    pal.addEventListener('click',function(e){if(e.target===pal)closePal()});
    [].forEach.call(document.querySelectorAll('[data-find]'),function(b){
      b.addEventListener('click',openPal);
    });
  }

  // A fold he shut stays shut. Reopening the page every hour and closing the
  // same three sections again is how a page stops being used.
  [].forEach.call(document.querySelectorAll('details[data-remember]'),function(d){
    var key='fold-'+d.dataset.remember;
    try{
      var was=localStorage.getItem(key);
      if(was!==null)d.open=was==='1';
    }catch(e){}
    d.addEventListener('toggle',function(){
      try{localStorage.setItem(key,d.open?'1':'0')}catch(e){}
    });
  });

  // The rest of the card's folds are not worth remembering forever, but they must
  // survive the reload an answer triggers: a section he opened to ask a question
  // should still be open when the answer lands, not snap back to its default. So
  // remember them for this tab only (sessionStorage clears on close, so a fresh
  // session still opens at the intended defaults), keyed by the card and the fold's
  // position within it so every card keeps its own state.
  var FOLDS='details.sub:not([data-remember]),details.qa-earlier';
  [].forEach.call(document.querySelectorAll(FOLDS),function(d){
    var card=d.closest('[id]');
    if(!card)return;
    var key='open-'+card.id+'-'+[].indexOf.call(card.querySelectorAll(FOLDS),d);
    try{var was=sessionStorage.getItem(key);if(was!==null)d.open=was==='1';}catch(e){}
    d.addEventListener('toggle',function(){
      try{sessionStorage.setItem(key,d.open?'1':'0')}catch(e){}
    });
  });

  // Keep his place across that same reload, so the card he was reading does not
  // jump to the top when the answer lands. Skipped when the URL points at an
  // anchor, so a link to a specific ticket still wins.
  try{
    var sy=sessionStorage.getItem('desk-scroll');
    if(!location.hash&&sy!==null){var y=parseInt(sy,10);if(y)window.scrollTo(0,y);}
  }catch(e){}
  window.addEventListener('beforeunload',function(){
    try{sessionStorage.setItem('desk-scroll',String(window.scrollY||window.pageYOffset||0))}catch(e){}
  });

  // The ask box: the chat for one job. Opening it, the one-tap starters, and the
  // way out for when the page is a file on disk with no server behind it, which
  // is the same words with the job named, on the clipboard.
  function openAsk(box,seed){
    var panel=box.querySelector('.ask-box');
    var field=box.querySelector('textarea');
    panel.hidden=false;
    box.querySelector('.ask-bar').hidden=true;
    if(seed&&!field.value)field.value=seed;
    field.focus();
    field.selectionStart=field.selectionEnd=field.value.length;
    // Say which of the two this box is. A page with no server behind it can
    // only hand the words to a chat, and a copy button that looks like the
    // whole feature is worse than one that admits what it is.
    var send=box.querySelector('.ask-send');
    var keys=box.querySelector('.ask-keys');
    if(keys)keys.innerHTML=(send&&!send.hidden)
      ?'Enter sends \u00b7 Shift+Enter for a new line'
      :'No desk server behind this page, so Enter copies it for a chat instead';
    return field;
  }
  function closeAsk(box){
    box.querySelector('.ask-box').hidden=true;
    box.querySelector('.ask-bar').hidden=false;
    box.querySelector('.ask-hint').textContent='';
  }
  document.addEventListener('click',function(e){
    // Rewrite this draft, from the draft. The box that does it is at the foot of
    // the card, so the button up here opens it with the sentence started.
    var here=e.target.closest('.ask-here');
    if(here){
      // The nearest of the three, so a button in a draft header opens that
      // job's box and one in a Say this header opens the speaking card's.
      var within=here.closest('.act-body,.tk,.st-tk');
      var target=within&&within.querySelector('.ask');
      if(target){
        var f=openAsk(target,here.dataset.askSeed||'');
        target.scrollIntoView({behavior:'smooth',block:'center'});
        f.focus();
      }
      return;
    }
    var box=e.target.closest('.ask');
    if(!box)return;
    // Two composers can be open in one block: the box at the foot of the card,
    // and the one inside whichever answer he is pulling on. Every button works
    // on the one it is inside.
    var here=e.target.closest('.fu')||box.querySelector('.ask-box');
    var field=here.querySelector('textarea');
    var follow=e.target.closest('.qa-follow');
    if(follow){
      var fu=follow.closest('details').querySelector('.fu');
      fu.hidden=false;
      follow.closest('.qa-foot').hidden=true;
      var t=fu.querySelector('textarea');
      t.focus();
      return;
    }
    if(e.target.closest('.fu-cancel')){
      var mine=e.target.closest('.fu');
      mine.hidden=true;
      var foot=mine.parentNode.querySelector('.qa-foot');
      if(foot)foot.hidden=false;
      return;
    }
    if(e.target.closest('.ask-open')){
      openAsk(box,'');
    }else if(e.target.closest('.ask-cancel')){
      closeAsk(box);
    }else if(e.target.closest('.qa-chip')){
      var add=e.target.closest('.qa-chip').dataset.fill;
      field.value=field.value.trim()?field.value.trim()+' '+add:add;
      field.focus();
      field.selectionStart=field.selectionEnd=field.value.length;
    }else if(e.target.closest('.ask-copy')){
      var q=(field.value||'').trim();
      // Following up in a chat means handing over what it is a follow-up to,
      // otherwise "why?" arrives on its own and means nothing.
      var lead=box.dataset.askLead||'';
      var about=e.target.closest('.qa');
      if(about){
        var asked=about.querySelector('.qa-q');
        var got=about.querySelector('.qa-a');
        lead+='\n\nHe is following up on this exchange.\n\nQ: '
          +(asked?asked.textContent.trim():'')+'\n\nA: '
          +(got?got.textContent.trim():'');
      }
      putPlain(lead+(q?'\n\n'+q:''));
      var hint=here.querySelector('.ask-hint')||box.querySelector('.ask-hint');
      hint.textContent=q?'Copied. Paste it into a chat on this folder.'
        :'Copied the job. Paste it into a chat and type what you want.';
    }
  });
  // Enter sends, the way it does in every chat. Shift-Enter is a new line, and
  // escape puts the box away.
  document.addEventListener('keydown',function(e){
    var panel=e.target.closest&&(e.target.closest('.ask-box')||e.target.closest('.fu'));
    if(!panel||e.target!==panel.querySelector('textarea'))return;
    var box=panel.closest('.ask');
    if(e.key==='Escape'){
      if(panel.classList.contains('fu')){
        panel.hidden=true;
        var foot=panel.parentNode.querySelector('.qa-foot');
        if(foot)foot.hidden=false;
      }else{closeAsk(box)}
      return;
    }
    if(e.key!=='Enter'||e.shiftKey||e.altKey)return;
    e.preventDefault();
    var send=panel.querySelector('.ask-send');
    // No server behind the page, so the only thing Enter can honestly do is
    // hand the words over for a chat.
    (send&&!send.hidden?send:panel.querySelector('.ask-copy')).click();
  });

  var help=document.getElementById('help');
  function openHelp(){if(help&&!help.open)help.showModal()}
  if(help){
    [].forEach.call(document.querySelectorAll('[data-help]'),function(b){
      b.addEventListener('click',openHelp);
    });
    help.addEventListener('click',function(e){if(e.target===help)help.close()});
    var x=help.querySelector('.help-close');
    if(x)x.addEventListener('click',function(){help.close()});
  }

  // The chip for the ticket you are looking at lights up as you scroll.
  var chips=[].slice.call(document.querySelectorAll('.jump a[href^="#t-"]'));
  if(chips.length&&'IntersectionObserver' in window){
    var seen={};
    var eye=new IntersectionObserver(function(rows){
      rows.forEach(function(r){seen[r.target.id]=r.isIntersecting});
      var live=chips.filter(function(a){return seen[a.getAttribute('href').slice(1)]});
      chips.forEach(function(a){a.classList.remove('on')});
      if(live.length)live[0].classList.add('on');
    },{rootMargin:'-90px 0px -70% 0px'});
    chips.forEach(function(a){
      var el=document.getElementById(a.getAttribute('href').slice(1));
      if(el)eye.observe(el);
    });
  }

  document.addEventListener('keydown',function(e){
    if((e.metaKey||e.ctrlKey)&&e.key==='k'){openPal();e.preventDefault();return}
    if(e.metaKey||e.ctrlKey||e.altKey)return;
    var tag=(e.target.tagName||'').toLowerCase();
    if(tag==='input'||tag==='textarea')return;
    if(e.key==='1')show('desk');
    if(e.key==='2')show('standup');
    if(e.key==='s'&&t)t.click();
    if(e.key==='/'){openPal();e.preventDefault()}
    if(e.key==='?')openHelp();
    if(e.key==='Escape')closePal();
  });
  if(tabs.length){
    var start=document.body.dataset.view;
    try{
      var saved=sessionStorage.getItem('desk-view');
      if(saved)start=saved;
    }catch(e){}
    if(location.hash.indexOf('#s-')===0)start='standup';
    show(start,false);
  }
  // Scroll-spy: light the jump link for the section at the top of the view, so
  // the rail always says where you are down a long board. A top-line test rather
  // than a mid-band one, so a gap between sections never leaves nothing lit.
  (function(){
    var nav=document.querySelector('nav.jump');
    if(!nav)return;
    var links=[].slice.call(nav.querySelectorAll('a[href^="#"]'));
    var map={},targets=[];
    links.forEach(function(a){
      var id=decodeURIComponent(a.getAttribute('href').slice(1));
      var el=document.getElementById(id);
      if(el){map[id]=a;targets.push(el);}
    });
    if(!targets.length)return;
    var ticking=false;
    function paint(){
      ticking=false;
      // Last section whose top has scrolled above the line is the one in view;
      // later in document order wins, so a ticket lights over its container.
      var line=140,current=targets[0].id;
      for(var i=0;i<targets.length;i++){
        if(targets[i].getBoundingClientRect().top-line<=0)current=targets[i].id;
      }
      links.forEach(function(a){a.classList.toggle('on',map[current]===a);});
    }
    function onScroll(){if(!ticking){ticking=true;requestAnimationFrame(paint);}}
    window.addEventListener('scroll',onScroll,{passive:true});
    window.addEventListener('resize',onScroll,{passive:true});
    paint();
  })();
})();
