#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "tree_sitter/parser.h"

extern const TSLanguage *tree_sitter_baml(void);

static PyObject *language(PyObject *self, PyObject *unused) {
    return PyCapsule_New((void *)tree_sitter_baml(), "tree_sitter.Language", NULL);
}

static PyMethodDef methods[] = {
    {"language", language, METH_NOARGS, "Return the pinned BAML grammar capsule."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "_binding",
    NULL,
    -1,
    methods,
};

PyMODINIT_FUNC PyInit__binding(void) {
    return PyModule_Create(&module);
}
