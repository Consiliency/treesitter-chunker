def boundary():
    shown = (lambda visible: visible,)
    hidden = f"{(lambda hidden: hidden)}"
    ordinary = "lambda inert: inert"
    # lambda comment: comment
    return shown, hidden, ordinary
