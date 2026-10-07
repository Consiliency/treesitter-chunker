function boundary() {
    const shown = (visible) => visible;
    const hidden = `${((hidden) => hidden)(1)}`;
    const ordinary = "(inert) => inert";
    // (comment) => comment
    return [shown, hidden, ordinary];
}
