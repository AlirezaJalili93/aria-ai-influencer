/* UTF-8 · Persian RTL · original Gemini layout with persistent server actions. */
'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let serverState=null, studioState=null, currentPack=null, simulationTokens=0, sending=false, mediaSignature=null;
function showToast(text){$('toastMessage').textContent=text;$('toastContainer').classList.remove('hidden');clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>$('toastContainer').classList.add('hidden'),6000);}
$('toastContainer').setAttribute('role','status');
$('closeToastBtn').onclick=()=>$('toastContainer').classList.add('hidden');
function copyTextSafe(text,label){navigator.clipboard.writeText(text).then(()=>showToast(label+' کپی شد.')).catch(()=>showToast('کپی خودکار انجام نشد؛ متن را انتخاب و کپی کنید.'));}
async function api(path,data){const response=await fetch(path,{method:data===undefined?'GET':'POST',headers:data===undefined?{}:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});const result=await response.json();if(!response.ok||result.ok===false)throw Error(result.error||'خطا در درخواست');return result;}
async function action(button,work){button.disabled=true;try{await work();}catch(e){showToast(e.message);}finally{button.disabled=false;}}
function openTab(id){document.querySelectorAll('.nav-tab').forEach(b=>{b.classList.toggle('tab-active',b.dataset.tab===id);b.setAttribute('aria-selected',String(b.dataset.tab===id));});document.querySelectorAll('.tab-panel').forEach(p=>p.classList.toggle('hidden',p.id!==id));if(id==='tab-keys-tokens')drawTokenChart();}
document.querySelectorAll('.nav-tab').forEach(b=>{b.setAttribute('role','tab');b.onclick=()=>openTab(b.dataset.tab);});
const defaults={gemini:['https://generativelanguage.googleapis.com/v1beta','gemini-2.5-pro','gemini-2.5-flash'],openai:['https://api.openai.com/v1','gpt-4o','gpt-4o-mini'],anthropic:['https://api.anthropic.com/v1','claude-3-7-sonnet-latest','claude-3-5-haiku-latest'],deepseek:['https://api.deepseek.com/v1','deepseek-chat','deepseek-chat'],openrouter:['https://openrouter.ai/api/v1','google/gemini-2.5-flash','openai/gpt-4o-mini'],custom:['https://api.avalai.ir/v1','gpt-4o','gpt-4o-mini']};
$('vaultProviderInput').onchange=()=>{const d=defaults[$('vaultProviderInput').value];['vaultBaseUrlInput','vaultScenarioModelInput','vaultFastModelInput'].forEach((id,i)=>$(id).value=d[i]);};
$('addVaultKeyBtn').onclick=()=>action($('addVaultKeyBtn'),async()=>{await api('/api/add-key',{provider:$('vaultProviderInput').value,alias:$('vaultAliasInput').value.trim(),api_key:$('vaultKeyInput').value.trim(),base_url:$('vaultBaseUrlInput').value.trim(),scenario_model:$('vaultScenarioModelInput').value.trim(),fast_model:$('vaultFastModelInput').value.trim(),daily_limit:Number($('vaultLimitInput').value),priority:Number($('vaultPriorityInput').value)});$('vaultKeyInput').value='';await refresh();showToast('کلید در سرور ذخیره شد؛ اعتبار آن با درخواست واقعی بررسی می‌شود.');});
$('saveQuickKeyBtn').onclick=()=>action($('saveQuickKeyBtn'),async()=>{const key=$('quickApiKeyInput').value.trim();if(!key)throw Error('کلید را وارد کنید.');let provider=$('liveProviderSelect').value;if(['auto','simulator'].includes(provider))provider=key.startsWith('AIza')?'gemini':'openai';if(provider==='custom'){openTab('tab-keys-tokens');throw Error('برای درگاه اختصاصی، کلید و نشانی Base URL را در تب کلیدها ثبت کنید.');}await api('/api/add-key',{provider,alias:provider+'_quick',api_key:key,daily_limit:500000,priority:10});$('quickApiKeyInput').value='';$('liveProviderSelect').value=provider;await refresh();showToast('کلید ثبت شد. برای بررسی اعتبار، یک پیام آزمایشی بفرستید.');});
function drawTokenChart(){const canvas=$('tokenUsageChart'),ctx=canvas.getContext('2d');const keys=serverState?.token_report?.configured_keys||[];const width=Math.max(320,canvas.clientWidth||600);canvas.width=width*2;canvas.height=460;ctx.scale(2,2);ctx.clearRect(0,0,width,230);ctx.font='12px Vazirmatn';ctx.textAlign='right';ctx.direction='rtl';ctx.fillStyle='#94a3b8';if(!keys.length){ctx.fillText('هنوز مصرف واقعی ثبت نشده است.',width-20,100);return;}const max=Math.max(1,...keys.map(k=>k.used_tokens_today));keys.forEach((k,i)=>{const row=28+i*(180/keys.length);ctx.fillStyle='#67e8f9';ctx.fillRect(20,row,Math.max(1,(width-220)*k.used_tokens_today/max),14);ctx.fillStyle='#e2e8f0';ctx.fillText(k.key_alias+' · '+k.used_tokens_today,width-10,row+12);});}
function renderKeys(){const keys=serverState.token_report.configured_keys;$('headerTotalTokens').textContent=keys.reduce((n,k)=>n+k.used_tokens_today,0).toLocaleString('fa-IR');$('vaultKeysTableBody').innerHTML=keys.length?keys.map(k=>`<tr><td class="py-3"><b>${esc(k.key_alias)}</b><div>اولویت: ${esc(k.priority)}</div><small>${esc(k.masked_key)}</small></td><td class="py-3">${esc(k.provider)}<div class="ltr-code">${esc(k.scenario_model)} / ${esc(k.fast_model)}</div></td><td class="py-3">${k.used_tokens_today.toLocaleString('fa-IR')} / ${k.daily_token_limit.toLocaleString('fa-IR')}<div>باقی‌مانده: ${k.remaining_tokens_today.toLocaleString('fa-IR')}</div></td><td>${k.is_active?'فعال':'متوقف'}</td><td><button class="toggle-key-btn" data-alias="${esc(k.key_alias)}" data-active="${!k.is_active}">${k.is_active?'توقف':'فعال‌سازی'}</button></td></tr>`).join(''):'<tr><td colspan="5">هنوز کلیدی در سرور ثبت نشده است.</td></tr>';$('vaultKeysTableBody').querySelectorAll('button').forEach(b=>b.onclick=()=>action(b,async()=>{await api('/api/toggle-key',{alias:b.dataset.alias,active:b.dataset.active==='true'});await refresh();}));drawTokenChart();}
$('simulateTrafficBtn').onclick=()=>{simulationTokens+=50*240+850;showToast('برآورد نمایشی ۵۰ دایرکت و ۱ سناریو: ۱۲٬۸۵۰ توکن؛ در مصرف واقعی ثبت نشده. مجموع شبیه‌ساز: '+simulationTokens.toLocaleString('fa-IR'));};
function bubble(text,role,meta=''){const el=document.createElement('div');el.className='aria-chat'+(role==='user'?' user':'');const p=document.createElement('p');p.textContent=text;el.append(p);if(meta){const small=document.createElement('small');small.textContent=meta;el.append(small);}$('chatMessagesContainer').append(el);$('chatMessagesContainer').scrollTop=$('chatMessagesContainer').scrollHeight;}
async function sendMessage(customText,customKind){if(sending)return;const text=(customText??$('userChatInput').value).trim();if(!text)return;const kind=customKind||$('interactionKindSelect').value;$('interactionKindSelect').value=kind;$('userChatInput').value='';bubble(text,'user',kind==='DM'?'دایرکت آزمایشی':'کامنت آزمایشی');sending=true;await action($('sendChatBtn'),async()=>{try{const provider=$('liveProviderSelect').value;if(provider==='simulator'){const used=Math.ceil(text.length/3)+95;simulationTokens+=used;bubble(generateSmartPersianFallbackReply(text,kind),'agent','شبیه‌ساز محلی · مصرف API: صفر · برآورد: '+used);}else{const result=await api('/api/test-reply',{text,kind,provider});bubble(result.reply,'agent',result.meta.provider+' / '+result.meta.model+' · '+result.meta.total_tokens+' توکن واقعی');await refresh();}}catch(e){bubble('درخواست واقعی انجام نشد: '+e.message,'agent','خطا؛ پاسخ شبیه‌ساز جایگزین نشده است.');}finally{sending=false;}});}
$('sendChatBtn').onclick=()=>sendMessage();$('userChatInput').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();sendMessage();}};
document.querySelectorAll('.sample-msg-btn').forEach(b=>b.onclick=()=>sendMessage(b.dataset.sampleMsg,b.dataset.sampleKind));
$('clearChatBtn').onclick=()=>$('chatMessagesContainer').replaceChildren();
$('copyBioBtn').onclick=()=>copyTextSafe(studioState?.character.official_bio||$('officialBioText').innerText,'بیو');
$('liveProviderSelect').onchange=()=>{$('activeModeBadge').textContent=$('liveProviderSelect').value==='simulator'?'شبیه‌ساز محلی':$('liveProviderSelect').value==='auto'?'چرخش هوشمند (Auto-Failover)':$('liveProviderSelect').value;};
const referenceStories=[{slot:'10:00',title:'استوری صبحگاهی: باتری شما چند درصده؟',overlay_text_fa:'سلام زمینی‌ها! باتری شما امروز چند درصده؟ مال من که روی ۱۰۰٪ قفله ⚡',interactive_sticker:'نظرسنجی: سرحالم 🚀 / هنوز خوابم 😴'},{slot:'16:00',title:'استوری ترفند هوش مصنوعی (فراخوان بیو)',overlay_text_fa:'طبق قولی که توی بیو دادم: چه کاری داری که وقتت رو می‌گیره؟ 👇',interactive_sticker:'باکس سوال: کدوم کار روزمره‌ت رو هوشمند کنم؟'},{slot:'21:00',title:'استوری معرفی ریلز اول',overlay_text_fa:'اولین ویدیوی رسمیم آپلود شد! برید زیر پست یه سوال عجیب بپرسید تا زیر ۱۰ ثانیه جواب بدم 🎬',interactive_sticker:'لینک به ریلز اول + اسلایدر 🔥'}];
function renderStories(stories=referenceStories){$('scheduledStoriesList').innerHTML='<p class="text-xs text-amber-300">قالب‌های محتوایی پیشنهادی · این کارت‌ها صف انتشار نیستند.</p>'+stories.map(s=>`<div class="aria-chip"><b>${esc(s.slot)} · ${esc(s.title||s.story_type||'استوری')}</b><p>${esc(s.overlay_text_fa)}</p><small>${esc(s.interactive_sticker)}</small></div>`).join('');}
function packText(pack){const reel=pack.reel_scenario||{};return ['موضوع: '+(pack.topic||''),'قلاب ۳ ثانیه: '+(reel.hook_0_to_3_sec||''),...(reel.body_scenes||[]).map(s=>'صحنه '+s.scene+': '+(s.visual_and_motion||'')+'\n'+(s.dialogue_fa||'')),'فراخوان: '+(reel.call_to_action||''),'پرامپت ویدیو: '+(reel.ai_video_prompt_en||''),'کپشن:\n'+(pack.caption?.text_fa||''),(pack.caption?.hashtags||[]).join(' '),...(pack.scheduled_stories||[]).map(s=>s.slot+'\n'+s.overlay_text_fa+'\n'+s.interactive_sticker+'\n'+s.visual_prompt_en)].join('\n\n');}
function showPack(pack,label='پکیج ذخیره‌شده در سرور'){currentPack=pack;$('scenarioTitleLabel').textContent=label;const pre=document.createElement('div');pre.className='aria-content';pre.textContent=packText(pack);$('scenarioBodyContent').replaceChildren(pre);$('storyHeadlineInput').value=(pack.topic||'').slice(0,100);$('scheduleCaption').value=pack.caption?.text_fa||'';renderStories(pack.scheduled_stories?.length?pack.scheduled_stories:referenceStories);}
$('generateScenarioBtn').onclick=()=>action($('generateScenarioBtn'),async()=>{const topic=$('scenarioTopicInput').value.trim();if(!topic)throw Error('موضوع را بنویسید.');if($('liveProviderSelect').value==='simulator'){showPack({topic,reel_scenario:{hook_0_to_3_sec:'صبر کن اسکرول نکنی! '+topic,body_scenes:[{scene:1,visual_and_motion:'هولوگرام‌های شناور در استودیوی شیشه‌ای تهران',dialogue_fa:'بیاید این موضوع رو از نگاه پردازنده‌های من ببینیم!'}],call_to_action:'توی دایرکت بگو چه کاری رو برات هوشمند کنم؟'},caption:{text_fa:'سلام رفقای زمینی! امروز رفتیم سراغ «'+topic+'»؛ کدوم کار روزمره‌ت رو می‌خوای هوشمند کنی؟',hashtags:['#هوش_مصنوعی','#اینفلوئنسر_مجازی']},scheduled_stories:referenceStories},'نمونه شبیه‌ساز · بدون مصرف API');return;}const result=await api('/api/generate-daily',{topic,provider:$('liveProviderSelect').value});showPack(result.pack);await refresh();showToast('سناریو، کپشن و استوری‌ها در سرور ذخیره شدند.');});
document.querySelectorAll('.topic-pill').forEach(b=>b.onclick=()=>{$('scenarioTopicInput').value=b.dataset.topic;showToast('موضوع انتخاب شد؛ برای تولید روی دکمه تولید کلیک کنید.');});
$('copyCaptionBtn').onclick=()=>{if(!currentPack)return showToast('ابتدا پکیج را تولید یا از تاریخچه باز کنید.');copyTextSafe((currentPack.caption?.text_fa||'')+'\n'+(currentPack.caption?.hashtags||[]).join(' '),'کپشن');};
function editorValues(){return {headline:$('storyHeadlineInput').value,subheadline:$('storySubInput').value,badge:$('storyBadgeInput').value,background_image:$('sourceStoryPortraitImg').getAttribute('src'),caption:$('scheduleCaption').value};}
$('downloadStoryPngBtn').onclick=async()=>{await document.fonts.ready;const a=document.createElement('a');a.href=$('motionStoryCanvas').toDataURL('image/png');a.download='aria_story_rtl_vazirmatn.png';a.click();};
$('sendToScheduleQueueBtn').onclick=()=>action($('sendToScheduleQueueBtn'),async()=>{await document.fonts.ready;await api('/api/save-draft',{...editorValues(),image:$('motionStoryCanvas').toDataURL('image/png')});await refresh();showToast('پیش‌نویس و تصویر ۱۰۸۰×۱۹۲۰ ذخیره شدند. برای انتشار، نشانی عمومی رسانه و زمان را ثبت کنید.');});
$('addNewStoryScheduleBtn').onclick=()=>{$('scheduleForm').scrollIntoView({behavior:'smooth'});$('scheduleUrl').focus();};
$('scheduleForm').onsubmit=e=>{e.preventDefault();action(e.submitter,async()=>{await api('/api/schedule-media',{kind:$('scheduleKind').value,media_url:$('scheduleUrl').value,publish_at:$('publishAt').value,timezone:'Asia/Tehran',caption:$('scheduleCaption').value});await refresh();showToast('رسانه در صف واقعی انتشار ثبت شد.');});};
$('automationForm').onsubmit=e=>{e.preventDefault();action(e.submitter,async()=>{await api('/api/studio-settings',{enabled:$('dailyEnabled').value==='true',time:$('dailyTime').value,topic:$('dailyTopic').value,generate_image:$('dailyImage').value==='true'});await refresh();showToast('برنامه روزانه در سرور ذخیره شد.');});};
$('testIgGraphBtn').onclick=()=>action($('testIgGraphBtn'),async()=>{const box=$('igConnectionResultBox');box.classList.remove('hidden');try{const result=await api('/api/connect-instagram',{ig_user_id:$('igUserIdInput').value.trim(),access_token:$('igAccessTokenInput').value.trim()});box.textContent='اتصال تأیید شد: @'+(result.profile.username||result.profile.id);$('igAccessTokenInput').value='';await refresh();}catch(e){box.textContent='اتصال تأیید نشد: '+e.message;}});
$('copyCliCommandBtn').onclick=()=>copyTextSafe($('generatedCliBlock').innerText,'دستور اجرا');
function addMediaLink(url,label){const a=document.createElement('a');a.href=url;a.textContent=label;a.className='aria-link';a.download='';$('mediaResults').append(a,document.createElement('br'));}
$('generateImageBtn').onclick=()=>action($('generateImageBtn'),async()=>{const r=await api('/api/generate-image',{prompt:$('imagePrompt').value});addMediaLink(r.media_url,'دانلود تصویر AI جدید');await refresh();});
function addVoiceMedia(result){const box=document.createElement('div');box.className='aria-chip';const label=document.createElement('p');label.textContent='صدای ساخته‌شده با هوش مصنوعی'+(result.voice?' · '+result.voice:'');const audio=document.createElement('audio');audio.controls=true;audio.preload='none';audio.src=result.media_url;audio.className='aria-audio';audio.setAttribute('aria-label','پخش صدای کاراکتر آریا');const link=document.createElement('a');link.href=result.media_url;link.download='';link.className='aria-link';link.textContent='دانلود صدای MP3';box.append(label,audio,link);$('mediaResults').append(box);}
$('generateVoiceBtn').onclick=()=>action($('generateVoiceBtn'),async()=>{await api('/api/generate-voice',{text:$('voiceText').value,voice:$('voicePreset').value,speed:Number($('voiceSpeed').value),instructions:$('voiceInstructions').value});await refresh();showToast('صدای آریا ساخته شد و تنظیمات آن ذخیره شد.');});
$('renderMotionBtn').onclick=()=>action($('renderMotionBtn'),async()=>{const r=await api('/api/render-motion',editorValues());showToast('رندر آغاز شد. نتیجه در همین بخش نمایش داده می‌شود.');await refresh();});
function tehranInput(date){const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tehran',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(date),p=Object.fromEntries(parts.map(x=>[x.type,x.value]));return p.year+'-'+p.month+'-'+p.day+'T'+p.hour+':'+p.minute;}
function renderServerState(){const s=serverState;$('backendStatus').textContent='بک‌اند آنلاین';$('liveFollowerCount').textContent=s.instagram_connected?s.instagram_account.followers_count.toLocaleString('fa-IR'):'—';$('liveReplyStatus').textContent=s.instagram_connected?'آماده':'نیازمند اتصال';$('liveUsername').textContent=s.instagram_account.ig_username?'@'+s.instagram_account.ig_username:'@aria.ai.iran · نام پیشنهادی';$('statusNotice').textContent='بک‌اند آنلاین · اینستاگرام: '+(s.instagram_connected?'اطلاعات اتصال موجود است':'متصل نیست')+' · '+s.token_report.configured_keys.filter(k=>k.is_active).length+' کلید فعال · زمان تهران · نمونه‌ها و شبیه‌ساز از صف واقعی جدا هستند.';$('webhookState').textContent=s.webhook_signature_configured?'App Secret تنظیم شده؛ دریافت واقعی وب‌هوک هنوز باید با متا تست شود.':'App Secret تنظیم نشده است.';$('verifyToken').value=s.webhook_verify_token||'';renderKeys();$('realQueue').innerHTML=(s.scheduled_media.length?s.scheduled_media.map(item=>`<div class="aria-chip"><b>${esc(item.kind)} · ${esc(item.publish_at)} · ${esc(item.status)}</b><p class="aria-content">${esc(item.caption)}</p><div class="ltr-code">${esc(item.media_url)}</div>${item.error_message?'<p>'+esc(item.error_message)+'</p>':''}${item.status==='PENDING'?`<button data-cancel="${item.id}">لغو زمان‌بندی</button>`:''}</div>`).join(''):'<p>صف واقعی انتشار خالی است.</p>');$('realQueue').querySelectorAll('[data-cancel]').forEach(b=>b.onclick=()=>action(b,async()=>{await api('/api/cancel-schedule',{schedule_id:Number(b.dataset.cancel)});await refresh();}));$('recentReplies').innerHTML=s.recent_replies.map(r=>`<div class="aria-chip"><b>${esc(r.kind)} · ${esc(r.user_handle)}</b><p>${esc(r.incoming_text)}</p><p>${esc(r.reply_text)}</p></div>`).join('')||'<p>هنوز پاسخ واقعی ثبت نشده است.</p>';}
function renderStudioState(first){const s=studioState;if(first){$('dailyEnabled').value=String(s.settings.enabled);$('dailyTime').value=s.settings.time;$('dailyTopic').value=s.settings.topic;$('dailyImage').value=String(s.settings.generate_image);$('voicePreset').replaceChildren(...s.media_capabilities.voice_options.map(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;return o;}));$('voicePreset').value=s.settings.voice;$('voiceSpeed').value=s.settings.voice_speed;$('voiceInstructions').value=s.settings.voice_instructions;if(s.packs.length)showPack(s.packs[0].pack);}$('voiceStatus').textContent=s.media_capabilities.voice_configured?'OpenAI آمادهٔ درخواست است · '+s.media_capabilities.voice_model+' · نتیجهٔ واقعی پس از تولید مشخص می‌شود.':'کلید فعال OpenAI برای صدا موجود نیست؛ آن را در تب مدیریت کلیدها ثبت یا فعال کنید.';$('draftsList').innerHTML='<h3>پیش‌نویس‌های سرور</h3>'+s.drafts.map(d=>`<div class="aria-chip"><b>${esc(d.headline)}</b><p>${esc(d.subheadline)}</p>${d.media_url?`<a class="aria-link" download href="${esc(d.media_url)}">دانلود PNG</a>`:''} · پیش‌نویس؛ منتشر نشده</div>`).join('');$('packHistory').innerHTML='<h3>تاریخچه پکیج‌های روزانه</h3>'+s.packs.map((p,i)=>`<button data-pack="${i}">${esc(p.created_at.slice(0,16))} · ${esc(p.topic)}</button>`).join(' ');$('packHistory').querySelectorAll('button').forEach(b=>b.onclick=()=>showPack(s.packs[Number(b.dataset.pack)].pack));$('dailyJobs').innerHTML=s.jobs.filter(j=>j.id.startsWith('daily:')).map(j=>`<div class="aria-chip">${esc(j.id)} · ${esc(j.status)}<p>${esc(j.result.error||j.result.image_error||'')}</p></div>`).join('');const mediaJobs=s.jobs.filter(j=>!j.id.startsWith('daily:')), signature=JSON.stringify(mediaJobs);if(signature===mediaSignature)return;mediaSignature=signature;$('mediaResults').replaceChildren();for(const j of mediaJobs){if(j.result.media_url){if(j.result.media_type==='voice'){addVoiceMedia(j.result);}else{addMediaLink(j.result.media_url,j.result.media_type==='image'?'دانلود تصویر AI':'دانلود MP4 موشن');}if(j.result.media_type==='image'){const b=document.createElement('button');b.textContent='استفاده در استوری';b.onclick=()=>{$('sourceStoryPortraitImg').src=j.result.media_url;showToast('تصویر برای پیش‌نمایش و رندر انتخاب شد.');};$('mediaResults').append(b);}}else{const p=document.createElement('p');p.textContent='رندر '+j.id.slice(0,6)+' · '+j.status+' '+(j.result.error||'');$('mediaResults').append(p);}}}
let loading=false,firstLoad=true;
async function refresh(){if(loading)return;loading=true;try{[serverState,studioState]=await Promise.all([api('/api/status'),api('/api/studio')]);renderServerState();renderStudioState(firstLoad);firstLoad=false;}catch(e){$('backendStatus').textContent='ارتباط قطع است';$('statusNotice').textContent='دریافت وضعیت سرور انجام نشد: '+e.message;}finally{loading=false;}}
$('publishAt').value=tehranInput(new Date(Date.now()+3600000));$('vaultProviderInput').onchange();$('vaultKeysTableBody').replaceChildren();$('scenarioBodyContent').textContent='پکیج واقعی را تولید کنید یا حالت شبیه‌ساز را در تب تست انتخاب کنید.';renderStories();openTab('tab-live-test');refresh();setInterval(()=>{if(!document.hidden)refresh();},10000);window.addEventListener('resize',drawTokenChart);
    function generateSmartPersianFallbackReply(incomingText, kind) {
      const t = incomingText.trim();
      if (t.includes('آنلاین‌شاپ') || t.includes('فروش') || t.includes('قیمت') || t.includes('دایرکت')) {
        return 'رفیق آنلاین‌شاپی، وقتت طلاست! ⚡ می‌تونی یه ایجنت هوشمند مستقیم به دایرکتت وصل کنی که ۲۴ ساعته موجودی و سایز و قیمت رو بگه و لینک پرداخت بده؛ می‌خوای بهت بگم چطوری بدون کدنویسی راه‌اندازیش کنی؟ 😎🤖';
      }
      if (t.includes('ادمین') || t.includes('واقعا خودت') || t.includes('فیلم بازی')) {
        return 'ادمین کجا بود رفیق؟ 😂 من خودم ۲۴ ساعته بیدارم، نه مرخصی می‌خوام نه چایی نبات! فقط گاهی فنِ سرورم از دست کامنت‌های باحالتون داغ می‌کنه ⚡🤖';
      }
      if (t.includes('دانشجو') || t.includes('مقاله') || t.includes('جزوه') || t.includes('درس') || t.includes('PDF')) {
        return 'آخ آخ، مقاله و جزوه خوراک پردازنده‌های منه! 📚 فایل‌های PDF رو بنداز توی NotebookLM یا بده به من تا تو ۳۰ ثانیه برات خلاصه نکته‌به‌نکته و حتی پادکست صوتی بسازم. رشته‌ت چیه؟ 😎✨';
      }
      if (t.includes('برق') || t.includes('خاموش')) {
        return 'نه دیگه، سرورهای من روی کلودِ ابری با باتری خورشیدی سال ۲۰۵۰ کار می‌کنه! ⚡ حتی اگه کل شهر هم تاریک بشه من باز بیدارم و دارم استوری فردا رو رندر می‌گیرم 😎🌌';
      }
      if (kind === 'COMMENT') {
        return `دمت گرم بابت کامنتت رفیق! ⚡ پردازنده‌هام با پیام «${t.slice(0, 35)}» کلی انرژی گرفت؛ به نظرت پست فردا رو درباره کدوم ابزار هوش مصنوعی بسازم؟ 🤖✨`;
      }
      return `پیامت مستقیم رسید به هسته پردازش من! ⚡ درباره «${t.slice(0, 40)}» می‌تونم کمکت کنم تا با ابزارهای هوش مصنوعی ۱۰ برابر سریع‌تر انجامش بدی؛ دقیق‌تر می‌گی کدوم بخشش بیشترین وقتت رو می‌گیره؟ 😎🤖`;
    }

    // Live 9:16 Motion Story Canvas Animation
    const storyCanvas = document.getElementById('motionStoryCanvas');
    const storyCtx = storyCanvas.getContext('2d');
    const portraitImg = document.getElementById('sourceStoryPortraitImg');
    let animPhase = 0;

    function drawMotionStoryFrame() {
      animPhase += 0.045;
      const W = 360;
      storyCtx.setTransform(3,0,0,3,0,0);
      const H = 640;

      storyCtx.clearRect(0, 0, W, H);

      // Draw Portrait with subtle zoom
      if (portraitImg && portraitImg.complete && portraitImg.naturalWidth > 0) {
        const zoom = 1.0 + 0.025 * Math.sin(animPhase * 0.5);
        const sw = W * zoom;
        const sh = H * zoom;
        const sx = (W - sw) / 2;
        const sy = (H - sh) / 2;
        storyCtx.drawImage(portraitImg, sx, sy, sw, sh);
      } else {
        const grad = storyCtx.createLinearGradient(0, 0, 0, H);
        grad.addColorStop(0, '#0f172a');
        grad.addColorStop(1, '#020617');
        storyCtx.fillStyle = grad;
        storyCtx.fillRect(0, 0, W, H);
      }

      // Dark translucent HUD bands at top and bottom
      storyCtx.fillStyle = 'rgba(7, 11, 20, 0.76)';
      storyCtx.fillRect(0, 0, W, 82);
      storyCtx.fillRect(0, H - 165, W, 165);

      // Top HUD Cyan Brackets
      storyCtx.strokeStyle = '#22d3ee';
      storyCtx.lineWidth = 2;
      storyCtx.beginPath();
      storyCtx.moveTo(18, 22);
      storyCtx.lineTo(68, 22);
      storyCtx.moveTo(18, 22);
      storyCtx.lineTo(18, 56);
      storyCtx.moveTo(W - 18, 22);
      storyCtx.lineTo(W - 68, 22);
      storyCtx.moveTo(W - 18, 22);
      storyCtx.lineTo(W - 18, 56);
      storyCtx.stroke();

      // RTL Persian Texts with Vazirmatn font
      storyCtx.direction = 'rtl';
      storyCtx.textAlign = 'right';

      const badgeText = document.getElementById('storyBadgeInput').value;
      const headText = document.getElementById('storyHeadlineInput').value;
      const subText = document.getElementById('storySubInput').value;

      storyCtx.font = 'bold 11px Vazirmatn, sans-serif';
      storyCtx.fillStyle = '#67e8f9';
      storyCtx.fillText(badgeText, W - 26, 44, W - 52);

      storyCtx.font = 'bold 14px Vazirmatn, sans-serif';
      storyCtx.fillStyle = '#ffffff';
      storyCtx.fillText(headText, W - 24, H - 128, W - 48);

      storyCtx.font = '500 11.5px Vazirmatn, sans-serif';
      storyCtx.fillStyle = '#fde047';
      storyCtx.fillText(subText, W - 24, H - 102, W - 48);

      // Animated Equalizer & Hologram Ring
      const cx = W / 2;
      const cy = H - 52;
      const rPulse = 22 + 3.5 * Math.sin(animPhase * 2);

      storyCtx.beginPath();
      storyCtx.arc(cx, cy, rPulse, 0, Math.PI * 2);
      storyCtx.strokeStyle = '#22d3ee';
      storyCtx.lineWidth = 1.8;
      storyCtx.stroke();

      storyCtx.beginPath();
      storyCtx.arc(cx, cy, rPulse + 6, 0, Math.PI * 2);
      storyCtx.strokeStyle = 'rgba(250, 204, 21, 0.75)';
      storyCtx.lineWidth = 1;
      storyCtx.stroke();

      const bars = 20;
      const spacing = 10;
      const startX = cx - ((bars - 1) * spacing) / 2;
      storyCtx.strokeStyle = '#22d3ee';
      storyCtx.lineWidth = 2.5;
      for (let i = 0; i < bars; i++) {
        const h = 5 + 22 * Math.abs(Math.sin(animPhase * 1.8 + i * 0.45));
        const bx = startX + i * spacing;
        storyCtx.beginPath();
        storyCtx.moveTo(bx, cy - h / 2);
        storyCtx.lineTo(bx, cy + h / 2);
        storyCtx.stroke();
      }

      window._storyAnimId = requestAnimationFrame(drawMotionStoryFrame);
    }

document.fonts.ready.then(()=>{storyCanvas.width=1080;storyCanvas.height=1920;drawMotionStoryFrame();});
