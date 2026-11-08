# -*- coding: utf-8 -*-
"""P0-1 回归：配置树白名单必须递归、拒绝 __jsExpr、配置目录与内核源不得越仓。

背景（2026-11-08 深度审核）：cordis 的 `interpolate()` 对 `__jsExpr` 执行裸 eval，
`Group` 的 `config` 是嵌套 entry 列表且递归 importlib.import_module —— 只校验顶层
`name` 时，一份 yml 即可执行任意 Python 代码。本文件把这两条链钉成回归用例。
"""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

import yaml

from kernel import _cordis_locate, tree


class ConfigTreeSecurityTests(unittest.TestCase):

    def test_real_config_passes(self):
        path = tree.config_path(tree.ALLIN_CONFIG)
        with open(path, encoding='utf-8') as fh:
            data = yaml.safe_load(fh)
        tree._resolve_service_names(data, path)
        tree._validate_entry_names(data, path)  # 不抛即通过

    def test_nested_group_entry_name_is_rejected(self):
        data = [{
            'name': '@cordisjs/plugin-group', 'id': 'g',
            'config': [{'name': 'os', 'id': 'x'}],
        }]
        with self.assertRaises(ValueError):
            tree._validate_entry_names(data, '<test>')

    def test_nested_group_with_allowed_name_passes(self):
        data = [{
            'name': '@cordisjs/plugin-group', 'id': 'g',
            'config': [{'name': '_allinsrv.docs', 'id': 'x'}],
        }]
        tree._validate_entry_names(data, '<test>')

    def test_js_expr_in_config_rejected(self):
        data = [{
            'name': '_allinsrv.docs', 'id': 'docs',
            'config': {'__jsExpr': "__import__('os').system('echo pwned')"},
        }]
        with self.assertRaises(ValueError):
            tree._validate_entry_names(data, '<test>')

    def test_js_expr_nested_in_list_rejected(self):
        data = [{
            'name': '_allinsrv.docs', 'id': 'docs',
            'config': {'items': [{'__jsExpr': '1 + 1'}]},
        }]
        with self.assertRaises(ValueError):
            tree._validate_entry_names(data, '<test>')

    def test_js_expr_in_non_config_field_rejected(self):
        data = [{'name': '_allinsrv.docs', 'id': 'docs', 'label': {'__jsExpr': '1 + 1'}}]
        with self.assertRaises(ValueError):
            tree._validate_entry_names(data, '<test>')

    def test_top_level_out_of_whitelist_still_rejected(self):
        with self.assertRaises(ValueError):
            tree._validate_entry_names([{'name': 'os'}], '<test>')

    def test_config_dir_must_stay_inside_repo(self):
        with mock.patch.dict(os.environ, {'ALLIN_CONFIGS': tempfile.gettempdir()}):
            with self.assertRaises(RuntimeError):
                tree._safe_config_dir()

    def test_config_dir_accepts_in_repo_dir(self):
        inside = os.path.join(tree.ROOT, 'kernel')
        with mock.patch.dict(os.environ, {'ALLIN_CONFIGS': inside}):
            self.assertEqual(
                os.path.realpath(tree._safe_config_dir()), os.path.realpath(inside)
            )

    def test_external_cordis_src_rejected_without_optin(self):
        with mock.patch.dict(os.environ, {'ALLIN_ALLOW_EXTERNAL_CORDIS': ''}):
            self.assertFalse(_cordis_locate._external_allowed(tempfile.gettempdir()))
            self.assertTrue(_cordis_locate._external_allowed(_cordis_locate.vendor_dir()))

    def test_external_cordis_src_allowed_with_optin(self):
        with mock.patch.dict(os.environ, {'ALLIN_ALLOW_EXTERNAL_CORDIS': '1'}):
            self.assertTrue(_cordis_locate._external_allowed(tempfile.gettempdir()))


if __name__ == '__main__':
    unittest.main()
