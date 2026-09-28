class Receipt {
    vendor: string @stream.done,
    total: float?,
    items: string[],
}

function extract(text: string) -> Receipt {
    client: "openai/gpt-5.6-luna"
    prompt: `${text} ${ctx.output_format()}`
}

type Ack = 1n;

function classify(text: string) -> string {
    client: "typesafeai/jev-latest"
    prompt: `Classify the sentiment of: ${text}`
}
