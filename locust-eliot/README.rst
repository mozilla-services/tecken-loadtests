====================
README: locust-eliot
====================

Directory of load test bits for the Mozilla Symbolication Service.

Run this from the root of this repository::

    make shell
    cd locust-eliot

Then run the scripts from there.

For methodology and such, see:

* `<https://bugzilla.mozilla.org/show_bug.cgi?id=1827719>`__
* `<https://docs.google.com/document/d/1oKVhvs2DMd28dhj3RWpNjY6pLgJm1CWPkrVTjw38564/edit#>`__


Testfile
========

``testfile.py``
    This runs a Locust test case which uses stacks in ``../stacks/`` and schema
    files in ``../schemas/``.


Scripts
=======

``prime_env.sh``
    Primes a fresh environment that has a cold cache.

``loadtest_normal.sh``
    Runs a "normal load" load test.

``loadtest_high.sh``
    Runs a "high_load" load test.
