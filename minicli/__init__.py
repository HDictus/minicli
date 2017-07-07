import argparse
import inspect


NO_DEFAULT = object()
NARGS = ...

parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(title='Available commands', metavar='')

GLOBALS = {}


class Cli:

    def __init__(self, command):
        self.command = command
        self.inspect()
        self.init_parser()
        self.set_globals()

    def __call__(self, *args, **kwargs):
        """Run original command."""
        try:
            self.command(*args, **kwargs)
        except KeyboardInterrupt:
            pass

    def invoke(self, parsed):
        """Run command from command line args."""
        kwargs = {}
        args = []
        for name, parameter in self.spec.parameters.items():
            value = getattr(parsed, name)
            if parameter.kind == parameter.VAR_POSITIONAL:
                args.extend(value)
            elif parameter.default == inspect._empty:
                args.append(value)
            else:
                kwargs[name] = value
        kwargs.update(self.parse_globals(parsed))
        self(*args, **kwargs)

    def set_globals(self):
        for name, kwargs in GLOBALS.items():
            if not isinstance(kwargs, dict):
                kwargs = {'default': kwargs}
            self.add_argument(name, **kwargs)

    def parse_globals(self, parsed):
        return {k: getattr(parsed, k, None) for k in GLOBALS.keys()
                if hasattr(parsed, k)}

    @property
    def name(self):
        return self.command.__name__

    @property
    def help(self):
        return self.command.__doc__ or ''

    @property
    def short_help(self):
        return self.help.split('\n\n')[0]

    def inspect(self):
        self.__doc__ = inspect.getdoc(self.command)
        self.spec = inspect.signature(self.command)

    def parse_parameter_help(self, name):
        try:
            return (self.help.split(':{}:'.format(name), 1)[1]
                             .split('\n')[0].strip())
        except IndexError:
            return ''

    def init_parser(self):
        self.parser = subparsers.add_parser(self.name, help=self.short_help,
                                            conflict_handler='resolve')
        self.set_defaults(func=self.invoke)
        for name, parameter in self.spec.parameters.items():
            kwargs = {}
            default = parameter.default
            if default == inspect._empty:
                default = NO_DEFAULT
            if parameter.kind == parameter.VAR_POSITIONAL:
                default = NARGS
            type_ = parameter.annotation
            if type_ != inspect._empty:
                kwargs['type'] = type_
            self.add_argument(name, default, **kwargs)

    def add_argument(self, name, default=NO_DEFAULT, **kwargs):
        if 'help' not in kwargs:
            kwargs['help'] = self.parse_parameter_help(name)
        args = [name]
        if default not in (NO_DEFAULT, NARGS):
            if '_' not in name:
                args.append('-{}'.format(name[0]))
            args[0] = '--{}'.format(name.replace('_', '-'))
            kwargs['dest'] = name
            kwargs['default'] = default
            type_ = kwargs.pop('type', type(default))
            if type_ == bool:
                action = 'store_false' if default else 'store_true'
                kwargs['action'] = action
            elif type_ in (int, str):
                kwargs['type'] = type_
            elif type_ in (list, tuple):
                kwargs['nargs'] = '*'
            elif callable(default):
                kwargs['type'] = type_
                kwargs['default'] = ''
        elif default == NARGS:
            kwargs['nargs'] = '*'
        self.parser.add_argument(*args, **kwargs)

    def set_defaults(self, **kwargs):
        self.parser.set_defaults(**kwargs)


def cli(*args, **kwargs):
    if not args:
        # User-friendlyness: allow usage @cli() without any argument.
        return cli
    elif isinstance(args[0], Cli):
        args[0].add_argument(*args[1:], **kwargs)
        return args[0]
    elif callable(args[0]):
        inst = Cli(args[0])
        if len(args) > 1:
            inst.add_argument(*args[1:], **kwargs)
        return inst
    elif args or kwargs:
        # We are overriding an argument from the decorator.
        return lambda f: cli(f, *args, **kwargs)


def run(*args):
    parsed = parser.parse_args(args or None)
    if hasattr(parsed, 'func'):
        parsed.func(parsed)
    else:
        # No argument given, just display help.
        parser.print_help()
