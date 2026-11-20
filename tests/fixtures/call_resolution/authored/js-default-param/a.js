function wrap(t) {
  function f(x = t()) {
    function t() { return 1; }
    return x;
  }
  return f;
}
