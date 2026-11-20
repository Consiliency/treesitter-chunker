export function t(x: number): number { return x + 1; }
export function caller(): number { return t(3) + t(4); }
