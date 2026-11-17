"""An example adopter whose chain cannot be contract-checked: the chain skip case.

The chain's upstream link declares no vocabulary (@link() with no accepts), so there are
no input cases to enumerate and no way to produce the upstream outputs the contract check
feeds downstream. run_suite discovers the chain but skips the contract check for it, so it
reports zero failures and does not crash on enumerate_test_cases(None). The two links are
also vocabulary-less, so the honesty checks skip them too.
"""

from honest_type import chain, link


@link()
def first(manifest):
    """Upstream with no declared vocabulary: nothing to enumerate it over."""
    return {**manifest, "stage": "first"}


@link()
def second(manifest):
    """Downstream, also untyped."""
    return {**manifest, "stage": "second"}


untyped_pipeline = chain(first, second)
