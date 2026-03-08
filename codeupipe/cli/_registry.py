"""
CommandRegistry — routes CLI command names to handler functions.

Each command module calls ``registry.register(name, handler)`` during setup.
``main()`` calls ``registry.dispatch(args)`` instead of cascading if/elif.
"""


class CommandRegistry:
    """Map command names to handler callables."""

    def __init__(self):
        self._handlers = {}

    def register(self, name, handler):
        """Bind *name* → *handler*.  handler(args) → int exit code."""
        self._handlers[name] = handler

    def dispatch(self, args):
        """Look up ``args.command`` and call the matching handler.

        Returns the handler's exit code, or ``None`` when no handler
        is registered for the command.
        """
        handler = self._handlers.get(args.command)
        if handler is None:
            return None
        return handler(args)

    @property
    def commands(self):
        return set(self._handlers.keys())


registry = CommandRegistry()
