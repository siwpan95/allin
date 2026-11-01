'use strict';

/** 公开资源：/media/<asset_key>，字节全部来自数据库解密，磁盘上没有对应的原图。 */

const express = require('express');
const delivery = require('../services/assetDelivery');

const router = express.Router();

router.get('/:key', (req, res) => {
  delivery.sendAsset({ req, res, assetKey: req.params.key, allow: ['public'] });
});

router.head('/:key', (req, res) => {
  delivery.sendAsset({ req, res, assetKey: req.params.key, allow: ['public'] });
});

module.exports = router;
