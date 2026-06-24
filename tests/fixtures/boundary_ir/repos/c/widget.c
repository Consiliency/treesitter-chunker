struct Widget {
    int count;
};

int helper(int value) {
    return value + 1;
}

int render(struct Widget *w) {
    return helper(w->count);
}
