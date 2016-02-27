# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

import os
import re

from django.utils.functional import cached_property
from django.utils.lru_cache import lru_cache


PATH_MAPPING = (
    (".", "\."),
    ("<lang>", "(?P<lang>[\w\-\.]*)"),
    ("<filename>", "(?P<filename>[\w\-\.]*)"),
    ("/<directory_path>/", "/<directory_path>"),
    ("<directory_path>", "(?P<directory_path>[\w\/\-]*?)"))


class TranslationFileFinder(object):

    path_mapping = PATH_MAPPING

    def __init__(self, translation_path, ext="po", template_ext=["pot"]):
        self.translation_path = translation_path
        self.ext = ext
        self.template_ext = template_ext
        self.validate_path()
        self.regex = re.compile(self._parse_path())

    @cached_property
    def file_root(self):
        file_root = self.translation_path.split("<")[0]
        if not file_root.endswith("/"):
            file_root = "/".join(file_root.split("/")[:-1])
        return file_root.rstrip("/")

    def find(self):
        # print("Walking the FS: %s" % self.file_root)
        for root, dirs, files in os.walk(self.file_root):
            for filename in files:
                file_path = os.path.join(root, filename)
                match = self.match(file_path)
                if match:
                    matched = match.groupdict()
                    matched["directory_path"] = (
                        matched.get("directory_path", "").strip("/"))
                    if not matched.get("filename"):
                        matched["filename"] = os.path.splitext(
                            os.path.basename(filename))[0]
                    if matched["ext"]:
                        yield file_path, matched

    @lru_cache(maxsize=None)
    def match(self, file_path):
        return self.regex.match(file_path)

    @lru_cache(maxsize=None)
    def reverse_match(self, lang, filename, ext=None, directory_path=None):
        if ext is None:
            ext = self.ext
        ext = ext.strip(".")
        path = self.translation_path
        path = os.path.splitext(path)
        path = "%s.%s" % (path[0], ext)

        matching = not (
            directory_path and "<directory_path>" not in path)
        if not matching:
            return

        path = (path.replace("<lang>",
                             lang)
                    .replace("<filename>",
                             filename))
        if "<directory_path>" in path:
            if directory_path and directory_path.strip("/"):
                path = path.replace(
                    "<directory_path>", "/%s/" % directory_path.strip("/"))
            else:
                path = path.replace("<directory_path>", "")
        local_path = path.replace(self.file_root, "")
        if "//" in local_path:
            path = os.path.join(
                self.file_root,
                local_path.replace("//", "/").lstrip("/"))
        return path

    def validate_path(self):
        path = self.translation_path
        links_to_parent = (
            path == ".."
            or path.startswith("../")
            or "/../" in path
            or path.endswith("/.."))

        if links_to_parent:
            raise ValueError(
                "Translation path should not contain '..'")

        if "<lang>" not in path:
            raise ValueError(
                "Translation path must contain a <lang> pattern to match.")

        # TODO: test for correct file extension

        stripped_path = (path.replace("<lang>", "")
                             .replace("<directory_path>", "")
                             .replace("<filename>", ""))

        if "<" in stripped_path or ">" in stripped_path:
            raise ValueError(
                "Only <lang>, <directory_path> and <filename> are valid "
                "patterns to match in the translation path")

        if re.search("[^\w\/\-\.]+", stripped_path):
            raise ValueError(
                "Translation paths can only contain alpha-numeric characters, "
                "_ or -: '%s'" % path)

    def _ext_re(self):
        return (
            r".(?P<ext>(%s))"
            % "|".join(
                ("%s$" % x)
                for x in [self.ext] + self.template_ext))

    def _parse_path(self):
        path = self.translation_path
        for k, v in self.path_mapping:
            path = path.replace(k, v)
        return "%s%s$" % (
            os.path.splitext(path)[0],
            self._ext_re())
