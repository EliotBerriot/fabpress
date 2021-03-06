#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base
import os
from fabpress import utils
from fabric.api import hide, warn_only

class WPFilesDrop(base.ConfirmTask, base.TargetTask):
    """Remove all files of target, including target directory"""

    name = "drop"

    def operation(self, target):
        command = 'find {0}/ -name "*" | xargs rm -rf '.format(os.path.join(utils.setting("path", target)))
        self.subtask(base.run_target, target=target, command=command)

drop = WPFilesDrop()


class WPSymlink(base.AbstractBaseTask):
    """Create a symlink on local to target directory"""

    name = "symlinks"
    symlink_directory = ""
    target = "local"

    def operation(self, target, symlink_name):
        path = os.path.join(utils.setting('path', self.target), self.symlink_directory, symlink_name)
        self.info("Symlinking {0} to {1}".format(target, path))
        command = "ln -s '{0}' '{1}'".format(target, path)
        with hide('everything'), warn_only():
            self.subtask(base.run_target, 'local', command)


class WPPluginSymlink(WPSymlink):
    symlink_directory="wp-content/plugins"

class WPThemeSymlink(WPSymlink):
    symlink_directory="wp-content/themes"


plugin_symlink = WPPluginSymlink()
theme_symlink = WPThemeSymlink()
