export function t() { return 1; }
export function g() {
  { t(); const t = () => 2; }
}
