// Generator dependency context for treesitter-chunker#289.
function ordinary(input) {
  const secret = input + 1;
  return secret;
}

function* generated(input) {
  const secret = input + 1;
  yield secret;
}

export function exportedOrdinary(input) {
  const secret = input + 1;
  return secret;
}

export function* exportedGenerated(input) {
  const secret = input + 1;
  yield secret;
}

function consumer() {
  return [
    ordinary(1),
    ...generated(2),
    exportedOrdinary(3),
    ...exportedGenerated(4),
  ];
}

consumer();
