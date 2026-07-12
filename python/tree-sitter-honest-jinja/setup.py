from setuptools import setup, Extension
setup(packages=["tree_sitter_honest_jinja"],
  package_dir={"tree_sitter_honest_jinja":"bindings/python/tree_sitter_honest_jinja"},
  ext_modules=[Extension("tree_sitter_honest_jinja._binding",
    sources=["src/parser.c","bindings/python/tree_sitter_honest_jinja/binding.c"],
    include_dirs=["src"], extra_compile_args=["-std=c11"])])
