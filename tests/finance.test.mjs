import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeAmount, changeRate, valuation, portfolioVolatility } from '../data.js';
test('금액 구분자와 단위를 정규화하고 결측·모호한 형식을 구별한다',()=>{
 assert.equal(normalizeAmount('1,250','백만원'),1250000000n);
 assert.equal(normalizeAmount(' -1,250 ','원'),-1250n);
 assert.equal(normalizeAmount('','원'),null);
 assert.throws(()=>normalizeAmount('1,25','원'));
 assert.throws(()=>normalizeAmount('1e9','원'));
 assert.throws(()=>normalizeAmount('1250','미확인'));
});
test('변화율, 분모 0, 적자 PER, 단위가 통일된 비율',()=>{
 assert.equal(changeRate(100,110),10);
 assert.equal(changeRate(0,110),null);
 assert.equal(valuation(1000000000000n,50000000000n),20);
 assert.equal(valuation(1000n,-50n),null);
});
test('상관계수 경계에서 포트폴리오 위험을 계산한다',()=>{
 assert.ok(Math.abs(portfolioVolatility(.5,.2,.2,1)-.2)<1e-10);
 assert.equal(portfolioVolatility(.5,.2,.2,-1),0);
 assert.equal(portfolioVolatility(1,.2,.3,0),.2);
 assert.throws(()=>portfolioVolatility(.5,.2,.3,2));
});
