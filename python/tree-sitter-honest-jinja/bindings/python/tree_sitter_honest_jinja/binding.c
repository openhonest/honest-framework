#include <Python.h>
typedef struct TSLanguage TSLanguage;
TSLanguage *tree_sitter_honest_jinja(void);
static PyObject* _language(PyObject *s, PyObject *a){ return PyCapsule_New(tree_sitter_honest_jinja(), "tree_sitter.Language", NULL); }
static PyMethodDef m[] = {{"language",_language,METH_NOARGS,"language"},{NULL,NULL,0,NULL}};
static struct PyModuleDef mod = {PyModuleDef_HEAD_INIT,"tree_sitter_honest_jinja._binding",NULL,-1,m};
PyMODINIT_FUNC PyInit__binding(void){ return PyModule_Create(&mod); }
