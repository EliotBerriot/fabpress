#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base
import os, datetime
from fabpress import utils

class WPMediaSync(base.ConfirmTask, base.TargetTask):
    """Download origin media files to target"""

    name = "sync"

    
    def operation(self, target):
        origin = utils.reverse(target)
        media_files = os.path.join(utils.setting("path", origin), "wp-content", "uploads", "*")
        target_media_path = os.path.join(utils.setting("path", target), "wp-content", "uploads")
        self.log("Syncing media files from {0} to {1} (please, be patient, this may take some time)".format(utils.reverse(self.target), self.target))
        self.subtask(base.get_file, target=utils.reverse(origin), origin_path=media_files, target_path=target_media_path)

sync = WPMediaSync()
