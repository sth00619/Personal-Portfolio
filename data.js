// 공개 설명용 가상 데이터 계산입니다. 실제 서비스 코드·시장 데이터·API를 사용하지 않습니다.
const UNIT_SCALE = { '원': 1n, '백만원': 1000000n, '억원': 100000000n };
export function normalizeAmount(raw, unit) {
  if (!(unit in UNIT_SCALE)) throw new Error('단위를 확인해 주세요.');
  const value=String(raw).trim();
  if (!value) return null;
  if (!/^-?(?:\d+|\d{1,3}(?:,\d{3})+)$/.test(value) || value.replaceAll(',','').replace('-','').length>18) throw new Error('18자리 이내 정수를 입력하세요. 쉼표는 세 자리마다 구분합니다.');
  return BigInt(value.replaceAll(',','')) * UNIT_SCALE[unit];
}
export function changeRate(previous,current) {
  if (![previous,current].every(Number.isFinite) || previous<=0 || current<0) return null;
  return (current-previous)/previous*100;
}
export function valuation(cap,income) {
  if (cap<=0n || income<=0n) return null;
  return Number(cap)/Number(income);
}
export function portfolioVolatility(weight,sigmaA,sigmaB,rho) {
  if (![weight,sigmaA,sigmaB,rho].every(Number.isFinite)||weight<0||weight>1||sigmaA<0||sigmaB<0||Math.abs(rho)>1) throw new Error('비중·변동성·상관계수의 범위를 확인해 주세요.');
  const b=1-weight;
  return Math.sqrt(Math.max(0,weight**2*sigmaA**2+b**2*sigmaB**2+2*weight*b*sigmaA*sigmaB*rho));
}
