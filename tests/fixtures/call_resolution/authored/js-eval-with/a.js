function t() { return 1; }
function e() { eval('var t = 5'); return t(); }
function w(o) { with (o) { return t(); } }
