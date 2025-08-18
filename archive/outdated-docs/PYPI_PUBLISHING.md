# PyPI Publishing Instructions

## Prerequisites

1. Create a PyPI account at https://pypi.org/account/register/
2. Generate an API token at https://pypi.org/manage/account/token/
3. Save the token securely (starts with `pypi-`)

## Manual Publishing (First Time)

1. **Set up authentication**:
   ```bash
   # Option 1: Using token (recommended)
   export TWINE_USERNAME=__token__
   export TWINE_PASSWORD=your-token-here
   
   # Option 2: Create ~/.pypirc file
   [pypi]
   username = __token__
   password = pypi-AgEIcHlwaS5vcmcCJGNmNjE5...
   ```

2. **Upload to TestPyPI first** (optional but recommended):
   ```bash
   twine upload --repository testpypi dist/treesitter_chunker-1.0.0*
   
   # Test installation
   pip install --index-url https://test.pypi.org/simple/ treesitter-chunker
   ```

3. **Upload to PyPI**:
   ```bash
   twine upload dist/treesitter_chunker-1.0.0*
   ```

## Automated Publishing (GitHub Actions)

The repository is now configured for automated publishing via GitHub Actions.

### Setup Trusted Publishing

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new trusted publisher:
   - **PyPI Project Name**: treesitter-chunker
   - **GitHub Repository Owner**: Consiliency
   - **GitHub Repository Name**: treesitter-chunker
   - **Workflow name**: release.yml
   - **Environment name**: pypi (optional but recommended)

3. Once configured, the GitHub Action will automatically publish to PyPI when:
   - A new release is created on GitHub
   - A tag starting with 'v' is pushed

### Manual Workflow Trigger

You can also trigger the release workflow manually:
1. Go to Actions tab on GitHub
2. Select "Release" workflow
3. Click "Run workflow"
4. Enter version and options

## Post-Publishing Checklist

- [ ] Verify package on PyPI: https://pypi.org/project/treesitter-chunker/
- [ ] Test installation: `pip install treesitter-chunker`
- [ ] Update documentation if needed
- [ ] Announce release on relevant channels

## Conda-forge Publishing

After PyPI release, submit to conda-forge:

1. Fork https://github.com/conda-forge/staged-recipes
2. Create recipe using: `grayskull pypi treesitter-chunker`
3. Submit PR with recipe
4. Follow reviewer feedback

## Docker Registry

Build and push Docker image:
```bash
docker build -t ghcr.io/consiliency/treesitter-chunker:1.0.0 .
docker push ghcr.io/consiliency/treesitter-chunker:1.0.0
docker tag ghcr.io/consiliency/treesitter-chunker:1.0.0 ghcr.io/consiliency/treesitter-chunker:latest
docker push ghcr.io/consiliency/treesitter-chunker:latest
```