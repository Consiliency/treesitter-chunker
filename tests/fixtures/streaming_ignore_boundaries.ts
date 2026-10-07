function boundary() {
    const shown = (visible: number) => visible;
    const hidden = `${((hidden: number) => hidden)(1)}`;
    const ordinary = "(inert: number) => inert";
    // (comment: number) => comment
    return [shown, hidden, ordinary];
}
