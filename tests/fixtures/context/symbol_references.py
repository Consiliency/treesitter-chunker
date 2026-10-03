def render(value=None, **kwargs):
    return value


render("call")
holder = type("Holder", (), {"render": "property"})()
property_value = holder.render
render(render="keyword")
