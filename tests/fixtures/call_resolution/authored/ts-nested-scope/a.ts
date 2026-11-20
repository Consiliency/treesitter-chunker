export function t() { return 1; }
export function outer() {
  function t() { return 2; }
  return t();
}
export function blk() {
  { const t = () => 3; return t(); }
}
