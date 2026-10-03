function formatName(value) {
  return value;
}

const object = { formatName: "property" };
formatName("call");
object.formatName;

function* generate() {
  yield formatName("generator call");
}
generate();
