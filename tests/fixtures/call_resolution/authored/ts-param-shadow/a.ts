export function t() { return 1; }
export function run(t: () => number) { return t(); }
export function loc() { const t = make(); return t(); }
function make() { return () => 3; }
