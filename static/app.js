'use strict';
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const defaultText = 'ยินดีต้อนรับเข้าสู่ thai voice lab สร้างเสียงได้ฟรี ไม่จำกัด บนคอมพิวเตอร์เราเอง';
let voices = [], selectedId = '', filter = 'all', previewId = '', busy = false;
let activeJob = '', pollTimer, elapsedTimer, toastTimer, currentPeaks = [];
const previewAudio = new Audio();
const palettes = [['#e8eefb','#627fb1'],['#edeafa','#8a7bb1'],['#f6ede5','#b1947b'],['#e4f0ee','#63968c'],['#f5e9f0','#ab7a95'],['#e4eff6','#7595ae'],['#f3efdf','#a19365'],['#e9f1e8','#7a9872'],['#eeeaf4','#9983af']];
function icon(id) { const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); const use = document.createElementNS(svg.namespaceURI,'use'); use.setAttribute('href','#i-'+id); svg.append(use); return svg; }
function element(tag, className, text) { const e=document.createElement(tag); if(className)e.className=className; if(text!==undefined)e.textContent=text; return e; }
function notify(message, error=false) { clearTimeout(toastTimer); const t=$('#toast'); t.textContent=message; t.classList.toggle('error',error); t.hidden=false; toastTimer=setTimeout(()=>t.hidden=true,error?8500:4500); }
async function api(path, options={}) { const response=await fetch(path, options); if(!response.ok){ let message; try{const data=await response.json();message=typeof data.detail==='string'?data.detail:'ตรวจสอบข้อความ ไฟล์เสียง หรือค่าที่เลือกอีกครั้ง';}catch{message='เชื่อมต่อเซิร์ฟเวอร์ไม่ได้'} const error=new Error(message);error.status=response.status;throw error; } return response.json(); }
function timeString(seconds) { const n=Math.max(0,Math.round(seconds)); return `${Math.floor(n/60)}:${String(n%60).padStart(2,'0')}`; }
function updateCount() { $('#char-count').textContent=`${$('#text').value.length.toLocaleString()} / 2,000 ตัวอักษร`; $('#generate').disabled=busy || !selectedId || !$('#text').value.trim(); }
function selectVoice(id) { selectedId=id; const v=voices.find(v=>v.id===id); if(!v)return; $('#selected-name').textContent=v.name; $('#selected-type').textContent=v.kind==='public'?'THAI · CC0':v.kind==='upload'?'YOUR VOICE':'LOCAL REFERENCE'; localStorage.setItem('thaiVoice.selected',id); renderVoices(); updateCount(); }
function renderVoices() {
  const list=$('#voice-list'); list.replaceChildren();
  const visible=voices.filter(v=>filter==='all'||(filter==='public'?v.kind==='public':v.kind!=='public'));
  $('#voice-count').textContent=`${voices.length} เสียง`;
  if(!visible.length)list.append(element('div','empty-library','ยังไม่มีเสียงในหมวดนี้ ลองอัปโหลดเสียงของคุณ'));
  for(const v of visible){
    const card=element('div','voice-card'+(v.id===selectedId?' selected':''));
    const select=element('button','voice-select');select.type='button';select.setAttribute('aria-label',`เลือกเสียง ${v.name}`);select.setAttribute('aria-pressed',String(v.id===selectedId));select.onclick=()=>selectVoice(v.id);
    const avatar=element('div','voice-avatar'); const color=palettes[voices.indexOf(v)%palettes.length];avatar.style.setProperty('--avatar-bg',color[0]);avatar.style.setProperty('--avatar-fg',color[1]);avatar.append(icon('wave'));
    const copy=element('div','voice-copy');copy.append(element('strong','',v.name),element('small','',`${v.kind==='public'?'Thai · CC0':v.kind==='upload'?'เสียงของคุณ':'เสียงในเครื่อง'}${v.duration?' · '+v.duration.toFixed(1)+' วิ':''}`));
    const play=element('button','preview-button');play.type='button';play.setAttribute('aria-label',(previewId===v.id?'หยุด':'ฟังตัวอย่าง')+' '+v.name);play.append(icon(previewId===v.id?'pause':'play'));play.onclick=()=>playPreview(v);
    card.append(select,avatar,copy,play); if(v.id===selectedId){const check=icon('check');check.classList.add('selected-check');card.append(check);} list.append(card);
  }
}
async function playPreview(v){
  if(previewId===v.id){previewAudio.pause();previewId='';renderVoices();return;}
  $('#result-audio').pause();$$('#history-list audio').forEach(a=>a.pause());
  previewAudio.pause(); previewId=v.id; previewAudio.src=v.audio_url;renderVoices();
  try{await previewAudio.play();}catch{previewId='';renderVoices();notify('เล่นตัวอย่างไม่ได้ กรุณาลองอีกครั้ง',true);}
}
previewAudio.onended=()=>{previewId='';renderVoices()};
$('#result-audio').onplay=()=>{previewAudio.pause();previewId='';renderVoices();$$('#history-list audio').forEach(a=>a.pause());};
async function loadVoices(){voices=await api('/api/voices'); const old=selectedId||localStorage.getItem('thaiVoice.selected');selectVoice(voices.some(v=>v.id===old)?old:(voices.find(v=>v.id==='mhee')||voices[0]||{}).id||'');renderSources();}
function renderSources(){const list=$('#source-list');list.replaceChildren();for(const v of voices.filter(v=>v.kind==='public')){const row=element('div','source-row');row.append(element('strong','',v.name+' · CC0 1.0'));row.append(element('p','',v.transcript||'')); const a=element('a','',v.source_clip||'Common Voice 17.0');a.href=v.source_url;a.target='_blank';a.rel='noreferrer';row.append(a); list.append(row);}}
async function uploadFile(file){
  if(!file)return;if(file.size>20*1024*1024){notify('ไฟล์ต้องมีขนาดไม่เกิน 20 MB',true);return;}
  $('#audio-file').disabled=true;$('#upload-title').textContent='กำลังเตรียมไฟล์เสียง…';
  try{const form=new FormData();form.append('file',file);const v=await api('/api/upload',{method:'POST',body:form}); await loadVoices();filter='custom';$$('[data-filter]').forEach(b=>b.classList.toggle('active',b.dataset.filter===filter));selectVoice(v.id);notify(`เพิ่ม ${v.name} แล้ว${v.original_duration>12?' · ใช้ 12 วินาทีแรกเป็นเสียงอ้างอิง':''}`);}catch(e){notify(e.message,true);}finally{$('#audio-file').disabled=false;$('#audio-file').value='';$('#upload-title').textContent='หรือใช้เสียงของคุณเอง';}
}
$('#audio-file').onchange=e=>uploadFile(e.target.files[0]);
['dragenter','dragover'].forEach(event=>$('#drop-zone').addEventListener(event,e=>{e.preventDefault();$('#drop-zone').classList.add('dragging')}));
['dragleave','drop'].forEach(event=>$('#drop-zone').addEventListener(event,e=>{e.preventDefault();$('#drop-zone').classList.remove('dragging')}));
$('#drop-zone').addEventListener('drop',e=>{if(!$('#audio-file').disabled)uploadFile(e.dataTransfer.files[0])});
function setBusy(value){busy=value;$('#generate span').textContent=value?'กำลังสร้างเสียง…':'สร้างเสียงพูด';$('#job-progress').hidden=!value;updateCount();}
function watchJob(id, createdAt){
  activeJob=id;localStorage.setItem('thaiVoice.job',id);setBusy(true);clearTimeout(pollTimer);clearInterval(elapsedTimer);
  const started=createdAt?Date.parse(createdAt):Date.now();const tick=()=>$('#job-time').textContent=timeString((Date.now()-started)/1000);tick();elapsedTimer=setInterval(tick,1000);
  async function poll(){
    try{const job=await api('/api/jobs/'+id);$('#job-message').textContent=job.message;$('#progress-bar').value=job.progress||0;
      if(job.status==='completed'||job.status==='failed'){clearInterval(elapsedTimer);setBusy(false);localStorage.removeItem('thaiVoice.job');activeJob=''; if(job.status==='completed'){showOutput(job);notify('สร้างเสียงเรียบร้อย พร้อมฟังและดาวน์โหลด');}else notify(job.message,true);refreshStatus();return;}
    }catch(e){if(e.status===404){clearInterval(elapsedTimer);setBusy(false);localStorage.removeItem('thaiVoice.job');activeJob='';notify('ไม่พบงานนี้แล้ว กรุณาสร้างเสียงใหม่',true);return;}$('#job-message').textContent='ขาดการเชื่อมต่อ กำลังลองใหม่…';}
    pollTimer=setTimeout(poll,1400);
  }poll();
}
async function generate(){
  if(busy)return;if(!$('#text').value.trim()){notify('ใส่ข้อความก่อนสร้างเสียง',true);$('#text').focus();return;}if(!selectedId){notify('เลือกเสียงอ้างอิงก่อน',true);return;}
  previewAudio.pause();previewId='';renderVoices();setBusy(true);
  try{const job=await api('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:$('#text').value,voice_id:selectedId,speed:Number($('#speed').value),steps:Number($('#quality').value)})});watchJob(job.id,job.created_at);}catch(e){setBusy(false);notify(e.message,true);}
}
function showOutput(job){
  $('#output-title').textContent='เสียงของคุณ พร้อมแล้ว';$('#output-meta').textContent=`${job.voice_name} · ${timeString(job.duration)} · ${job.sample_rate/1000} kHz · สร้างใน ${timeString(job.elapsed)}`;
  $('#output-empty').hidden=true;$('#output-content').hidden=false;$('#result-audio').src=job.audio_url;
  $('#download').href=job.audio_url;$('#download').download=`thai-voice-${job.id.slice(0,8)}.wav`;currentPeaks=job.peaks||[];drawWave();
}
function drawWave(){const canvas=$('#waveform');if(!currentPeaks.length||!canvas.clientWidth)return; const ratio=window.devicePixelRatio||1; const w=canvas.clientWidth,h=52;canvas.width=w*ratio;canvas.height=h*ratio;const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);const max=Math.max(...currentPeaks,.01),step=w/currentPeaks.length;ctx.fillStyle='#729ce5';currentPeaks.forEach((p,i)=>{const height=Math.max(2,p/max*(h-6));ctx.fillRect(i*step,(h-height)/2,Math.max(1,step-1.5),height)});}
window.addEventListener('resize',drawWave);
for(let i=0;i<75;i++){const bar=element('i');bar.style.height=(5+Math.abs(Math.sin(i*.57)*Math.sin(i*.13))*38)+'px';$('#output-empty').append(bar);}
async function loadHistory(){
  const list=$('#history-list');
  try{const jobs=await api('/api/history');list.replaceChildren();if(!jobs.length){list.append(element('p','history-empty','ยังไม่มีเสียงที่สร้าง ลองสร้างเสียงแรกของคุณในสตูดิโอ'));return;}
    for(const job of jobs){const row=element('div','history-row'),copy=element('div');copy.append(element('strong','',job.text));copy.append(element('p','',`${job.voice_name} · ${new Date(job.created_at).toLocaleString('th-TH')} · ${job.status==='completed'?timeString(job.duration):job.message}`));row.append(copy);
      if(job.status==='completed'){const audio=element('audio');audio.controls=true;audio.preload='none';audio.src=job.audio_url;audio.onplay=()=>{previewAudio.pause();previewId='';renderVoices();$('#result-audio').pause();$$('#history-list audio').filter(a=>a!==audio).forEach(a=>a.pause())};const a=element('a','download-button','WAV');a.prepend(icon('download'));a.href=job.audio_url;a.download=`thai-voice-${job.id.slice(0,8)}.wav`;row.append(audio,a);}list.append(row);
    }
  }catch(e){list.replaceChildren(element('p','history-empty',e.message));}
}
function setView(view){
  const current=['studio','history','skill'].includes(view)?view:'studio';
  for(const name of ['studio','history','skill'])$('#'+name+'-view').hidden=name!==current;
  $('.page-heading').hidden=current==='skill';
  $$('[data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===current);b.setAttribute('aria-current',b.dataset.view===current?'page':'false')});
  if(current==='history')loadHistory();else if(current==='skill')loadSkillGuide();else requestAnimationFrame(drawWave);
}
$$('[data-view]').forEach(b=>b.onclick=()=>{location.hash=b.dataset.view;setView(b.dataset.view)});
window.addEventListener('hashchange',()=>setView(location.hash.slice(1)||'studio'));
$$('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;$$('[data-filter]').forEach(t=>t.classList.toggle('active',t===b));renderVoices()});
$$('.about-button').forEach(b=>b.onclick=()=>$('#about-dialog').showModal());$('#close-about').onclick=()=>$('#about-dialog').close();$('#about-dialog').onclick=e=>{if(e.target===$('#about-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close()}};
$('#refresh-history').onclick=loadHistory;$('#generate').onclick=generate;$('#sample-text').onclick=()=>{$('#text').value=defaultText;updateCount();localStorage.setItem('thaiVoice.text',defaultText)};
$('#text').oninput=()=>{updateCount();localStorage.setItem('thaiVoice.text',$('#text').value)};
$('#speed').oninput=()=>$('#speed-value').textContent=Number($('#speed').value).toFixed(2)+'×';
document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key==='Enter'&&!$('#about-dialog').open){e.preventDefault();generate()}});
async function refreshStatus(){try{const status=await api('/api/status');$('#connection span:last-child').textContent=status.state==='loading'?'กำลังโหลดโมเดล':'รันบนเครื่องคุณ';$('#connection .status-dot').style.background='';}catch{$('#connection span:last-child').textContent='ไม่ได้เชื่อมต่อ';$('#connection .status-dot').style.background='#edb898';}}
async function init(){
  $('#text').value=localStorage.getItem('thaiVoice.text')??defaultText;updateCount();setView(location.hash.slice(1)||'studio');
  try{await loadVoices();await refreshStatus();const history=await api('/api/history');const latest=history.find(j=>j.status==='completed');if(latest)showOutput(latest);
    const pending=history.find(j=>!['completed','failed'].includes(j.status));if(pending)watchJob(pending.id,pending.created_at);else localStorage.removeItem('thaiVoice.job');
  }catch(e){notify('เปิดคลังเสียงไม่ได้ ตรวจสอบว่าเซิร์ฟเวอร์กำลังทำงานอยู่',true);$('#voice-list').replaceChildren(element('p','empty-library','ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ ลองโหลดหน้าใหม่'));}
}
let skillGuide=null, selectedAgent='codex', guideLoading=false;
async function loadSkillGuide(){
  if(skillGuide){renderSkillGuide();return;}if(guideLoading)return;guideLoading=true;
  try{skillGuide=await api('/api/skill');renderSkillGuide();}catch(e){$('#install-prompt').value='โหลดคู่มือไม่ได้ กรุณาลองเปิดแท็บนี้อีกครั้ง';notify(e.message,true);}finally{guideLoading=false;}
}
function renderSkillGuide(){
  $('#install-prompt').value=skillGuide.install_prompts[selectedAgent];$('#copy-install').disabled=false;
  for(const name of ['codex','claude','reference'])$('#example-'+name).textContent=skillGuide.examples[name];
  $('#skill-download').href=skillGuide.download_url;
}
async function copyText(text,button){
  if(!text)return;
  try{await navigator.clipboard.writeText(text);const original=button.textContent;button.textContent='คัดลอกแล้ว';setTimeout(()=>button.textContent=original,1800);notify('คัดลอกแล้ว นำไปวางใน AI ได้เลย');}
  catch{const box=$('#install-prompt');box.value=text;box.focus();box.select();notify('เลือกข้อความให้แล้ว กดคัดลอกด้วย ⌘C หรือ Ctrl+C');}
}
$$('[data-agent]').forEach(button=>button.onclick=()=>{selectedAgent=button.dataset.agent;$$('[data-agent]').forEach(b=>b.classList.toggle('active',b===button));if(skillGuide)renderSkillGuide();});
$('#copy-install').onclick=()=>copyText(skillGuide?.install_prompts[selectedAgent],$('#copy-install'));
$$('.copy-example').forEach(button=>button.onclick=()=>copyText(skillGuide?.examples[button.dataset.example],button));
init();setInterval(refreshStatus,15000);
