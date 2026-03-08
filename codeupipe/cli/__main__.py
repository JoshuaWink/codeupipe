"""Allow ``python -m codeupipe.cli`` to work as a package entry-point."""

from codeupipe.cli import main

raise SystemExit(main())
