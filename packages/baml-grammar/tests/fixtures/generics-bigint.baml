class Reading {
    sensor: string,
    nanoseconds: bigint,
}

type Id = 1n | 2n;

function round_trip(text: string) -> string {
    let reading = baml.json.from_string<Reading>(text);
    baml.json.to_string(reading)
}
