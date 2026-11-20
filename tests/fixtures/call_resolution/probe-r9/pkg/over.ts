export function f(x: string): string;
export function f(x: number): number;
export function f(x: any): any { return x; }
interface Box { n: number }
class Box { constructor(public n: number) {} }
export function g(): number { return f(1) + new Box(2).n; }
