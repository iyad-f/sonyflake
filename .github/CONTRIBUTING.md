# Contribution Guide

First off, thanks for taking the time to contribute. It makes the library substantially better. :+1:

## Setting up the environment

1. Install Astral's [UV](http://docs.astral.sh/uv/), if you haven't already.
2. Run `uv sync --all-groups` to create a [virtual environment](https://docs.python.org/3/tutorial/venv.html) and install dependencies.

## Good Bug Reports

Please be aware of the following things when filing bug reports.

1. Don't open duplicate issues. Please search your issue to see if it has been asked already. Duplicate issues will be closed.
2. When filing a bug about exceptions or tracebacks, please include the _complete_ traceback. Without the complete traceback the issue might be **unsolvable** and you will be asked to provide more information.
3. Make sure to provide enough information to make the issue workable. The issue template will generally walk you through the process, but they are enumerated here as well:
  - A **summary** of your bug report. This is generally a quick sentence or two to describe the issue in human terms.
  - Guidance on **how to reproduce the issue**. Ideally, this should have a small code sample that allows us to run and see the issue for ourselves to debug. **Please make sure that the token is not displayed**. If you cannot provide a code snippet, then let us know what the steps were, how often it happens, etc.
  - Tell us **what you expected to happen**. That way we can meet that expectation.
  - Tell us **what actually happens**. What ends up happening in reality? It's not helpful to say "it fails" or "it doesn't work". Say _how_ it failed, do you get an exception? Does it hang? How are the expectations different from reality?
  - Tell us **information about your environment**. What version of `sonyflake` are you using? How was it installed? What operating system are you running on? These are valuable questions and information that we use.

If the bug report is missing this information then it'll take us longer to fix the issue. We will probably ask for clarification, and barring that if no response was given then the issue will be closed.

## Submitting a Pull Request

Submitting a pull request is fairly simple, just make sure it focuses on a single aspect and doesn't manage to have scope creep, and it's probably good to go. It would be incredibly lovely if the style is consistent to that found in the project. This project follows PEP-8 guidelines (mostly) with a column limit of 125.
There are provided tool rules in `pyproject.toml` for `ruff` and `pyright` when committing here.
There are actions that run on new PRs and if those checks fail then the PR will not be accepted.
Pull requests and commits all need to follow the [Conventional Commit format](https://www.conventionalcommits.org)
