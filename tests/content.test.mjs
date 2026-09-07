import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile,readdir } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
test('공개 빌드에 내부 브리프·문서·원본 자료가 들어가지 않는다',async()=>{
 execFileSync(process.execPath,['scripts/build.mjs']);
 assert.deepEqual((await readdir('dist')).sort(),['app.js','assets','data.js','index.html','projects-library.js','studio.js','styles.css']);
 assert.deepEqual(await readdir('dist/assets'),['favicon.svg','image-review.jpg']);
});
test('기본 HTML만으로 모든 프로젝트와 금융 설명에 접근할 수 있다',async()=>{
 const html=await readFile('index.html','utf8');
 for(const id of ['finai','capstone','kis','quality','etl','data','theory','workstyle']) assert.ok(html.includes(`id="${id}"`));
 assert.equal((html.match(/data-project-roles=/g)||[]).length,5);
 for(const forbidden of ['public/evidence','/Users/','localhost:8080','sh_profile','327,503','71%']) assert.ok(!html.includes(forbidden));
 assert.ok(html.includes('가상 계산 예제'));
 assert.ok(!html.includes('PORTFOLIO_REVAMP_BRIEF'));
});
test('기존 중복 workflow도 저장소 전체를 배포하지 않는다',async()=>{
 const deploy=await readFile('.github/workflows/deploy.yml','utf8');
 const old=await readFile('.github/workflows/static.yml','utf8');
 assert.ok(deploy.includes('path: dist'));
 assert.ok(!old.includes('upload-pages-artifact'));
 assert.ok(!old.includes('deploy-pages'));
});
