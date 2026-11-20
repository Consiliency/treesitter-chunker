export function onlyA(): number { return 1; }
export function onlyB(): number { return 2; }
export class K {
  m(a: number): number {
    return onlyA();
  }
  m(a: string): number {
    return onlyB();
  }
}
