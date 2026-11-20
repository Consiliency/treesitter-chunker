function g(x) {
  function d() { return 1; }
  if (x) { function d() { return 2; } }
  return d();
}
