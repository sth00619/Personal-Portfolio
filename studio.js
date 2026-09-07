import {normalizeAmount,portfolioVolatility} from './data.js';
const $=s=>document.querySelector(s);
const stages=['원본 수집','문자열 파싱','단위 통일','검증·적재'];
const records=[['A · 매출',' 1,250 ','백만원','2025 · KRW',null],['B · 매출','3','억원','2025 · KRW',null],['C · 매출','','백만원','2025 · KRW','결측 · 보류'],['A · 매출','1,250','백만원','2025 · KRW','중복 · 보류'],['D · 매출','9,2x0','백만원','2025 · KRW','형식 오류'],['E · 매출','400','백만원','2024 · USD','기간·통화 불일치']];
let step=0,timer;
function stop(){clearInterval(timer);timer=null;$('#pipeline-play').textContent='자동 재생';$('#pipeline-play').setAttribute('aria-pressed','false');}
function renderPipeline(){
 $('#pipeline-steps').innerHTML=stages.map((s,i)=>`<span class="${i<=step?'active':''}"><b>0${i+1}</b>${s}</span>`).join('');
 $('#pipeline-rows').innerHTML=records.map(([name,raw,unit,context,reason])=>{
 let val=null,error=false;try{val=normalizeAmount(raw,unit);}catch{error=true;}
 const early=error||val===null,held=step>=1&&early||step===3&&reason;
 const display=step<1?'—':early?'—':step===1?raw.trim().replaceAll(',',''):val.toLocaleString('ko-KR')+' 원';
 return `<tr class="${held?'held':step===3?'accepted':''}"><td>${name}</td><td><code>“${raw}”</code> ${unit}</td><td>${context}</td><td>${display}</td><td>${held?reason:step===3?'적재 가능':stages[step]}</td></tr>`;
 }).join('');
 $('#pipeline-status').textContent=`${step+1} / 4 단계${step===3?' · 적재 가능 2건 / 보류 4건':''}`;
 $('#pipeline-explain').textContent=['원본 문자열과 단위·기간을 함께 보존합니다. 같은 기업의 같은 계정이 두 번 들어온 경우도 있습니다.','공백·쉼표를 제거하고 정수로 해석합니다. 빈 값을 0으로 채우거나 잘못된 문자를 조용히 제거하지 않습니다.','백만원은 10⁶, 억원은 10⁸을 곱해 원 단위로 맞춥니다. 공개 예제는 BigInt로 정수 정밀도를 유지합니다.','기준 기간·통화가 일치하고 중복되지 않는 2건만 남깁니다. 환율·환산 시점이 없으므로 USD를 임의 환산하지 않습니다.'][step];
 $('#pipeline-next').disabled=step===3;
}
$('#pipeline-next').onclick=()=>{stop();step=Math.min(3,step+1);renderPipeline();};
$('#pipeline-reset').onclick=()=>{stop();step=0;renderPipeline();};
$('#pipeline-play').onclick=()=>{if(timer){stop();return;}if(step===3)step=0;renderPipeline();$('#pipeline-play').textContent='일시 정지';$('#pipeline-play').setAttribute('aria-pressed','true');timer=setInterval(()=>{step++;renderPipeline();if(step===3)stop();},1600);};
document.querySelectorAll('[data-lab]').forEach(button=>button.onclick=()=>{stop();document.querySelectorAll('[data-lab]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));document.querySelectorAll('.lab').forEach(panel=>panel.hidden=panel.id!==`lab-${button.dataset.lab}`);});
function risk(){
 const w=+$('#studio-weight').value/100,rho=+$('#studio-rho').value;
 $('#studio-weight-label').textContent=`${Math.round(w*100)}%`;
 $('#studio-rho-label').textContent=rho.toFixed(1);
 const x=v=>50+550*v,y=v=>290-v/0.35*250;
 const curve=r=>Array.from({length:101},(_,i)=>`${i?'L':'M'}${x(i/100)},${y(portfolioVolatility(i/100,.2,.3,r))}`).join(' ');
 const vol=portfolioVolatility(w,.2,.3,rho);
 $('#risk-chart').innerHTML=`${[0,.1,.2,.3].map(v=>`<path d="M50 ${y(v)}H600" class="gridline"/><text x="6" y="${y(v)+5}">${Math.round(v*100)}%</text>`).join('')}<path d="${curve(1)}" class="baseline"/><path d="${curve(rho)}" class="risk-curve"/><path d="M${x(w)} 290V${y(vol)}" class="baseline"/><circle cx="${x(w)}" cy="${y(vol)}" r="8" class="chart-dot"/>${[0,.25,.5,.75,1].map(v=>`<text x="${x(v)-12}" y="320">${v*100}%</text>`).join('')}`;
 const a=w*w*.04,b=(1-w)**2*.09,c=2*w*(1-w)*.2*.3*rho;
 $('#risk-terms').innerHTML=[['A 분산 기여',a],['B 분산 기여',b],['공분산 항',c],['합계 분산',a+b+c]].map(([k,v])=>`<div><span>${k}</span><b>${v.toFixed(4)}</b></div>`).join('');$('#studio-risk-result').textContent=`${(vol*100).toFixed(2)}%`;
}
['studio-weight','studio-rho'].forEach(id=>$('#'+id).addEventListener('input',risk));
$('#image-reveal').addEventListener('input',e=>{const v=e.target.value;$('#image-after').style.clipPath=`inset(0 0 0 ${v}%)`;$('#compare-line').style.left=v+'%';$('#image-reveal-label').textContent=v+'%';});
function ab(){
 const n=+$('#ab-n').value,pA=.1,kB=Math.round(n*+$('#ab-rate').value/100),pB=kB/n,d=pB-pA,margin=1.96*Math.sqrt((pA*(1-pA)+pB*(1-pB))/n),lo=d-margin,hi=d+margin;
 $('#ab-n-label').textContent=`각 ${n.toLocaleString()}명`;
 $('#ab-rate-label').textContent=(pB*100).toFixed(1)+'%';
 $('#ab-bars').innerHTML=[['A · 기존 화면',pA,n*pA],['B · 단위·기준일 설명',pB,kB]].map(([s,p,k])=>`<div><span>${s}</span><div class="ab-track"><div style="width:${p/0.2*100}%"></div></div><b>${(p*100).toFixed(1)}% · ${k}/${n}</b></div>`).join('');
 const x=p=>320+p/.12*260;
 $('#ab-chart').innerHTML=`<path d="M60 100H580" class="gridline"/><path d="M320 25V130" class="baseline"/><path d="M${x(lo)} 80H${x(hi)}" class="risk-curve"/><circle cx="${x(d)}" cy="80" r="7" class="chart-dot"/>${[-.1,-.05,0,.05,.1].map(v=>`<text x="${x(v)-18}" y="153">${v*100}pp</text>`).join('')}`;
 $('#ab-result').textContent=`완료율 차이 ${(d*100).toFixed(2)}%p · 근사 95% 구간 [${(lo*100).toFixed(2)}, ${(hi*100).toFixed(2)}]%p. ${lo<=0&&hi>=0?'0을 포함하므로 방향을 확정하기 어렵습니다.':'0을 포함하지 않습니다. 다만 실무 의사결정에는 가드레일·설계 검증이 추가로 필요합니다.'}`;
}
['ab-n','ab-rate'].forEach(id=>$('#'+id).addEventListener('input',ab));
renderPipeline();risk();ab();
