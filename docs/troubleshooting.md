# Troubleshooting

## Common Issues

### "Required status check 'CI' is expected" when trying to push

This usually means branch protection is configured to require a pull request. You cannot push directly to `main`.

**Solution**: Create a branch, push it, open a PR, then merge (using admin rights if you're the owner and CI is green).

### Inner run keeps timing out

Increase `--timeout` and/or use `--wait-for-completion --max-wait`.

### The generated patch doesn't apply cleanly

This can happen if the target directory has diverged since the delegation started. Review the actual changes in the working directory rather than blindly applying the patch.

### Import errors in tests after renaming / packaging changes

The test suite has some legacy import hacks from the rename to `code_delegation_harness`. Run tests with `python -m pytest` after `pip install -e .` for the most reliable results.

## Getting Help

- Check the [CLI Reference](usage/cli-reference.md)
- Review [For Agents and Sidecars](usage/for-agents-and-sidecars.md) if you're building on top of this
- Open an issue with as much context as possible (command used, error output, target directory state)
