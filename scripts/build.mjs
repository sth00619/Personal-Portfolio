import { mkdir, rm, copyFile } from 'node:fs/promises';
// 검토한 공개 파일만 배포합니다. 브리프·내부 문서·원본 데이터는 복사하지 않습니다.
const files=['index.html','styles.css','app.js','data.js','projects-library.js','assets/favicon.svg'];
await rm('dist',{recursive:true,force:true});
await mkdir('dist/assets',{recursive:true});
for(const file of files) await copyFile(file,`dist/${file}`);
console.log(`공개 파일 ${files.length}개 준비 완료`);
