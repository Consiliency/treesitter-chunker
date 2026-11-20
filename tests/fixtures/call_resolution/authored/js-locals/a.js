export function t() { return 1; }
export function c1() { try { return 0; } catch (t) { return t(); } }
export function c2(xs) { for (const t of xs) { t(); } }
export function c3({ t }) { return t(); }
export function c4() { let t = mk(); return t(); }
export function c6() { var t = mk(); return t(); }
function mk() { return () => 3; }
