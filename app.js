import { normalizeAmount, valuation, portfolioVolatility } from './data.js';
import { ROLE_LENSES } from './projects-library.js';
const q=s=>document.querySelector(s);
function setRole(role){
  if(!ROLE_LENSES[role])role='all';
  document.querySelectorAll('[data-role-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.roleFilter===role)));
  let count=0;
  document.querySelectorAll('[data-project-roles]').forEach(card=>{card.hidden=role!=='all'&&!card.dataset.projectRoles.split(' ').includes(role);if(!card.hidden)count++;});
  q('#role-description').textContent=ROLE_LENSES[role].text;
  q('#case-count').textContent=`${count}개 프로젝트`;
}
document.querySelectorAll('[data-role-filter]').forEach(b=>b.addEventListener('click',()=>setRole(b.dataset.roleFilter)));
function updateUnits(){
 const out=q('#normalized-value'),error=q('#unit-error');
 try {const value=normalizeAmount(q('#amount').value,q('#amount-unit').value);out.textContent=value===null?'결측 · 계산 보류':`${value.toLocaleString('ko-KR')} 원`;error.textContent='';}
 catch(e){out.textContent='형식 오류 · 계산 보류';error.textContent=e.message;}
}
q('#amount').addEventListener('input',updateUnits);q('#amount-unit').addEventListener('change',updateUnits);updateUnits();
function updatePer(){
 const out=q('#per-result');
 try{const cap=normalizeAmount(q('#market-cap').value,'억원');const income=normalizeAmount(q('#net-income').value,'백만원');
 if(cap===null||income===null){out.textContent='입력 누락 · 계산 보류';return;}
 const ratio=valuation(cap,income);out.textContent=ratio===null?'양수 분모·시가총액 확인 필요':`${ratio.toFixed(2)} 배`;
 }catch{out.textContent='정수 형식 확인 필요';}
}
q('#market-cap').addEventListener('input',updatePer);q('#net-income').addEventListener('input',updatePer);updatePer();
function updateRisk(){
 const weight=Number(q('#weight').value)/100,rho=Number(q('#correlation').value);
 const vol=portfolioVolatility(weight,.2,.3,rho)*100;
 q('#weight-value').textContent=`A ${Math.round(weight*100)}% / B ${Math.round((1-weight)*100)}%`;
 q('#correlation-value').textContent=rho.toFixed(1);
 q('#risk-result').textContent=`${vol.toFixed(2)}%`;
 q('#risk-fill').style.width=`${vol/30*100}%`;
}
q('#weight').addEventListener('input',updateRisk);q('#correlation').addEventListener('input',updateRisk);updateRisk();
q('#print-page').addEventListener('click',()=>window.print());
