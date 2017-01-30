from importlib import import_module
import os
import pkgutil


def init_view_modules(current_dir, parent_path=None):
    """Initializes all modules named `views.py`.

    :param current_dir: The abspath of a directory.  Will iterate
        recursively through the directories files and submodules.

    :param parent_path: Should always equal `None` during
        initial invocation.  Assigned to the parent directory of
        the initial current_dir.  This is stripped from all
        following recursive iterations to generate the `prefix`.
        The `prefix` is a string of the import path of the file

        eg. `powernap.architect.blueprints`

    We have to initialize `views.py` files that use
    :class:`powernap.architect.blueprints.Architect` to add blueprints,
    otherwise the :meth:`Architect.register` will do nothing.
    Because the `views.py` files were not initialized,
    :meth:`sub_blueprint` will never get run and there will be no
    blueprints in `Architect`'s `self.blueprints`.
    """
    for importer, modname, ispkg in pkgutil.iter_modules([current_dir]):
        if not parent_path:
            parent_path, prefix = os.path.split(current_dir)
        else:
            # Convert the abspath to a valid import path.
            prefix = current_dir[len(parent_path) + 1:].replace('/', '.')
        prefix += ".{}".format(modname)
        if ispkg:
            new_path = "{}/{}".format(current_dir, modname)
            init_view_modules(new_path, parent_path)
        else:
            # TODO: Make this accessible via an Environment variable.
            if prefix.split('.')[-1] in ["views"]:
                try:
                    import_module(prefix)
                    print("LOADED:", prefix)
                except ImportError as err:
                    print("ERROR IMPORTING:", prefix, err)
