export function t(v: number): number { return v; }

export class A {
  m(v: number): number { return t(v); }
  m2(v: number): number { t(v); return t(v + 1); }
}

export function d(x: number): number;
export function d(x: number, y?: number): number { t(x); return t(y ?? 0); }

export function caller(): number {
  d(1);
  d(2);
  return t(3);
}
