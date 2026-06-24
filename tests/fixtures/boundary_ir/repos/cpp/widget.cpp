enum Color { RED, GREEN, BLUE };

class Widget {
public:
    int count;

    int render() {
        return helper();
    }

    int helper() {
        return count + 1;
    }
};

int run() {
    Widget w;
    return w.render();
}
