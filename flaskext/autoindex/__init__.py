# -*- coding: utf-8 -*-
"""
    flaskext.autoindex
    ~~~~~~~~~~~~~~~~~~

    A mod_autoindex for `Flask <http://flask.pocoo.org/>`_.

    :copyright: (c) 2010 by Lee Heung-sub.
    :license: BSD, see LICENSE for more details.
"""
import os.path
import re
from werkzeug import cached_property
from jinja2 import FileSystemLoader, TemplateNotFound
from flask import *
from flaskext.silk import Silk
from .entry import *
from . import icons


__autoindex__ = "__autoindex__"


class AutoIndex(object):
    """This class makes the Flask application to serve automatically
    generated index page. The wrapped application will route ``/`` and
    ``/<path:path>`` when ``add_url_rules`` is ``True``. Here's a simple
    example::

        app = Flask(__name__)
        idx = AutoIndex(app, "/home/someone/public_html", add_url_rules=True)
    """

    def _register_shared_autoindex(self, state=None, app=None):
        """Registers a magic module named __autoindex__."""
        app = app or state.app
        if __autoindex__ not in app.modules:
            shared_mod = Module(__name__)
            AutoIndex(shared_mod)
            app.modules[__autoindex__] = shared_mod

    def __new__(cls, base, *args, **kwargs):
        if isinstance(base, Flask):
            return object.__new__(AutoIndexApplication)
        elif isinstance(base, Module):
            return object.__new__(AutoIndexModule)
        else:
            raise TypeError("'base' should be Flask or Module.")

    def __init__(self, base, browse_root=None, add_url_rules=False,
                 **silk_options):
        """Initializes an autoindex instance.

        :param base: a flask application
        :param browse_root: a path which is served by root address.
        :param add_url_rules: if it is ``True``, the wrapped application routes
                              ``/`` and ``/<path:path>`` to autoindex. default
                              is ``False``.
        :param **silk_options: keyword options for :class:`flaskext.silk.Silk`
        """
        self.base = base
        if browse_root:
            self.rootdir = RootDirectory(browse_root, autoindex=self)
        else:
            self.rootdir = None
        self.silk = Silk(self.base, **silk_options)
        self.icon_map = []
        self.converter_map = []
        if add_url_rules:
            @self.base.route("/")
            @self.base.route("/<path:path>")
            def autoindex(path="."):
                return self.render_autoindex(path)

    def render_autoindex(self, path, browse_root=None, template=None):
        """Renders an autoindex with the given path.

        :param path: the relative path
        :param browse_root: if it is specified, it used to a path which is
                            served by root address.
        :param template: a template name
        """
        if browse_root:
            rootdir = RootDirectory(browse_root, autoindex=self)
        else:
            rootdir = self.rootdir
        path = re.sub("\/*$", "", path)
        abspath = os.path.join(rootdir.abspath, path)
        if os.path.isdir(abspath):
            sort_by = request.args.get("sort_by", "name")
            order = {"asc": 1, "desc": -1}[request.args.get("order", "asc")]
            curdir = Directory(path, rootdir)
            entries = curdir.explore(sort_by=sort_by, order=order)
            context = dict(curdir=curdir, path=path, entries=entries,
                           sort_by=sort_by, order=order, readme=None)
            if template:
                return render_template(template, **context)
            try:
                template = "{0}autoindex.html".format(self.template_prefix)
                return render_template(template, **context)
            except TemplateNotFound as e:
                template = "{0}/autoindex.html".format(__autoindex__)
                return render_template(template, **context)
        elif os.path.isfile(abspath):
            return send_file(abspath)
        else:
            return abort(404)

    def add_icon_rule(self, icon, rule=None, ext=None, mimetype=None,
                      name=None, filename=None, dirname=None, cls=None):
        """Adds a new icon rule.
        
        There are many shortcuts for rule. You can use one or more shortcuts in
        a rule.

        `rule`
            A function which returns ``True`` or ``False``. It has one argument
            which is an instance of :class:`Entry`. Example usage::

                def has_long_name(ent):
                    return len(ent.name) > 10
                idx.add_icon_rule("brick.png", rule=has_log_name)

            Now the application represents files or directorys such as
            ``very-very-long-name.js`` with ``brick.png`` icon.

        `ext`
            A file extension or file extensions to match with a file::

                idx.add_icon_rule("ruby.png", ext="ruby")
                idx.add_icon_rule("bug.png", ext=["bug", "insect"])

        `mimetype`
            A mimetype or mimetypes to match with a file::

                idx.add_icon_rule("application.png", mimetype="application/*")
                idx.add_icon_rule("world.png", mimetype=["image/icon", "x/*"])

        `name`
            A name or names to match with a file or directory::

                idx.add_icon_rule("error.png", name="error")
                idx.add_icon_rule("database.png", name=["mysql", "sqlite"])

        `filename`
            Same as `name`, but it matches only a file.

        `dirname`
            Same as `name`, but it matches only a directory.

        If ``icon`` is callable, it is used to ``rule`` function and the result
        is used to the url for an icon. This way is useful for getting an icon
        url dynamically. Here's a nice example::

            def get_favicon(ent):
                favicon = "favicon.ico"
                if type(ent) is Directory and favicon in ent:
                    return "/" + os.path.join(ent.path, favicon)
                return False
            idx.add_icon_rule(get_favicon)

        Now a directory which has a ``favicon.ico`` guesses the ``favicon.ico``
        instead of silk's ``folder.png``.
        """
        if name:
            filename = name
            directoryname = name
        if ext:
            File.add_icon_rule_by_ext.im_func(self, icon, ext)
        if mimetype:
            File.add_icon_rule_by_mimetype.im_func(self, icon, mimetype)
        if filename:
            File.add_icon_rule_by_name.im_func(self, icon, filename)
        if dirname:
            Directory.add_icon_rule_by_name.im_func(self, icon, dirname)
        if cls:
            Entry.add_icon_rule_by_class.im_func(self, icon, cls)
        if callable(rule) or callable(icon):
            Entry.add_icon_rule.im_func(self, icon, rule)

    def send_static_file(self, filename):
        """Serves a static file. It finds the file from autoindex internal
        static directory first. If it failed to find the file, it finds from
        the wrapped application or module's static directory.
        """
        global_static = os.path.join(os.path.dirname(__file__), "static")
        if os.path.isfile(os.path.join(global_static, filename)):
            static = global_static
        else:
            static = os.path.join(self.base.root_path, "static")
        return send_from_directory(static, filename)

    @property
    def template_prefix(self):
        raise NotImplementedError()


class AutoIndexApplication(AutoIndex):

    template_prefix = ""

    def __init__(self, app, browse_root=None, **silk_options):
        super(AutoIndexApplication, self).__init__(app, browse_root,
                                                   **silk_options)
        self.app = app
        self.app.view_functions["static"] = self.send_static_file
        self._register_shared_autoindex(app=self.app)


class AutoIndexModule(AutoIndex):

    def __init__(self, mod, browse_root=None, **silk_options):
        super(AutoIndexModule, self).__init__(mod, browse_root, **silk_options)
        self.mod = self.base
        self.mod._record(self._register_shared_autoindex)
        self.mod.send_static_file = self.send_static_file

    @cached_property
    def template_prefix(self):
        return self.mod.name + "/"

