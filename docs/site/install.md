# Install

## From PyPI

```bash
pip install codeupipe
```

## From Source (Development)

```bash
git clone https://github.com/codeuchain/codeupipe.git
cd codeupipe
pip install -e '.[dev]'
```

## Requirements

- **Python 3.9+** (tested on 3.9, 3.12, 3.13)
- **Zero external dependencies** — stdlib only

## Verify

```python
import codeupipe
print(codeupipe.__version__)
```

```bash
cup --help
```

## Connectors (Optional)

Official connectors are separate packages:

```bash
pip install codeupipe-postgres     # PostgreSQL
pip install codeupipe-stripe       # Stripe payments
pip install codeupipe-resend       # Resend email
pip install codeupipe-google-ai    # Google Gemini AI
```

Each connector auto-registers via the entry-point protocol. See the [Marketplace](https://github.com/codeuchain/codeupipe) for the full list.
