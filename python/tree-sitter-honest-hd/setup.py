from setuptools import setup, Extension
setup(packages=["tree_sitter_honest_hd"],
  package_dir={"tree_sitter_honest_hd":"bindings/python/tree_sitter_honest_hd"},
  ext_modules=[Extension("tree_sitter_honest_hd._binding",
    sources=["src/parser.c","bindings/python/tree_sitter_honest_hd/binding.c"],
    include_dirs=["src"], extra_compile_args=["-std=c11"])])
