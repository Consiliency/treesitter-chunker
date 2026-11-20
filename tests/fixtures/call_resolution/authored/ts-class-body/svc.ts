export function t() { return 1; }
export class A {
  t() { return 0; }
  m() { return t(); }
}
