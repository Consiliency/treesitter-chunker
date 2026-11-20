function only_a() { return 1; }
function only_b() { return 2; }
function d(x) {
  return only_a();
}
function d(x, y) {
  return only_b();
}
function g() { return d(1); }
