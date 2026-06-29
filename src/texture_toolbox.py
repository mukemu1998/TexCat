#!/usr/bin/env python3
"""Browser-based texture toolbox for game texture production."""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable

warnings.filterwarnings("ignore", message="'cgi' is deprecated.*", category=DeprecationWarning)
try:
    import cgi
except ModuleNotFoundError:
    import form_compat as cgi

import numpy as np
from PIL import Image, ImageFilter, ImageOps

import texture_resizer as core


IMAGE_EXTENSIONS = core.IMAGE_EXTENSIONS
OUTPUT_FORMATS = ("psd", "png", "tga", "tif", "tiff", "jpg", "jpeg", "dds", "webp", "bmp")
APP_VERSION = "v1.02-dev"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_ROOT = app_root()
ASSETS_DIR = APP_ROOT / "assets"
DEFAULT_OUTPUT_DIR = APP_ROOT / "output"
UPLOAD_ROOT = APP_ROOT / ".texture_toolbox_uploads"


def ensure_default_dirs() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def clear_default_output_dir() -> int:
    ensure_default_dirs()
    output_root = DEFAULT_OUTPUT_DIR.resolve()
    app_root_path = APP_ROOT.resolve()
    if output_root.name != "output" or app_root_path not in output_root.parents:
        raise ValueError(f"拒绝清空非默认输出目录：{output_root}")
    removed = 0
    for child in output_root.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed += 1
    return removed


TOOLBOX_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TexCat贴图工具箱</title>
<link rel="icon" type="image/png" href="/assets/TexCat.png">
<style>
* { box-sizing: border-box; }
:root {
  --bg: #15181d;
  --panel: #20242b;
  --panel-soft: #262b33;
  --text: #eef2f7;
  --muted: #a8b0bd;
  --base-border: #3a414d;
  --border: #633836;
  --control: #171b21;
  --control-disabled: #2c323b;
  --primary: #ff938e;
  --primary-text: #25100f;
  --notice-bg: #332a18;
  --notice-border: #a67c2d;
  --notice-text: #ffe4a8;
  --hover-danger: #ff8f82;
  --shadow: rgba(0, 0, 0, .38);
  --radius: 30px;
  --radius-control: 999px;
  --radius-limited: 18px;
  --log-width: 300px;
  --layout-gap: 24px;
  --main-max: 1120px;
  --main-min: 760px;
  --checker-a: #242a33;
  --checker-b: #303744;
}
body.tone-dark {
  --bg: #15181d;
  --panel: #20242b;
  --panel-soft: #262b33;
  --text: #eef2f7;
  --muted: #a8b0bd;
  --base-border: #3a414d;
  --border: #3a414d;
  --control: #171b21;
  --control-disabled: #2c323b;
  --notice-bg: #332a18;
  --notice-border: #a67c2d;
  --notice-text: #ffe4a8;
  --hover-danger: #ff8f82;
  --shadow: rgba(0, 0, 0, .38);
  --checker-a: #242a33;
  --checker-b: #303744;
}
body.tone-light {
  --bg: #f3f5f7;
  --panel: #ffffff;
  --panel-soft: #fbfcfd;
  --text: #1f2430;
  --muted: #697386;
  --base-border: #d8dde6;
  --border: #d8dde6;
  --control: #ffffff;
  --control-disabled: #eef1f5;
  --notice-bg: #fff7df;
  --notice-border: #f0c76f;
  --notice-text: #60430d;
  --hover-danger: #c0392b;
  --shadow: rgba(31, 36, 48, .16);
  --checker-a: #dbe2ec;
  --checker-b: #f3f6fa;
}
body.scheme-pink { --primary: #e86f9d; --primary-text: #ffffff; --scheme-border: #efcbd7; }
body.scheme-green { --primary: #57bf8d; --primary-text: #ffffff; --scheme-border: #bfebd2; }
body.scheme-red { --primary: #ee7774; --primary-text: #ffffff; --scheme-border: #f2c5c3; }
body.scheme-yellow { --primary: #d9a928; --primary-text: #1b1303; --scheme-border: #f0df9f; }
body.scheme-orange { --primary: #f28c4b; --primary-text: #ffffff; --scheme-border: #f0c9a8; }
body.scheme-blue { --primary: #65a7e8; --primary-text: #07111f; --scheme-border: #bfd9f2; }
body.scheme-cyan { --primary: #42bfd0; --primary-text: #06191d; --scheme-border: #b7e8ee; }
body.scheme-purple { --primary: #a989e8; --primary-text: #ffffff; --scheme-border: #d9c8f2; }
body.tone-dark.scheme-pink { --primary: #ff9abc; --primary-text: #231119; --scheme-border: #613445; }
body.tone-dark.scheme-green { --primary: #7bd8a8; --primary-text: #06180f; --scheme-border: #2f5b45; }
body.tone-dark.scheme-red { --primary: #ff938e; --primary-text: #25100f; --scheme-border: #633836; }
body.tone-dark.scheme-yellow { --primary: #f1cd5c; --primary-text: #201800; --scheme-border: #675a2b; }
body.tone-dark.scheme-orange { --primary: #ffb26f; --primary-text: #211206; --scheme-border: #6a4428; }
body.tone-dark.scheme-blue { --primary: #8bc3ff; --primary-text: #061423; --scheme-border: #345472; }
body.tone-dark.scheme-cyan { --primary: #65d6e3; --primary-text: #04191c; --scheme-border: #2e5960; }
body.tone-dark.scheme-purple { --primary: #c4a6ff; --primary-text: #160e24; --scheme-border: #4c3d67; }
body.scheme-pink, body.scheme-green, body.scheme-red, body.scheme-yellow,
body.scheme-orange, body.scheme-blue, body.scheme-cyan, body.scheme-purple {
  --border: color-mix(in srgb, var(--scheme-border) 45%, var(--base-border));
}
body.radius-compact {
  --radius: 6px;
  --radius-control: 5px;
  --radius-limited: 5px;
}
body.radius-round {
  --radius: 30px;
  --radius-control: 999px;
  --radius-limited: 18px;
}
body {
  margin: 0;
  font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
  color: var(--text);
  background: var(--bg);
}
main {
  width: min(var(--main-max), calc(100vw - var(--log-width) - var(--layout-gap) - 58px));
  max-width: var(--main-max);
  margin: 0 auto 0 max(calc(var(--log-width) + var(--layout-gap) + 18px), calc((100vw - var(--main-max)) / 2));
  padding: 22px 0 92px;
}
body { padding-top: 58px; }
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
  margin-bottom: 16px;
}
h1 { margin: 0 0 8px; font-size: 26px; font-weight: 650; letter-spacing: 0; }
.app-title { display: inline-flex; align-items: center; gap: 10px; }
.app-icon { width: 36px; height: 36px; object-fit: contain; flex: 0 0 36px; }
.title-block { min-width: 260px; }
.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 14px;
}
#drop {
  min-height: 190px;
  border: 2px dashed var(--muted);
  background: var(--panel-soft);
  display: grid;
  place-items: center;
  text-align: center;
}
#drop.active { border-color: var(--primary); background: var(--panel-soft); }
#drop strong { display: block; font-size: 20px; margin-bottom: 8px; }
.module-title {
  text-align: center;
  font-size: 16px;
  font-weight: 650;
  margin: 0 0 12px;
}
.tabs {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  padding-bottom: 14px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--border);
}
.tab {
  height: 34px;
  border: 1px solid var(--border);
  background: var(--control);
  color: var(--text);
  border-radius: var(--radius-control);
  padding: 0 12px;
}
.tab.active { border-color: var(--primary); background: var(--primary); color: var(--primary-text); }
.tool { display: none; }
.tool.active { display: block; }
.mode-switch {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin: 0 0 14px;
}
.mode-button {
  min-width: 148px;
  border-color: var(--border);
  background: var(--control);
  color: var(--text);
}
.mode-button.active {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--primary-text);
}
.mode-view[hidden] { display: none; }
.workflow-shell { padding: 18px; }
.workflow-badge {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 12px;
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--primary) 18%, var(--panel-soft));
  color: var(--text);
  font-size: 13px;
  white-space: nowrap;
}
.workflow-grid {
  display: grid;
  grid-template-columns: minmax(190px, .9fr) minmax(280px, 1.1fr) minmax(260px, 1fr);
  gap: 18px;
  margin-top: 16px;
}
.workflow-column {
  min-width: 0;
  padding: 0 12px;
  border-left: 1px solid var(--border);
}
.workflow-column:first-child { border-left: 0; padding-left: 0; }
.workflow-column-title {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 650;
}
.workflow-list {
  display: grid;
  gap: 0;
  border-top: 1px solid var(--border);
}
.workflow-row {
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
  min-width: 0;
}
.workflow-row strong { display: block; margin-bottom: 4px; }
.workflow-row.disabled { opacity: .68; }
.workflow-row-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workflow-step-number {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  margin-right: 8px;
  border-radius: 50%;
  background: var(--primary);
  color: var(--primary-text);
  font-size: 12px;
  font-weight: 700;
}
.workflow-empty {
  padding: 14px 0;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  color: var(--muted);
}
.workflow-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}
.workflow-step-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}
.workflow-step-toolbar select { min-width: 190px; }
.workflow-step-card {
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}
.workflow-step-card.active {
  margin: 0 -10px;
  padding: 12px 10px;
  border: 1px solid var(--primary);
  border-radius: var(--radius-limited);
  background: color-mix(in srgb, var(--primary) 12%, var(--panel));
}
.workflow-step-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}
.workflow-step-title {
  min-width: 0;
  font-weight: 650;
}
.workflow-step-controls {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}
.workflow-step-controls button {
  height: 28px;
  min-width: 30px;
  padding: 0 8px;
  font-size: 12px;
}
.workflow-detail {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}
.workflow-detail-body {
  display: grid;
  gap: 12px;
  margin-top: 10px;
}
.workflow-detail-note {
  color: var(--muted);
  line-height: 1.5;
}
.workflow-param-card {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-limited);
  background: color-mix(in srgb, var(--panel) 92%, var(--bg));
}
.workflow-param-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}
.workflow-param-grid label,
.workflow-size-options label {
  min-width: 0;
}
.workflow-size-options {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.workflow-param-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.workflow-param-list {
  display: grid;
  gap: 6px;
}
.workflow-param-list div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}
.workflow-param-list span:first-child { color: var(--muted); }
.workflow-json-status {
  min-height: 20px;
  margin-top: 10px;
}
.workflow-summary {
  display: grid;
  gap: 8px;
  margin: 10px 0 0;
}
.workflow-summary div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}
.workflow-summary span:first-child { color: var(--muted); }
.workflow-preview-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 14px 0 8px;
}
.workflow-preview-table {
  max-height: 260px;
}
.workflow-preview-table .preview-row {
  grid-template-columns: minmax(150px, 1fr) minmax(170px, 1fr) minmax(90px, .5fr) minmax(100px, .6fr) minmax(220px, 1.4fr);
}
@media (max-width: 980px) {
  .workflow-grid { grid-template-columns: 1fr; }
  .workflow-column { border-left: 0; border-top: 1px solid var(--border); padding: 14px 0 0; }
  .workflow-column:first-child { border-top: 0; padding-top: 0; }
}
.row { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; margin: 10px 0; }
label { display: inline-flex; align-items: center; gap: 6px; }
input[type="text"], input[type="number"], select {
  height: 34px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--control);
  color: var(--text);
  padding: 0 10px;
  min-width: 160px;
}
input.path { flex: 1; min-width: 360px; }
input:disabled, select:disabled { background: var(--control-disabled); color: var(--muted); }
.row-title { min-width: 72px; font-weight: 650; }
button {
  height: 36px;
  border: 1px solid var(--primary);
  background: var(--primary);
  color: var(--primary-text);
  border-radius: var(--radius-control);
  padding: 0 14px;
  cursor: pointer;
}
button.secondary { border-color: var(--border); background: var(--control); color: var(--text); }
button:disabled { opacity: .55; cursor: not-allowed; }
.power-exit {
  position: fixed;
  left: 18px;
  top: 14px;
  z-index: 10;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border-color: var(--border);
  background: var(--control);
  color: var(--text);
  padding: 0;
  font-size: 25px;
  line-height: 1;
  display: grid;
  place-items: center;
  box-shadow: 0 6px 18px var(--shadow);
}
.power-exit:hover {
  border-color: var(--hover-danger);
  color: var(--hover-danger);
  background: var(--panel-soft);
}
.personalize-button {
  position: fixed;
  left: 18px;
  top: 64px;
  z-index: 10;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border-color: var(--border);
  background: var(--control);
  color: var(--text);
  padding: 0;
  font-size: 22px;
  display: grid;
  place-items: center;
  line-height: 1;
  box-shadow: 0 6px 18px var(--shadow);
  font-family: "Segoe UI Symbol", "Segoe UI", "Microsoft YaHei", sans-serif;
}
.personalize-button:hover,
.personalize-button.active {
  border-color: var(--hover-danger);
  color: var(--hover-danger);
  background: var(--panel-soft);
}
.settings-panel {
  position: fixed;
  left: 70px;
  top: 64px;
  z-index: 12;
  width: min(360px, calc(100vw - 90px));
  display: none;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 12px 30px var(--shadow);
  padding: 14px;
}
.settings-panel.open { display: block; }
.settings-panel label { width: 100%; justify-content: space-between; margin: 8px 0; }
.settings-panel input[type="range"] {
  width: min(190px, 48vw);
  min-width: 120px;
  accent-color: var(--primary);
}
#files, #log {
  width: 100%;
  min-height: 116px;
  max-height: 240px;
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--panel);
  padding: 14px 28px;
  font-family: Consolas, "Microsoft YaHei", monospace;
  font-size: 13px;
  line-height: 1.55;
  text-align: center;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
#log { border-radius: var(--radius-limited); }
#memo {
  width: 100%;
  min-height: calc(20 * 1.55em + 30px);
  height: calc(20 * 1.55em + 30px);
  max-height: calc(20 * 1.55em + 30px);
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-limited);
  background: var(--panel);
  color: var(--text);
  padding: 14px 18px;
  font-family: Consolas, "Microsoft YaHei", monospace;
  font-size: 13px;
  line-height: 1.55;
  resize: vertical;
}
#memo::placeholder { color: var(--muted); }
.files-panel > .muted { text-align: center; margin-bottom: 8px; }
.files-panel .section-head {
  justify-content: center;
  flex-direction: column;
  align-items: center;
}
.files-panel #files {
  display: grid;
  place-items: center;
}
.floating-sidebar {
  position: fixed;
  left: 18px;
  top: 116px;
  z-index: 8;
  width: var(--log-width);
  height: min(680px, calc(100vh - 134px));
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.floating-memo,
.floating-log { margin: 0; }
.floating-memo { flex: 0 0 auto; }
.floating-memo .section-head,
.floating-log .section-head { justify-content: center; }
.floating-log #log {
  flex: 1;
  min-height: 0;
  max-height: none;
}
.floating-log {
  flex: 1;
  min-height: 240px;
  display: flex;
  flex-direction: column;
}
#log.log-idle {
  display: grid;
  place-items: center;
}
#log.log-active {
  display: block;
}
@media (max-width: 1140px) {
  main {
    width: auto;
    max-width: var(--main-max);
    margin: 0 auto;
    padding: 22px 22px 92px;
  }
  .floating-sidebar {
    position: static;
    width: auto;
    height: auto;
    margin: 0 22px 14px;
  }
  .floating-memo,
  .floating-log { margin: 0; }
  .floating-log #log {
    min-height: 160px;
    max-height: 260px;
  }
}
.muted { color: var(--muted); font-size: 13px; }
.notice {
  width: 100%;
  border: 1px solid var(--notice-border);
  background: var(--notice-bg);
  color: var(--notice-text);
  border-radius: var(--radius-control);
  padding: 8px 10px;
  font-size: 13px;
}
.notice.strong {
  border-color: #d67600;
  background: #fff0d2;
  color: #4d2c00;
}
.daily-widget {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: 10px 14px;
  margin-left: auto;
  padding-top: 4px;
  text-align: right;
}
.daily-widget[hidden] { display: none; }
.time-block {
  display: block;
  text-align: center;
  padding: 0;
}
.time-clock { font-size: 22px; font-weight: 700; line-height: 1.1; white-space: nowrap; }
.time-date { color: var(--muted); font-size: 13px; margin-top: 6px; }
.daily-details {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 5px;
  color: var(--text);
  font-size: 13px;
  text-align: left;
}
.daily-line {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  align-items: center;
  white-space: nowrap;
  min-height: 18px;
}
.daily-line[hidden] { display: none; }
#holiday-line { padding-left: 22px; }
.daily-icon { color: var(--primary); font-size: 15px; line-height: 1; }
.pin-icon {
  position: relative;
  width: 14px;
  height: 17px;
  flex: 0 0 14px;
  display: inline-block;
}
.pin-icon::before {
  content: "";
  position: absolute;
  left: 2px;
  top: 1px;
  width: 9px;
  height: 9px;
  border: 2px solid var(--primary);
  border-radius: 50% 50% 50% 0;
  transform: rotate(-45deg);
}
.pin-icon::after {
  content: "";
  position: absolute;
  left: 6px;
  top: 5px;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--primary);
}
@media (max-width: 760px) {
  .app-header { display: block; }
  .daily-widget { justify-content: flex-start; text-align: left; margin-top: 8px; }
  .daily-details { justify-content: flex-start; }
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}
.mini-button {
  height: 28px;
  border-color: var(--border);
  background: var(--control);
  color: var(--text);
  padding: 0 10px;
  font-size: 12px;
}
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.channel-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; }
.channel-grid.single { grid-template-columns: 1fr; }
.channel-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-limited);
  padding: 10px;
  background: var(--panel-soft);
  overflow: hidden;
  min-width: 0;
  overflow-wrap: anywhere;
}
.channel-card strong { display: block; margin-bottom: 8px; }
.channel-card label { display: flex; flex-wrap: wrap; margin: 6px 0; min-width: 0; }
.channel-card select, .channel-card input[type="text"] { width: 100%; min-width: 0; }
.merge-card-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px;
  gap: 10px;
  align-items: start;
}
@media (max-width: 1300px) {
  .merge-card-layout {
    grid-template-columns: 1fr;
  }
  .merge-card-layout .inline-preview {
    width: min(180px, 100%);
    justify-self: center;
  }
}
.inline-preview {
  border: 1px solid var(--border);
  border-radius: 0;
  overflow: hidden;
  background-color: var(--checker-b);
  background-image:
    linear-gradient(45deg, var(--checker-a) 25%, transparent 25%),
    linear-gradient(-45deg, var(--checker-a) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, var(--checker-a) 75%),
    linear-gradient(-45deg, transparent 75%, var(--checker-a) 75%);
  background-size: 32px 32px;
  background-position: 0 0, 0 16px, 16px -16px, -16px 0;
}
.inline-preview img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: contain;
  display: block;
  border-radius: 0;
  background: transparent;
}
.inline-preview img.preview-empty,
.compare-stage img.preview-empty {
  visibility: hidden;
}
.inline-preview span {
  display: block;
  padding: 6px;
  font-size: 12px;
  color: var(--muted);
}
.channel-preview {
  display: none;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  padding: 12px 0;
  margin: 12px 0;
}
.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
  margin-top: 10px;
}
.rename-preview {
  border: 1px solid var(--border);
  border-radius: var(--radius-limited);
  padding: 10px;
  background: var(--panel-soft);
  margin-top: 10px;
  text-align: center;
}
.rename-preview .section-head {
  justify-content: center;
  text-align: center;
  flex-wrap: wrap;
}
.preview-table {
  width: 100%;
  min-height: 48px;
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-limited);
  background: var(--panel);
  text-align: center;
}
.preview-row {
  display: grid;
  grid-template-columns: minmax(180px, 1.2fr) minmax(180px, 1.2fr) minmax(100px, .6fr) minmax(90px, .4fr);
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  align-items: center;
  font-size: 13px;
  text-align: center;
  overflow-wrap: anywhere;
}
.preview-row:last-child { border-bottom: 0; }
.preview-row.header { font-weight: 650; color: var(--muted); background: var(--panel-soft); }
.preview-row.conflict { color: var(--hover-danger); }
.preview-tile {
  border: 1px solid var(--border);
  border-radius: 0;
  background-color: var(--checker-b);
  background-image:
    linear-gradient(45deg, var(--checker-a) 25%, transparent 25%),
    linear-gradient(-45deg, var(--checker-a) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, var(--checker-a) 75%),
    linear-gradient(-45deg, transparent 75%, var(--checker-a) 75%);
  background-size: 32px 32px;
  background-position: 0 0, 0 16px, 16px -16px, -16px 0;
  overflow: hidden;
}
.preview-tile img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: contain;
  display: block;
  border-radius: 0;
  background: transparent;
}
.preview-caption {
  padding: 8px;
  font-size: 12px;
  color: var(--text);
}
.preview-caption strong { display: block; margin-bottom: 3px; }
.compare-wrap {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 0;
  overflow: hidden;
  background-color: var(--checker-b);
  background-image:
    linear-gradient(45deg, var(--checker-a) 25%, transparent 25%),
    linear-gradient(-45deg, var(--checker-a) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, var(--checker-a) 75%),
    linear-gradient(-45deg, transparent 75%, var(--checker-a) 75%);
  background-size: 32px 32px;
  background-position: 0 0, 0 16px, 16px -16px, -16px 0;
  margin-top: 10px;
}
.compare-stage {
  position: relative;
  width: 100%;
  min-height: 220px;
  user-select: none;
  touch-action: none;
}
.compare-stage img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 0;
}
.compare-after {
  clip-path: inset(0 0 0 50%);
}
.compare-divider {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 3px;
  background: #fff;
  box-shadow: 0 0 0 1px rgba(0,0,0,.35);
  cursor: ew-resize;
}
.compare-divider::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  width: 24px;
  height: 44px;
  border-radius: 14px;
  border: 1px solid rgba(0,0,0,.35);
  background: rgba(255,255,255,.92);
  transform: translate(-50%, -50%);
}
.compare-badge {
  position: absolute;
  top: 8px;
  padding: 4px 8px;
  border-radius: 5px;
  background: rgba(0,0,0,.62);
  color: #fff;
  font-size: 12px;
}
.compare-badge.left { left: 8px; }
.compare-badge.right { right: 8px; }
.step-list { display: grid; gap: 10px; }
.rename-step-card,
.crop-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-limited);
  padding: 12px;
  background: var(--panel-soft);
  overflow: hidden;
}
.rename-step-card .section-head,
.crop-card .section-head { margin-bottom: 10px; }
.rename-step-card label { flex-wrap: wrap; }
.step-fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
.step-fields label { width: 100%; }
.step-fields input,
.step-fields select { width: 100%; min-width: 0; }
.round-icon-button {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  padding: 0;
  display: inline-grid;
  place-items: center;
  font-size: 22px;
}
.crop-toolbar,
.crop-stage-actions { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.crop-stage-actions { margin-top: 12px; }
.crop-stage {
  width: min(720px, 100%);
  min-height: 280px;
  margin-top: 12px;
  border: 1px solid var(--border);
  background-color: var(--checker-b);
  background-image:
    linear-gradient(45deg, var(--checker-a) 25%, transparent 25%),
    linear-gradient(-45deg, var(--checker-a) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, var(--checker-a) 75%),
    linear-gradient(-45deg, transparent 75%, var(--checker-a) 75%);
  background-size: 32px 32px;
  background-position: 0 0, 0 16px, 16px -16px, -16px 0;
  display: grid;
  place-items: center;
  overflow: hidden;
}
.crop-stage img {
  width: 100%;
  max-height: 520px;
  object-fit: contain;
  display: block;
  border-radius: 0;
}
.crop-cards { display: grid; gap: 10px; margin-top: 12px; }
.crop-card-body {
  display: grid;
  grid-template-columns: 104px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
}
.template-note {
  width: 100%;
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--muted);
}
.crop-thumb {
  width: 104px;
  aspect-ratio: 1;
  object-fit: contain;
  border-radius: 0;
  border: 1px solid var(--border);
  background-color: var(--checker-b);
  background-image:
    linear-gradient(45deg, var(--checker-a) 25%, transparent 25%),
    linear-gradient(-45deg, var(--checker-a) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, var(--checker-a) 75%),
    linear-gradient(-45deg, transparent 75%, var(--checker-a) 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0;
  cursor: zoom-in;
}
.crop-overlay {
  position: fixed;
  inset: 0;
  z-index: 30;
  display: none;
  background: rgba(0,0,0,.86);
  place-items: center;
  padding: 26px;
}
.crop-overlay.open { display: grid; }
.crop-editor {
  position: relative;
  width: min(94vw, 1400px);
  height: min(88vh, 980px);
  overflow: hidden;
  border: 1px solid rgba(255,255,255,.16);
  background-color: #15181d;
  background-image:
    linear-gradient(45deg, rgba(255,255,255,.06) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(255,255,255,.06) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(255,255,255,.06) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(255,255,255,.06) 75%);
  background-size: 32px 32px;
  background-position: 0 0, 0 16px, 16px -16px, -16px 0;
  cursor: crosshair;
  user-select: none;
  touch-action: none;
}
.crop-editor img {
  position: absolute;
  left: 0;
  top: 0;
  max-width: none;
  max-height: none;
  object-fit: fill;
  border-radius: 0;
  touch-action: none;
  transform-origin: 0 0;
  -webkit-user-drag: none;
  user-select: none;
}
.crop-editor.pan-mode,
.crop-editor.space-pan {
  cursor: grab;
}
.crop-editor.panning {
  cursor: grabbing;
}
.crop-view-controls {
  position: absolute;
  left: 50%;
  top: 12px;
  z-index: 6;
  transform: translateX(-50%);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px;
  border: 1px solid rgba(255,255,255,.2);
  border-radius: var(--radius-limited);
  background: rgba(0,0,0,.62);
  color: #fff;
  box-shadow: 0 10px 24px rgba(0,0,0,.28);
}
.crop-view-controls button {
  min-width: 38px;
  height: 32px;
  padding: 0 10px;
  border-color: rgba(255,255,255,.28);
  background: rgba(255,255,255,.12);
  color: #fff;
}
.crop-view-controls button:hover,
.crop-view-controls button.active {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--primary-text);
}
.crop-view-status {
  min-width: 52px;
  color: #fff;
  text-align: center;
  font-size: 12px;
}
.crop-hint {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 1;
  pointer-events: none;
  padding: 12px 18px;
  border: 1px solid color-mix(in srgb, var(--primary) 45%, rgba(255,255,255,.24));
  border-radius: var(--radius-limited);
  background: rgba(0,0,0,.58);
  color: #fff;
  font-size: 15px;
  text-align: center;
  white-space: nowrap;
  box-shadow: 0 10px 24px rgba(0,0,0,.32);
}
.crop-box {
  position: absolute;
  border: 2px solid var(--primary);
  background: color-mix(in srgb, var(--primary) 22%, transparent);
  display: none;
  z-index: 2;
  pointer-events: auto;
  box-sizing: border-box;
  touch-action: none;
  cursor: move;
}
.crop-actions {
  position: absolute;
  display: none;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: min(720px, calc(100vw - 48px));
  transform: translateX(-50%);
  z-index: 5;
}
.crop-action-options {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid rgba(255,255,255,.22);
  border-radius: var(--radius-limited);
  background: rgba(0,0,0,.62);
  color: #fff;
  box-shadow: 0 10px 24px rgba(0,0,0,.28);
}
.crop-action-options label { color: #fff; }
.crop-pixels {
  display: none;
  flex-wrap: wrap;
  gap: 6px;
}
.crop-pixels input {
  width: 78px;
  min-width: 72px;
  height: 30px;
}
.crop-anchor-grid {
  display: grid;
  grid-template-columns: repeat(3, 24px);
  gap: 4px;
  margin-left: 2px;
}
.crop-anchor-grid button {
  width: 24px;
  height: 24px;
  min-width: 0;
  padding: 0;
  border-radius: 50%;
  border-color: rgba(255,255,255,.34);
  background: rgba(255,255,255,.12);
  color: #fff;
  font-size: 12px;
  line-height: 1;
}
.crop-anchor-grid button:hover {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--primary-text);
}
.crop-confirm,
.crop-cancel {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  padding: 0;
  font-size: 22px;
  display: grid;
  place-items: center;
}
.crop-confirm { border-color: #5fd08a; background: #5fd08a; color: #06200f; }
.crop-cancel { border-color: var(--hover-danger); background: var(--hover-danger); color: #230908; }
.crop-zoom {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: none;
  place-items: center;
  padding: 24px;
  background: rgba(0,0,0,.86);
  cursor: zoom-out;
}
.crop-zoom.open { display: grid; }
.crop-zoom img {
  max-width: 92vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 0;
  background-color: var(--checker-b);
  background-image:
    linear-gradient(45deg, var(--checker-a) 25%, transparent 25%),
    linear-gradient(-45deg, var(--checker-a) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, var(--checker-a) 75%),
    linear-gradient(-45deg, transparent 75%, var(--checker-a) 75%);
  background-size: 28px 28px;
  background-position: 0 0, 0 14px, 14px -14px, -14px 0;
}
.run-progress-wrap {
  margin-top: -4px;
  display: grid;
  gap: 8px;
}
.run-progress-wrap[hidden] { display: none; }
.run-progress-wrap progress {
  width: min(520px, 100%);
  height: 16px;
  accent-color: var(--primary);
}
.run-status { min-height: 18px; }
.run-status.ok { color: #6fd692; }
.run-status.warn { color: var(--notice-text); }
.run-status.error { color: var(--hover-danger); }
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 22px;
  background: rgba(0, 0, 0, .46);
}
.modal-backdrop[hidden] { display: none; }
.conflict-modal {
  width: min(560px, 94vw);
  background: var(--panel);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius-limited);
  padding: 18px;
  box-shadow: 0 22px 52px var(--shadow);
}
.conflict-list {
  max-height: 180px;
  overflow: auto;
  margin: 12px 0;
  padding: 10px;
  border: 1px solid var(--base-border);
  border-radius: var(--radius-limited);
  background: var(--control);
  font-family: Consolas, "Microsoft YaHei", monospace;
  font-size: 13px;
  white-space: pre-wrap;
}
.modal-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}
</style>
</head>
<body>
<main>
  <header class="app-header">
    <div class="title-block">
      <h1 class="app-title"><img class="app-icon" src="/assets/TexCat.png" alt="">TexCat贴图工具箱</h1>
      <div class="muted">版本：__APP_VERSION__</div>
    </div>
    <div id="daily-widget" class="daily-widget" hidden>
    <div class="time-block">
      <div id="clock-time" class="time-clock">--:--:--</div>
      <div id="clock-date" class="time-date">----</div>
    </div>
    <div class="daily-details">
      <div id="holiday-line" class="daily-line" hidden><span id="holiday-text"></span></div>
      <div class="daily-line"><span id="weather-icon" class="daily-icon" aria-hidden="true">○</span><span id="weather-text">同步中</span></div>
      <div class="daily-line"><span id="location-icon" class="daily-icon pin-icon" aria-hidden="true"></span><span id="weather-location">同步中</span></div>
    </div>
    </div>
  </header>
  <div class="mode-switch" role="tablist" aria-label="TexCat模式切换">
    <button id="mode-quick" class="mode-button active" type="button" data-mode="quick" role="tab" aria-selected="true">快速工具模式</button>
    <button id="mode-workflow" class="mode-button" type="button" data-mode="workflow" role="tab" aria-selected="false">工作流模式 Beta</button>
  </div>
  <div id="quick-mode-view" class="mode-view active">
  <section id="drop" class="panel">
    <div>
      <strong>把 PSD / PNG / TGA / TIF / JPG / DDS / WEBP / BMP 图片或文件夹拖到这里</strong>
      <span class="muted">支持一次拖入多张图片；Edge / Chrome 支持拖入文件夹递归读取。</span>
      <div style="margin-top:12px"><button id="pick" type="button">批量选择图片</button></div>
      <input id="picker" type="file" multiple hidden accept=".psd,.png,.tga,.tif,.tiff,.jpg,.jpeg,.dds,.webp,.bmp">
    </div>
  </section>

  <section class="panel files-panel">
    <div class="section-head">
      <div class="muted">待处理文件</div>
      <button id="clear" class="mini-button" type="button">清空列表</button>
    </div>
    <div id="files">尚未添加图片。</div>
  </section>

  <section class="panel">
    <div class="module-title">功能模块</div>
    <div class="tabs">
      <button class="tab active" data-tool="resize">图像大小</button>
      <button class="tab" data-tool="convert">格式转换</button>
      <button class="tab" data-tool="compress">高质量压缩</button>
      <button class="tab" data-tool="crop">图片裁切</button>
      <button class="tab" data-tool="normal">法线/黑白图调整</button>
      <button class="tab" data-tool="pbr">PBR辅助转换</button>
      <button class="tab" data-tool="split">通道拆分</button>
      <button class="tab" data-tool="merge">通道合并</button>
      <button class="tab" data-tool="rename">批量重命名</button>
    </div>
    <div class="row">
      <span class="row-title">输入来源</span>
      <label><input type="radio" name="input-mode" value="uploaded" checked>拖入/选择列表</label>
      <label><input type="radio" name="input-mode" value="folder">自定义输入目录</label>
      <input id="input-dir" class="path" type="text" placeholder="例如 D:\Textures\Source">
      <button id="refresh-input" class="secondary" type="button">扫描目录</button>
    </div>
    <div class="row">
      <span class="row-title">输出位置</span>
      <label><input type="radio" name="output-mode" value="default" checked>默认输出文件夹</label>
      <label><input type="radio" name="output-mode" value="source">源文件位置</label>
      <label><input type="radio" name="output-mode" value="ask">导出时弹框选择</label>
      <label><input type="radio" name="output-mode" value="custom">自定义输出目录</label>
      <input id="output" class="path" type="text" value="__OUTPUT_DIR__" data-default="__OUTPUT_DIR__">
      <button id="clear-default-output" class="secondary" type="button">清空默认位置文件</button>
    </div>
    <div class="row">
      <span class="row-title">通道/位深</span>
      <label>输出模式
        <select id="channel-mode">
          <option value="auto">自动/跟随源图</option>
          <option value="rgb24">RGB 24位</option>
          <option value="rgba32">RGBA 32位</option>
          <option value="gray8">灰度 8位</option>
        </select>
      </label>
      <span class="muted">贴近 PS 的图像模式选择；当前统一按 8位/通道写出。</span>
    </div>
    <div id="source-warning" class="notice">提醒：自定义输入目录只读取源图；拖入/选择使用临时缓存，任务完成后自动删除。</div>

    <div id="channel-preview-panel" class="channel-preview">
      <div class="section-head">
        <div>
          <strong>通道预览</strong>
          <div class="muted">查看图片实际通道和各通道灰度预览，方便拆分或打包前判断来源。</div>
        </div>
        <button id="preview-run" class="secondary" type="button">预览通道</button>
      </div>
      <div class="row">
        <label>选择操作对象图片 <select id="preview-file"></select></label>
      </div>
      <div id="preview-info" class="muted">切换到通道拆分或通道合并后，选择一张图片进行预览。</div>
      <div id="preview-grid" class="preview-grid"></div>
    </div>

    <div id="tool-resize" class="tool active">
      <div class="row">
        <span class="row-title">选择导出尺寸</span>
        <label><input type="checkbox" name="size" value="8192">8K</label>
        <label><input type="checkbox" name="size" value="4096">4K</label>
        <label><input type="checkbox" name="size" value="2048">2K</label>
        <label><input type="checkbox" name="size" value="1024">1K</label>
        <label><input type="checkbox" name="size" value="512">512</label>
        <label><input type="checkbox" name="size" value="256">256</label>
        <label>自定义 <input id="resize-custom" type="text" placeholder="1536,768"></label>
        <label><input id="resize-preserve" type="checkbox" checked>锁定比例</label>
      </div>
      <div class="row">
        <label>配置
          <select id="resize-profile">
            <option value="detail">detail - 颜色贴图/细节保留</option>
            <option value="data">data - 法线/遮罩/数据贴图</option>
            <option value="pixel">pixel - 像素风/硬边</option>
          </select>
        </label>
        <label>输出格式
          <select id="resize-format">
            <option value="keep">保持原格式</option>
            <option value="psd">PSD</option>
            <option value="png">PNG</option>
            <option value="tga">TGA</option>
            <option value="tif">TIF</option>
            <option value="jpg">JPG</option>
            <option value="jpeg">JPEG</option>
            <option value="tiff">TIFF</option>
            <option value="dds">DDS</option>
            <option value="webp">WEBP</option>
            <option value="bmp">BMP</option>
          </select>
        </label>
      </div>
      <div class="row">
        <span class="row-title">导出命名</span>
        <label><input id="resize-size-suffix" type="checkbox" checked>添加尺寸后缀</label>
        <span class="muted">勾选后输出示例：原名_1024x1024.png；取消后不添加尺寸后缀。</span>
      </div>
    </div>

    <div id="tool-convert" class="tool">
      <div class="row">
        <label>输出格式
          <select id="convert-format">
            <option value="png">PNG</option>
            <option value="tga">TGA</option>
            <option value="tif">TIF</option>
            <option value="jpg">JPG</option>
            <option value="jpeg">JPEG</option>
            <option value="tiff">TIFF</option>
            <option value="dds">DDS</option>
            <option value="webp">WEBP</option>
            <option value="bmp">BMP</option>
            <option value="psd">PSD</option>
          </select>
        </label>
      </div>
    </div>

    <div id="tool-compress" class="tool">
      <div class="row">
        <label>输出格式
          <select id="compress-format">
            <option value="keep">保持原格式</option>
            <option value="png">PNG</option>
            <option value="jpg">JPG</option>
            <option value="jpeg">JPEG</option>
            <option value="tif">TIF</option>
            <option value="tiff">TIFF</option>
            <option value="tga">TGA</option>
            <option value="webp">WEBP</option>
            <option value="bmp">BMP</option>
            <option value="dds">DDS</option>
            <option value="psd">PSD</option>
          </select>
        </label>
        <label style="min-width:300px;">有损格式质量
          <input id="compress-quality" type="range" min="80" max="100" step="1" value="95" style="flex:1;">
          <strong id="compress-quality-value">95</strong>
        </label>
        <label><input id="compress-lossless" type="checkbox" checked>无损优先</label>
      </div>
      <div class="muted">默认会在文件名后添加 _compressed。PNG/TIF/TGA/WEBP 优先使用无损或可逆压缩；JPG/JPEG 使用 4:4:4 高质量写出。</div>
    </div>

    <div id="tool-crop" class="tool">
      <div class="crop-toolbar">
        <span class="row-title">裁切范围</span>
        <label><input type="radio" name="crop-mode" value="single" checked>单图</label>
        <label><input type="radio" name="crop-mode" value="batch">多图同位置</label>
        <label>显示图片 <select id="crop-source-file"></select></label>
        <label>输出格式
          <select id="crop-format">
            <option value="keep">保持原格式</option>
            <option value="png">PNG</option>
            <option value="tga">TGA</option>
            <option value="tif">TIF</option>
            <option value="jpg">JPG</option>
            <option value="jpeg">JPEG</option>
            <option value="psd">PSD</option>
            <option value="tiff">TIFF</option>
            <option value="dds">DDS</option>
            <option value="webp">WEBP</option>
            <option value="bmp">BMP</option>
          </select>
        </label>
      </div>
      <div id="crop-info" class="muted">默认显示第一张导入图；多图模式只切换顶层显示参考图，执行时会把同一裁切位置批量应用到所有同尺寸贴图；命名模板不含 {name} 时会自动补源图名避免覆盖。</div>
      <div class="crop-stage">
        <img id="crop-preview-img" class="preview-empty" alt="裁切显示图">
      </div>
      <div class="crop-stage-actions">
        <button id="crop-load-preview" class="secondary" type="button">刷新显示</button>
        <button id="crop-add" type="button">添加裁切</button>
      </div>
      <div id="crop-cards" class="crop-cards"></div>
    </div>

    <div id="tool-normal" class="tool">
      <div class="row">
        <label>调整类型
          <select id="strength-kind">
            <option value="normal">法线贴图</option>
            <option value="roughness">黑白 / 粗糙度贴图</option>
          </select>
        </label>
        <label>输出格式
          <select id="normal-format">
            <option value="psd">PSD</option>
            <option value="png">PNG</option>
            <option value="tga">TGA</option>
            <option value="tif">TIF</option>
            <option value="jpg">JPG</option>
            <option value="jpeg">JPEG</option>
            <option value="tiff">TIFF</option>
            <option value="dds">DDS</option>
            <option value="webp">WEBP</option>
            <option value="bmp">BMP</option>
          </select>
        </label>
      </div>
      <div id="normal-options">
        <div class="row">
          <label style="min-width:360px;">法线强度
            <input id="normal-strength" type="range" min="0" max="4" step="0.1" value="1.5" style="flex:1;">
            <strong id="normal-strength-value">1.5</strong>
          </label>
          <label>法线模式
            <select id="normal-mode">
              <option value="opengl">OpenGL 模式</option>
              <option value="directx">DirectX / DX 模式</option>
            </select>
          </label>
        </div>
      </div>
      <div id="roughness-options" style="display:none;">
        <div class="row">
          <label style="min-width:300px;">整体强度
            <input id="roughness-strength" type="range" min="0" max="2" step="0.1" value="1.0" style="flex:1;">
            <strong id="roughness-strength-value">1.0</strong>
          </label>
          <label style="min-width:300px;">灰度对比
            <input id="roughness-contrast" type="range" min="0" max="3" step="0.1" value="1.0" style="flex:1;">
            <strong id="roughness-contrast-value">1.0</strong>
          </label>
          <label style="min-width:300px;">粗糙倾向
            <input id="roughness-bias" type="range" min="-1" max="1" step="0.1" value="0" style="flex:1;">
            <strong id="roughness-bias-value">0.0</strong>
          </label>
        </div>
        <div class="row">
          <label style="min-width:260px;">黑场
            <input id="roughness-black" type="range" min="0" max="0.95" step="0.01" value="0" style="flex:1;">
            <strong id="roughness-black-value">0.00</strong>
          </label>
          <label style="min-width:260px;">白场
            <input id="roughness-white" type="range" min="0.05" max="1" step="0.01" value="1" style="flex:1;">
            <strong id="roughness-white-value">1.00</strong>
          </label>
          <label style="min-width:260px;">中间调
            <input id="roughness-gamma" type="range" min="0.2" max="3" step="0.05" value="1" style="flex:1;">
            <strong id="roughness-gamma-value">1.00</strong>
          </label>
          <label style="min-width:260px;">曲线 S
            <input id="roughness-curve" type="range" min="-1" max="1" step="0.1" value="0" style="flex:1;">
            <strong id="roughness-curve-value">0.0</strong>
          </label>
          <button id="roughness-reset" class="secondary" type="button">重置滑杆</button>
        </div>
        <div class="row">
          <label><input id="roughness-invert" type="checkbox">黑白反相</label>
          <span class="muted">色阶和曲线只作用于黑白/粗糙度贴图，不会应用到法线。</span>
        </div>
      </div>
      <div class="row">
        <label>选择操作对象图片 <select id="normal-preview-file"></select></label>
        <button id="normal-preview-run" class="secondary" type="button">预览强度效果</button>
        <span id="normal-preview-info" class="muted">选择图片后点击预览，左侧为原图，右侧为调整后。</span>
      </div>
      <div class="compare-wrap">
        <div id="normal-compare-stage" class="compare-stage">
          <img id="normal-preview-before" class="preview-empty" alt="原图">
          <img id="normal-preview-after" class="compare-after preview-empty" alt="调整预览">
          <div class="compare-badge left">原图</div>
          <div class="compare-badge right">修改预览</div>
          <div id="normal-compare-divider" class="compare-divider"></div>
        </div>
      </div>
    </div>

    <div id="tool-pbr" class="tool">
      <div class="row">
        <label>输入类型
          <select id="pbr-source-type">
            <option value="color">Photo / Diffuse / Color</option>
            <option value="normal">Normal Map</option>
            <option value="height">Height / Displacement</option>
          </select>
        </label>
        <label>输出目标
          <select id="pbr-mode">
            <option value="normal">Normal</option>
            <option value="derivative">Derivative</option>
            <option value="height">Height</option>
            <option value="displacement">Displacement</option>
            <option value="ao">AO / Occ</option>
            <option value="cavity">Cavity</option>
            <option value="concavity">Concavity</option>
            <option value="convexity">Convexity</option>
            <option value="curvature">Curvature</option>
          </select>
        </label>
      </div>
      <div class="row">
        <label style="min-width:280px;">强度/深度
          <input id="pbr-strength" type="range" min="0" max="8" step="0.1" value="3.0" style="flex:1;">
          <strong id="pbr-strength-value">3.0</strong>
        </label>
        <label style="min-width:260px;">半径
          <input id="pbr-radius" type="range" min="1" max="32" step="1" value="10" style="flex:1;">
          <strong id="pbr-radius-value">10</strong>
        </label>
        <label style="min-width:260px;">细节
          <input id="pbr-detail" type="range" min="0" max="3" step="0.1" value="1.4" style="flex:1;">
          <strong id="pbr-detail-value">1.4</strong>
        </label>
        <label style="min-width:260px;">平滑
          <input id="pbr-smooth" type="range" min="0" max="8" step="0.1" value="0.6" style="flex:1;">
          <strong id="pbr-smooth-value">0.6</strong>
        </label>
        <label style="min-width:280px;">效果叠加
          <input id="pbr-stack" type="range" min="0" max="2" step="0.1" value="1.3" style="flex:1;">
          <strong id="pbr-stack-value">1.3</strong>
        </label>
        <button id="pbr-reset" class="secondary" type="button">重置滑杆</button>
      </div>
      <div class="muted">效果叠加会把大形、中频细节、微细节、AO/Cavity/Curvature 作为制作层叠加到输出里；0 更干净，1.3 为默认高质量生产预设，2 更适合做遮罩和二次叠加素材。</div>
      <div class="row">
        <label>法线模式
          <select id="pbr-normal-mode">
            <option value="opengl">OpenGL 模式</option>
            <option value="directx">DirectX / DX 模式</option>
          </select>
        </label>
        <label><input id="pbr-invert" type="checkbox">反相高度/结果</label>
        <label>输出格式
          <select id="pbr-format">
            <option value="psd">PSD</option>
            <option value="png">PNG</option>
            <option value="tga">TGA</option>
            <option value="tif">TIF</option>
            <option value="jpg">JPG</option>
            <option value="jpeg">JPEG</option>
            <option value="tiff">TIFF</option>
            <option value="dds">DDS</option>
            <option value="webp">WEBP</option>
            <option value="bmp">BMP</option>
          </select>
        </label>
      </div>
      <div class="row">
        <label>选择操作对象图片 <select id="pbr-preview-file"></select></label>
        <button id="pbr-preview-run" class="secondary" type="button">预览PBR辅助图</button>
        <span id="pbr-preview-info" class="muted">该模块生成制作过程辅助图，不作为物理准确贴图推导。</span>
      </div>
      <div class="compare-wrap">
        <div id="pbr-compare-stage" class="compare-stage">
          <img id="pbr-preview-before" class="preview-empty" alt="原图">
          <img id="pbr-preview-after" class="compare-after preview-empty" alt="PBR辅助预览">
          <div class="compare-badge left">原图</div>
          <div class="compare-badge right">辅助预览</div>
          <div id="pbr-compare-divider" class="compare-divider"></div>
        </div>
      </div>
    </div>

    <div id="tool-split" class="tool">
      <div class="row">
        <label>拆分输出
          <select id="split-format">
            <option value="psd">PSD 灰度图</option>
            <option value="png">PNG 灰度图</option>
            <option value="tga">TGA 灰度图</option>
            <option value="tif">TIF 灰度图</option>
            <option value="jpg">JPG 灰度图</option>
            <option value="jpeg">JPEG 灰度图</option>
            <option value="tiff">TIFF 灰度图</option>
            <option value="dds">DDS 灰度图</option>
            <option value="webp">WEBP 灰度图</option>
            <option value="bmp">BMP 灰度图</option>
          </select>
        </label>
      </div>
      <div class="muted">单通道图只会输出灰度；RGB 图默认输出 R/G/B；RGBA 图默认输出 R/G/B/A。可按通道自定义输出名。</div>
      <div class="channel-grid single">
        <div class="channel-card">
          <strong>灰度 / L</strong>
          <div class="merge-card-layout">
            <div>
              <label><input id="split-l-enabled" type="checkbox" checked>单通道图输出</label>
              <label>命名 <input id="split-l-name" type="text" value="{name}_L"></label>
              <div class="template-note">{name}占位符为源图原文件名后缀为可修改内容，例如 {name}_Mask 会输出 原名_Mask。删掉{name}占位符时不会自动补源图名。</div>
            </div>
            <div class="inline-preview"><img id="split-l-preview-img" class="preview-empty" alt="L 预览"><span id="split-l-preview-info">未预览</span></div>
          </div>
        </div>
        <div class="channel-card">
          <strong>R</strong>
          <div class="merge-card-layout">
            <div>
              <label><input id="split-r-enabled" type="checkbox" checked>输出 R</label>
              <label>命名 <input id="split-r-name" type="text" value="{name}_R"></label>
              <div class="template-note">{name}占位符为源图原文件名后缀为可修改内容，例如 {name}_Roughness 会输出 原名_Roughness。删掉{name}占位符时不会自动补源图名。</div>
            </div>
            <div class="inline-preview"><img id="split-r-preview-img" class="preview-empty" alt="R 预览"><span id="split-r-preview-info">未预览</span></div>
          </div>
        </div>
        <div class="channel-card">
          <strong>G</strong>
          <div class="merge-card-layout">
            <div>
              <label><input id="split-g-enabled" type="checkbox" checked>输出 G</label>
              <label>命名 <input id="split-g-name" type="text" value="{name}_G"></label>
              <div class="template-note">{name}占位符为源图原文件名后缀为可修改内容，例如 {name}_Metallic 会输出 原名_Metallic。删掉{name}占位符时不会自动补源图名。</div>
            </div>
            <div class="inline-preview"><img id="split-g-preview-img" class="preview-empty" alt="G 预览"><span id="split-g-preview-info">未预览</span></div>
          </div>
        </div>
        <div class="channel-card">
          <strong>B</strong>
          <div class="merge-card-layout">
            <div>
              <label><input id="split-b-enabled" type="checkbox" checked>输出 B</label>
              <label>命名 <input id="split-b-name" type="text" value="{name}_B"></label>
              <div class="template-note">{name}占位符为源图原文件名后缀为可修改内容，例如 {name}_AO 会输出 原名_AO。删掉{name}占位符时不会自动补源图名。</div>
            </div>
            <div class="inline-preview"><img id="split-b-preview-img" class="preview-empty" alt="B 预览"><span id="split-b-preview-info">未预览</span></div>
          </div>
        </div>
        <div class="channel-card">
          <strong>A</strong>
          <div class="merge-card-layout">
            <div>
              <label><input id="split-a-enabled" type="checkbox" checked>有 Alpha 时输出 A</label>
              <label>命名 <input id="split-a-name" type="text" value="{name}_A"></label>
              <div class="template-note">{name}占位符为源图原文件名后缀为可修改内容，例如 {name}_Alpha 会输出 原名_Alpha。删掉{name}占位符时不会自动补源图名。</div>
            </div>
            <div class="inline-preview"><img id="split-a-preview-img" class="preview-empty" alt="A 预览"><span id="split-a-preview-info">未预览</span></div>
          </div>
        </div>
      </div>
      <div class="muted">命名可用：{name} 原名、{channel} 通道名、{ext} 输出格式。</div>
    </div>

    <div id="tool-merge" class="tool">
      <div class="muted">可选基础图保留原 RGB/RGBA，再用指定文件的指定通道替换目标通道。</div>
      <div class="row">
        <label>基础图 <select id="merge-base"></select></label>
      </div>
      <div class="channel-grid single">
        <div class="channel-card">
          <strong>目标 R</strong>
          <div class="merge-card-layout">
            <div>
              <label>方式 <select id="merge-r-mode"></select></label>
              <label>来源文件 <select id="merge-r-file"></select></label>
              <label>来源通道 <select id="merge-r-channel"></select></label>
            </div>
            <div class="inline-preview"><img id="merge-r-preview-img" class="preview-empty" alt="目标 R 预览"><span id="merge-r-preview-info">未预览</span></div>
          </div>
        </div>
        <div class="channel-card">
          <strong>目标 G</strong>
          <div class="merge-card-layout">
            <div>
              <label>方式 <select id="merge-g-mode"></select></label>
              <label>来源文件 <select id="merge-g-file"></select></label>
              <label>来源通道 <select id="merge-g-channel"></select></label>
            </div>
            <div class="inline-preview"><img id="merge-g-preview-img" class="preview-empty" alt="目标 G 预览"><span id="merge-g-preview-info">未预览</span></div>
          </div>
        </div>
        <div class="channel-card">
          <strong>目标 B</strong>
          <div class="merge-card-layout">
            <div>
              <label>方式 <select id="merge-b-mode"></select></label>
              <label>来源文件 <select id="merge-b-file"></select></label>
              <label>来源通道 <select id="merge-b-channel"></select></label>
            </div>
            <div class="inline-preview"><img id="merge-b-preview-img" class="preview-empty" alt="目标 B 预览"><span id="merge-b-preview-info">未预览</span></div>
          </div>
        </div>
        <div class="channel-card">
          <strong>目标 A</strong>
          <div class="merge-card-layout">
            <div>
              <label>方式 <select id="merge-a-mode"></select></label>
              <label>来源文件 <select id="merge-a-file"></select></label>
              <label>来源通道 <select id="merge-a-channel"></select></label>
            </div>
            <div class="inline-preview"><img id="merge-a-preview-img" class="preview-empty" alt="目标 A 预览"><span id="merge-a-preview-info">未预览</span></div>
          </div>
        </div>
      </div>
      <div class="row">
        <label>输出名 <input id="merge-name" type="text" value="merged_rgba"></label>
        <label>输出格式
          <select id="merge-format">
            <option value="png">PNG</option>
            <option value="tga">TGA</option>
            <option value="tif">TIF</option>
            <option value="jpg">JPG</option>
            <option value="jpeg">JPEG</option>
            <option value="psd">PSD</option>
            <option value="tiff">TIFF</option>
            <option value="dds">DDS</option>
            <option value="webp">WEBP</option>
            <option value="bmp">BMP</option>
          </select>
        </label>
      </div>
      <div class="channel-card">
        <div class="section-head">
          <div>
            <strong>合成图预览</strong>
            <div class="muted">按当前 R/G/B/A 设置生成预览，不写入输出目录。</div>
          </div>
          <button id="merge-preview-run" class="secondary" type="button">手动刷新预览</button>
        </div>
        <div class="inline-preview" style="max-width:360px;"><img id="merge-composite-preview-img" class="preview-empty" alt="合成图预览"><span id="merge-composite-preview-info">未预览</span></div>
      </div>
    </div>

    <div id="tool-rename" class="tool">
      <div class="row">
        <label>输出格式
          <select id="rename-format">
            <option value="keep">保持原格式</option>
            <option value="png">PNG</option>
            <option value="tga">TGA</option>
            <option value="tif">TIF</option>
            <option value="jpg">JPG</option>
            <option value="jpeg">JPEG</option>
            <option value="psd">PSD</option>
            <option value="tiff">TIFF</option>
            <option value="dds">DDS</option>
            <option value="webp">WEBP</option>
            <option value="bmp">BMP</option>
          </select>
        </label>
      </div>
      <div class="muted">基础命名从原文件名开始；步骤会按从上到下顺序叠加，预览始终显示最终结果。</div>
      <div id="rename-steps" class="step-list"></div>
      <div class="row" style="justify-content:center;">
        <button id="rename-add-step" class="round-icon-button secondary" type="button" title="增加步骤">+</button>
      </div>
      <div class="rename-preview">
        <div class="section-head">
          <div>
            <strong>命名预览</strong>
            <div id="rename-preview-info" class="muted">预览会显示所有步骤叠加后的最终命名。</div>
          </div>
          <button id="rename-preview-run" class="secondary" type="button">命名预览</button>
        </div>
        <div class="muted">可用占位：{name} 原名、{ext} 原扩展名、{type} 识别贴图类型。</div>
        <div id="rename-preview-list" class="preview-table">尚未预览。</div>
      </div>
      <template id="rename-step-template">
        <div class="rename-step-card">
          <div class="section-head">
            <strong class="rename-step-title">步骤</strong>
            <button class="mini-button rename-step-delete" type="button">删除步骤</button>
          </div>
          <div class="row">
            <label><input type="radio" class="rename-step-op" value="replace">查找替换</label>
            <label><input type="radio" class="rename-step-op" value="prefix">添加前缀/项目名</label>
            <label><input type="radio" class="rename-step-op" value="suffix">添加后缀</label>
            <label><input type="radio" class="rename-step-op" value="insert">中间插入文本</label>
          </div>
          <div class="step-fields rename-step-fields">
            <label data-field="find">查找 <input class="rename-step-find" type="text"></label>
            <label data-field="replace">替换为 <input class="rename-step-replace" type="text"></label>
            <label data-field="prefix">前缀/项目名 <input class="rename-step-prefix" type="text"></label>
            <label data-field="suffix">后缀 <input class="rename-step-suffix" type="text"></label>
            <label data-field="left">查找左侧文本 <input class="rename-step-left" type="text"></label>
            <label data-field="insert">中间插入文本 <input class="rename-step-insert" type="text"></label>
            <label data-field="right">查找右侧文本 <input class="rename-step-right" type="text"></label>
          </div>
        </div>
      </template>
    </div>

    <div class="row">
      <button id="run" type="button">执行并导出所有选择的贴图</button>
    </div>
    <div id="run-progress-wrap" class="run-progress-wrap" hidden>
      <progress id="run-progress" max="100" value="0"></progress>
      <div id="run-status" class="run-status muted">等待执行。</div>
    </div>
  </section>
  </div>
  <section id="workflow-mode-view" class="mode-view panel workflow-shell" hidden>
    <div class="section-head">
      <div>
        <strong>工作流模式 Beta</strong>
        <div class="muted">第一阶段只搭建界面壳和流程位置，不执行真实处理；快速工具模式保持可用。</div>
      </div>
      <span class="workflow-badge">阶段 3 / 参数接入 Beta</span>
    </div>
    <div class="workflow-grid">
      <div class="workflow-column">
        <div class="workflow-column-title">资源池</div>
        <div id="workflow-resource-summary" class="muted">尚未添加图片。</div>
        <div id="workflow-resource-list" class="workflow-list" aria-live="polite">
          <div class="workflow-empty">拖入或选择图片后，这里会同步显示工作流输入资源。</div>
        </div>
      </div>
      <div class="workflow-column">
        <div class="workflow-column-title">处理步骤</div>
        <div class="workflow-step-toolbar">
          <label>步骤类型
            <select id="workflow-step-type">
              <option value="resize">缩放尺寸</option>
              <option value="export">格式与压缩</option>
              <option value="crop">图片裁切</option>
              <option value="normal">法线/黑白调整</option>
              <option value="split">通道拆分</option>
              <option value="merge">通道合并/打包</option>
              <option value="rename">命名规则</option>
            </select>
          </label>
          <button id="workflow-add-step" type="button">添加步骤</button>
        </div>
        <div id="workflow-step-list" class="workflow-list" aria-live="polite"></div>
        <div class="workflow-actions">
          <button id="workflow-save" class="secondary" type="button">保存工作流 JSON</button>
          <button id="workflow-load" class="secondary" type="button">载入工作流 JSON</button>
          <input id="workflow-load-input" type="file" accept=".json,application/json" hidden>
        </div>
        <div id="workflow-json-status" class="workflow-json-status muted">当前步骤会保存真实参数配置，暂不执行完整工作流处理。</div>
      </div>
      <div class="workflow-column">
        <div class="workflow-column-title">参数与输出摘要</div>
        <div class="muted">选中步骤后这里显示参数设置；输出预览会计算预计文件名、路径和冲突，不写入图片。</div>
        <div id="workflow-detail" class="workflow-detail">
          <strong id="workflow-detail-title">未选中步骤</strong>
          <div id="workflow-detail-body" class="workflow-detail-body">添加或选择一个步骤后，这里会显示该步骤的参数设置。</div>
        </div>
        <div id="workflow-output-summary" class="workflow-summary">
          <div><span>输入资源</span><strong id="workflow-summary-inputs">0</strong></div>
          <div><span>处理步骤</span><strong id="workflow-summary-steps">0</strong></div>
          <div><span>预计输出</span><strong id="workflow-summary-outputs">待接入</strong></div>
          <div><span>命名预览</span><strong id="workflow-summary-naming">待接入</strong></div>
          <div><span>冲突检查</span><strong id="workflow-summary-conflicts">待接入</strong></div>
          <div><span>导出策略</span><strong id="workflow-summary-export">复用全局设置</strong></div>
        </div>
        <div class="workflow-preview-actions">
          <button id="workflow-preview-run" class="secondary" type="button">预览工作流输出</button>
          <span id="workflow-preview-info" class="muted">预览只计算路径、命名和冲突，不会写出图片。</span>
        </div>
        <div id="workflow-preview-list" class="preview-table workflow-preview-table">尚未预览。</div>
        <div class="notice" style="margin-top:14px;">工作流 Beta 暂不写入输出目录，也不会修改源文件。当前阶段只维护步骤结构、参数 JSON 和输出预览。</div>
      </div>
    </div>
  </section>
</main>
<button id="shutdown" class="power-exit" type="button" title="退出工具箱" aria-label="退出工具箱">&#x23FB;</button>
<button id="personalize" class="personalize-button" type="button" title="个性化设置" aria-label="个性化设置">&#9881;</button>
<aside class="floating-sidebar">
  <section class="panel floating-memo">
    <div class="section-head">
      <div class="muted">备忘录</div>
      <button id="clear-memo" class="mini-button" type="button">清空备忘录</button>
    </div>
    <textarea id="memo" rows="20" spellcheck="false" placeholder="输入临时备忘..."></textarea>
  </section>
  <section class="panel floating-log">
    <div class="section-head">
      <div class="muted">日志</div>
      <button id="clear-log" class="mini-button" type="button">清空日志</button>
    </div>
    <div id="log" class="log-idle">工具箱已就绪。</div>
  </section>
</aside>
<div id="settings-panel" class="settings-panel" aria-label="个性化设置">
  <div class="section-head">
    <strong>个性化设置</strong>
    <button id="settings-close" class="mini-button" type="button">关闭</button>
  </div>
  <label>明暗模式
    <select id="tone-select">
      <option value="dark">暗色</option>
      <option value="light">明亮</option>
    </select>
  </label>
  <label>色系
    <select id="scheme-select">
      <option value="red">红</option>
      <option value="orange">橙</option>
      <option value="pink">粉</option>
      <option value="green">绿</option>
      <option value="yellow">黄</option>
      <option value="blue">蓝</option>
      <option value="cyan">青</option>
      <option value="purple">紫</option>
    </select>
  </label>
  <label>界面圆角
    <input id="radius-slider" type="range" min="0" max="1" step="0.01" value="1">
    <strong id="radius-value">1.00</strong>
  </label>
  <div class="row">
    <button id="settings-save" type="button">保存设置</button>
    <button id="settings-reset" class="secondary" type="button">恢复默认</button>
  </div>
  <div id="settings-status" class="muted">设置保存在当前浏览器里。</div>
</div>
<div id="crop-overlay" class="crop-overlay" aria-label="裁切编辑模式">
  <div id="crop-editor" class="crop-editor">
    <div class="crop-view-controls" aria-label="裁切视图控制">
      <button id="crop-view-fit" type="button" title="适配全图">适配</button>
      <button id="crop-view-out" type="button" title="缩小">-</button>
      <button id="crop-view-in" type="button" title="放大">+</button>
      <button id="crop-view-actual" type="button" title="按原图像素查看">1:1</button>
      <button id="crop-view-pan" type="button" title="移动视图" aria-pressed="false">移动</button>
      <span id="crop-view-status" class="crop-view-status">100%</span>
    </div>
    <img id="crop-editor-img" alt="裁切编辑图">
    <div id="crop-hint" class="crop-hint">拖拽图片区域，自由框选裁切范围</div>
    <div id="crop-box" class="crop-box"></div>
    <div id="crop-actions" class="crop-actions">
      <div class="crop-action-options">
        <label><input type="radio" name="crop-shape-mode" value="free" checked>自由框选</label>
        <label><input type="radio" name="crop-shape-mode" value="square">1:1 锁定</label>
        <label><input type="radio" name="crop-shape-mode" value="custom">自定义像素</label>
        <span id="crop-custom-pixels" class="crop-pixels">
          宽 <input id="crop-custom-width" type="number" min="1" step="1" value="512">
          高 <input id="crop-custom-height" type="number" min="1" step="1" value="512">
        </span>
        <span class="muted">九宫格吸附</span>
        <span id="crop-anchor-grid" class="crop-anchor-grid" aria-label="九宫格吸附">
          <button type="button" data-anchor="tl" title="左上吸附">1</button>
          <button type="button" data-anchor="tc" title="上中吸附">2</button>
          <button type="button" data-anchor="tr" title="右上吸附">3</button>
          <button type="button" data-anchor="ml" title="左中吸附">4</button>
          <button type="button" data-anchor="mc" title="中心吸附">5</button>
          <button type="button" data-anchor="mr" title="右中吸附">6</button>
          <button type="button" data-anchor="bl" title="左下吸附">7</button>
          <button type="button" data-anchor="bc" title="下中吸附">8</button>
          <button type="button" data-anchor="br" title="右下吸附">9</button>
        </span>
      </div>
      <button id="crop-confirm" class="crop-confirm" type="button" title="确认裁切">&#10003;</button>
      <button id="crop-cancel" class="crop-cancel" type="button" title="取消裁切">&#10005;</button>
    </div>
  </div>
</div>
<div id="crop-zoom" class="crop-zoom" aria-label="裁切预览放大图">
  <img id="crop-zoom-img" alt="裁切预览放大图">
</div>
<div id="conflict-modal" class="modal-backdrop" hidden>
  <div class="conflict-modal" role="dialog" aria-modal="true" aria-label="同名文件提醒">
    <div class="section-head">
      <strong>目标位置已有同名文件</strong>
    </div>
    <div class="muted">请选择本次导出的处理方式。</div>
    <div id="conflict-list" class="conflict-list"></div>
    <div class="modal-actions">
      <button id="conflict-overwrite" type="button">覆盖</button>
      <button id="conflict-suffix" class="secondary" type="button">整体命名加_TC后缀</button>
      <button id="conflict-cancel" class="secondary" type="button">取消</button>
    </div>
  </div>
</div>
<script>
const allowed = new Set(["psd","png","tga","tif","tiff","jpg","jpeg","dds","webp","bmp"]);
const modeButtons = document.querySelectorAll(".mode-button");
const quickModeView = document.getElementById("quick-mode-view");
const workflowModeView = document.getElementById("workflow-mode-view");
const workflowResourceSummary = document.getElementById("workflow-resource-summary");
const workflowResourceList = document.getElementById("workflow-resource-list");
const workflowOutputSummary = document.getElementById("workflow-output-summary");
const workflowStepType = document.getElementById("workflow-step-type");
const workflowAddStep = document.getElementById("workflow-add-step");
const workflowStepList = document.getElementById("workflow-step-list");
const workflowSave = document.getElementById("workflow-save");
const workflowLoad = document.getElementById("workflow-load");
const workflowLoadInput = document.getElementById("workflow-load-input");
const workflowJsonStatus = document.getElementById("workflow-json-status");
const workflowDetailTitle = document.getElementById("workflow-detail-title");
const workflowDetailBody = document.getElementById("workflow-detail-body");
const workflowSummaryInputs = document.getElementById("workflow-summary-inputs");
const workflowSummarySteps = document.getElementById("workflow-summary-steps");
const workflowSummaryOutputs = document.getElementById("workflow-summary-outputs");
const workflowSummaryNaming = document.getElementById("workflow-summary-naming");
const workflowSummaryConflicts = document.getElementById("workflow-summary-conflicts");
const workflowSummaryExport = document.getElementById("workflow-summary-export");
const workflowPreviewRun = document.getElementById("workflow-preview-run");
const workflowPreviewInfo = document.getElementById("workflow-preview-info");
const workflowPreviewList = document.getElementById("workflow-preview-list");
const drop = document.getElementById("drop");
const picker = document.getElementById("picker");
const filesBox = document.getElementById("files");
const logBox = document.getElementById("log");
const memoBox = document.getElementById("memo");
const runButton = document.getElementById("run");
const runProgressWrap = document.getElementById("run-progress-wrap");
const runProgress = document.getElementById("run-progress");
const runStatus = document.getElementById("run-status");
const conflictModal = document.getElementById("conflict-modal");
const conflictList = document.getElementById("conflict-list");
const dailyWidget = document.getElementById("daily-widget");
const clockTime = document.getElementById("clock-time");
const clockDate = document.getElementById("clock-date");
const holidayLine = document.getElementById("holiday-line");
const holidayText = document.getElementById("holiday-text");
const weatherIcon = document.getElementById("weather-icon");
const weatherText = document.getElementById("weather-text");
const locationIcon = document.getElementById("location-icon");
const weatherLocation = document.getElementById("weather-location");
const dailyDetails = dailyWidget ? dailyWidget.querySelector(".daily-details") : null;
const inputDir = document.getElementById("input-dir");
const refreshInput = document.getElementById("refresh-input");
const outputBox = document.getElementById("output");
const clearDefaultOutput = document.getElementById("clear-default-output");
const channelMode = document.getElementById("channel-mode");
const sourceWarning = document.getElementById("source-warning");
const channelPreviewPanel = document.getElementById("channel-preview-panel");
const previewFile = document.getElementById("preview-file");
const previewRun = document.getElementById("preview-run");
const previewInfo = document.getElementById("preview-info");
const previewGrid = document.getElementById("preview-grid");
const strengthKind = document.getElementById("strength-kind");
const normalOptions = document.getElementById("normal-options");
const roughnessOptions = document.getElementById("roughness-options");
const normalStrength = document.getElementById("normal-strength");
const normalStrengthValue = document.getElementById("normal-strength-value");
const normalPreviewFile = document.getElementById("normal-preview-file");
const normalPreviewRun = document.getElementById("normal-preview-run");
const normalPreviewInfo = document.getElementById("normal-preview-info");
const normalMode = document.getElementById("normal-mode");
const normalCompareStage = document.getElementById("normal-compare-stage");
const normalPreviewBefore = document.getElementById("normal-preview-before");
const normalPreviewAfter = document.getElementById("normal-preview-after");
const normalCompareDivider = document.getElementById("normal-compare-divider");
const roughnessStrength = document.getElementById("roughness-strength");
const roughnessStrengthValue = document.getElementById("roughness-strength-value");
const roughnessContrast = document.getElementById("roughness-contrast");
const roughnessContrastValue = document.getElementById("roughness-contrast-value");
const roughnessBias = document.getElementById("roughness-bias");
const roughnessBiasValue = document.getElementById("roughness-bias-value");
const roughnessBlack = document.getElementById("roughness-black");
const roughnessBlackValue = document.getElementById("roughness-black-value");
const roughnessWhite = document.getElementById("roughness-white");
const roughnessWhiteValue = document.getElementById("roughness-white-value");
const roughnessGamma = document.getElementById("roughness-gamma");
const roughnessGammaValue = document.getElementById("roughness-gamma-value");
const roughnessCurve = document.getElementById("roughness-curve");
const roughnessCurveValue = document.getElementById("roughness-curve-value");
const roughnessReset = document.getElementById("roughness-reset");
const compressQuality = document.getElementById("compress-quality");
const compressQualityValue = document.getElementById("compress-quality-value");
const pbrSourceType = document.getElementById("pbr-source-type");
const pbrMode = document.getElementById("pbr-mode");
const pbrStrength = document.getElementById("pbr-strength");
const pbrStrengthValue = document.getElementById("pbr-strength-value");
const pbrRadius = document.getElementById("pbr-radius");
const pbrRadiusValue = document.getElementById("pbr-radius-value");
const pbrDetail = document.getElementById("pbr-detail");
const pbrDetailValue = document.getElementById("pbr-detail-value");
const pbrSmooth = document.getElementById("pbr-smooth");
const pbrSmoothValue = document.getElementById("pbr-smooth-value");
const pbrStack = document.getElementById("pbr-stack");
const pbrStackValue = document.getElementById("pbr-stack-value");
const pbrReset = document.getElementById("pbr-reset");
const pbrNormalMode = document.getElementById("pbr-normal-mode");
const pbrPreviewFile = document.getElementById("pbr-preview-file");
const pbrPreviewRun = document.getElementById("pbr-preview-run");
const pbrPreviewInfo = document.getElementById("pbr-preview-info");
const pbrCompareStage = document.getElementById("pbr-compare-stage");
const pbrPreviewBefore = document.getElementById("pbr-preview-before");
const pbrPreviewAfter = document.getElementById("pbr-preview-after");
const pbrCompareDivider = document.getElementById("pbr-compare-divider");
const cropSourceFile = document.getElementById("crop-source-file");
const cropLoadPreview = document.getElementById("crop-load-preview");
const cropAdd = document.getElementById("crop-add");
const cropPreviewImg = document.getElementById("crop-preview-img");
const cropInfo = document.getElementById("crop-info");
const cropCards = document.getElementById("crop-cards");
const cropOverlay = document.getElementById("crop-overlay");
const cropEditor = document.getElementById("crop-editor");
const cropEditorImg = document.getElementById("crop-editor-img");
const cropViewFit = document.getElementById("crop-view-fit");
const cropViewOut = document.getElementById("crop-view-out");
const cropViewIn = document.getElementById("crop-view-in");
const cropViewActual = document.getElementById("crop-view-actual");
const cropViewPan = document.getElementById("crop-view-pan");
const cropViewStatus = document.getElementById("crop-view-status");
const cropHint = document.getElementById("crop-hint");
const cropBox = document.getElementById("crop-box");
const cropActions = document.getElementById("crop-actions");
const cropCustomPixels = document.getElementById("crop-custom-pixels");
const cropCustomWidth = document.getElementById("crop-custom-width");
const cropCustomHeight = document.getElementById("crop-custom-height");
const cropAnchorGrid = document.getElementById("crop-anchor-grid");
const cropConfirm = document.getElementById("crop-confirm");
const cropCancel = document.getElementById("crop-cancel");
const cropZoom = document.getElementById("crop-zoom");
const cropZoomImg = document.getElementById("crop-zoom-img");
const mergePreviewRun = document.getElementById("merge-preview-run");
const mergeCompositePreviewImg = document.getElementById("merge-composite-preview-img");
const mergeCompositePreviewInfo = document.getElementById("merge-composite-preview-info");
const renameSteps = document.getElementById("rename-steps");
const renameStepTemplate = document.getElementById("rename-step-template");
const renameAddStep = document.getElementById("rename-add-step");
const renamePreviewRun = document.getElementById("rename-preview-run");
const renamePreviewInfo = document.getElementById("rename-preview-info");
const renamePreviewList = document.getElementById("rename-preview-list");
const personalizeButton = document.getElementById("personalize");
const settingsPanel = document.getElementById("settings-panel");
const settingsClose = document.getElementById("settings-close");
const toneSelect = document.getElementById("tone-select");
const schemeSelect = document.getElementById("scheme-select");
const radiusSlider = document.getElementById("radius-slider");
const radiusValue = document.getElementById("radius-value");
const settingsSave = document.getElementById("settings-save");
const settingsReset = document.getElementById("settings-reset");
const settingsStatus = document.getElementById("settings-status");
let files = [];
let folderFiles = [];
let currentTool = "resize";
let customOutputValue = outputBox.dataset.default;
let askOutputValue = outputBox.dataset.default;
let mergePreviewTimer = null;
let comparePosition = 50;
let pbrComparePosition = 50;
let cropItems = [];
let cropDraft = null;
let cropDragStart = null;
let cropResizeState = null;
let cropPreviewMeta = null;
let cropView = { x: 0, y: 0, scale: 1, fitScale: 1, panMode: false };
let cropPanState = null;
let cropSpacePan = false;
let cropLastPointerTime = 0;
let workflowSteps = [];
let workflowSelectedStepId = null;
let workflowStepSerial = 1;
const settingsKey = "texture-toolbox-settings-v4";
const memoKey = "texcat-memo-v1";
const defaultUiSettings = { tone: "dark", scheme: "red", radius: 1 };

function sanitizeUiSettings(value) {
  const tone = ["light", "dark"].includes(value && value.tone) ? value.tone : defaultUiSettings.tone;
  const scheme = ["pink", "green", "red", "yellow", "orange", "blue", "cyan", "purple"].includes(value && value.scheme) ? value.scheme : defaultUiSettings.scheme;
  let radius = Number(value && value.radius);
  if (value && value.radius === "compact") radius = 0;
  if (value && value.radius === "round") radius = 1;
  if (!Number.isFinite(radius)) radius = defaultUiSettings.radius;
  radius = Math.max(0, Math.min(1, radius));
  return { tone, scheme, radius };
}
function selectedUiSettings() {
  return sanitizeUiSettings({ tone: toneSelect.value, scheme: schemeSelect.value, radius: radiusSlider.value });
}
function applyUiSettings(settings) {
  const clean = sanitizeUiSettings(settings);
  document.body.classList.remove(
    "theme-dark", "theme-macaron-pink", "theme-macaron-mint",
    "tone-light", "tone-dark",
    "scheme-pink", "scheme-green", "scheme-red", "scheme-yellow",
    "scheme-orange", "scheme-blue", "scheme-cyan", "scheme-purple",
    "radius-compact", "radius-round"
  );
  document.body.classList.add(`tone-${clean.tone}`, `scheme-${clean.scheme}`);
  const limitedRadius = Math.min(clean.radius, 0.5);
  document.body.style.setProperty("--radius", `${(6 + clean.radius * 24).toFixed(1)}px`);
  document.body.style.setProperty("--radius-control", clean.radius >= 0.98 ? "999px" : `${(5 + clean.radius * 28).toFixed(1)}px`);
  document.body.style.setProperty("--radius-limited", `${(5 + limitedRadius * 26).toFixed(1)}px`);
  toneSelect.value = clean.tone;
  schemeSelect.value = clean.scheme;
  radiusSlider.value = clean.radius.toFixed(2);
  radiusValue.textContent = clean.radius.toFixed(2);
  return clean;
}
function loadUiSettings() {
  let saved = null;
  try {
    saved = JSON.parse(localStorage.getItem(settingsKey) || "null");
  } catch (_) {
    saved = null;
  }
  applyUiSettings(saved || defaultUiSettings);
}
function saveUiSettings() {
  const clean = selectedUiSettings();
  applyUiSettings(clean);
  try {
    localStorage.setItem(settingsKey, JSON.stringify(clean));
    settingsStatus.textContent = "设置已保存。";
  } catch (_) {
    settingsStatus.textContent = "当前浏览器不允许保存设置，但本次已生效。";
  }
}
function resetUiSettings() {
  try {
    localStorage.removeItem(settingsKey);
  } catch (_) {}
  applyUiSettings(defaultUiSettings);
  settingsStatus.textContent = "已恢复默认设置。";
}

function loadMemo() {
  try {
    memoBox.value = localStorage.getItem(memoKey) || "";
  } catch (_) {
    memoBox.value = "";
  }
}

function saveMemo() {
  try {
    localStorage.setItem(memoKey, memoBox.value);
  } catch (_) {}
}

function clearMemo() {
  memoBox.value = "";
  saveMemo();
}

const solarFestivals = {
  "01-01": "元旦",
  "02-14": "情人节",
  "03-08": "妇女节",
  "03-12": "植树节",
  "04-01": "愚人节",
  "05-01": "劳动节",
  "05-04": "青年节",
  "06-01": "儿童节",
  "07-01": "建党节",
  "08-01": "建军节",
  "09-10": "教师节",
  "10-01": "国庆节",
  "12-24": "平安夜",
  "12-25": "圣诞节"
};
const weatherCodeText = {
  0: "晴", 1: "大部晴朗", 2: "局部多云", 3: "阴",
  45: "雾", 48: "雾凇",
  51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
  61: "小雨", 63: "中雨", 65: "大雨",
  71: "小雪", 73: "中雪", 75: "大雪",
  80: "阵雨", 81: "较强阵雨", 82: "强阵雨",
  95: "雷雨", 96: "雷雨伴冰雹", 99: "强雷雨伴冰雹"
};
const weatherCodeIcon = {
  0: "☼", 1: "☼", 2: "◐", 3: "☁",
  45: "≋", 48: "≋",
  51: "☂", 53: "☂", 55: "☂",
  61: "☂", 63: "☂", 65: "☂",
  71: "❄", 73: "❄", 75: "❄",
  80: "☂", 81: "☂", 82: "☂",
  95: "ϟ", 96: "ϟ", 99: "ϟ"
};

function timePeriodLabel(hour) {
  if (hour < 5) return "凌晨";
  if (hour < 8) return "早上";
  if (hour < 11) return "上午";
  if (hour < 13) return "中午";
  if (hour < 17) return "下午";
  if (hour < 19) return "傍晚";
  if (hour < 23) return "晚上";
  return "深夜";
}

function formatChineseClock(date) {
  const hour24 = date.getHours();
  const hour12 = hour24 % 12 || 12;
  const minute = String(date.getMinutes()).padStart(2, "0");
  const second = String(date.getSeconds()).padStart(2, "0");
  return `${timePeriodLabel(hour24)} ${hour12}:${minute}:${second}`;
}

function updateClock() {
  const now = new Date();
  clockTime.textContent = formatChineseClock(now);
  clockDate.textContent = now.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long"
  });
}

function fetchJsonWithTimeout(url, timeout = 5000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  return fetch(url, { signal: controller.signal, cache: "no-store" })
    .then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .finally(() => clearTimeout(timer));
}

function localFestivalText(date) {
  const key = `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  return solarFestivals[key] || "";
}

async function loadHolidayText(date, countryCode) {
  const year = date.getFullYear();
  const isoToday = `${year}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  const code = (countryCode || "CN").toUpperCase();
  try {
    const holidays = await fetchJsonWithTimeout(`https://date.nager.at/api/v3/PublicHolidays/${year}/${code}`, 5000);
    const today = Array.isArray(holidays) ? holidays.filter(item => item.date === isoToday) : [];
    return today.map(item => item.localName || item.name).filter(Boolean).join("、");
  } catch (_) {
    return "";
  }
}

async function initDailyWidget() {
  updateClock();
  setInterval(updateClock, 1000);
  dailyWidget.hidden = false;
  holidayLine.hidden = true;
  if (dailyDetails) dailyDetails.hidden = true;
  if (!navigator.onLine) {
    return;
  }
  try {
    const location = await fetchJsonWithTimeout("https://ipapi.co/json/", 5000);
    const latitude = Number(location.latitude);
    const longitude = Number(location.longitude);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) throw new Error("定位失败");
    const weather = await fetchJsonWithTimeout(
      `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,relative_humidity_2m,weather_code&timezone=auto`,
      5000
    );
    const current = weather.current || {};
    const now = new Date();
    const festival = localFestivalText(now);
    const holiday = await loadHolidayText(now, location.country_code);
    const holidayValue = [festival, holiday].filter(Boolean).join(" / ");
    holidayText.textContent = holidayValue;
    holidayLine.hidden = !holidayValue;
    const weatherName = weatherCodeText[current.weather_code] || "天气";
    weatherIcon.textContent = weatherCodeIcon[current.weather_code] || "○";
    weatherIcon.title = weatherName;
    const temp = Number.isFinite(Number(current.temperature_2m)) ? `${Number(current.temperature_2m).toFixed(0)}℃` : "--℃";
    const humidity = Number.isFinite(Number(current.relative_humidity_2m)) ? `湿度 ${Number(current.relative_humidity_2m).toFixed(0)}%` : "";
    weatherText.textContent = `${temp}${humidity ? ` / ${humidity}` : ""}`;
    locationIcon.title = "位置";
    weatherLocation.textContent = [location.city, location.region, location.country_name].filter(Boolean).join(" / ");
    if (dailyDetails) dailyDetails.hidden = false;
    dailyWidget.hidden = false;
  } catch (_) {
    holidayLine.hidden = true;
    if (dailyDetails) dailyDetails.hidden = true;
  }
}

function inputMode() {
  return document.querySelector('input[name="input-mode"]:checked').value;
}
function outputMode() {
  return document.querySelector('input[name="output-mode"]:checked').value;
}
function normalizePathText(value) {
  return (value || "").trim().replace(/^["']|["']$/g, "").replace(/\\/g, "/").replace(/\/+$/g, "").toLowerCase();
}
function updateSourceWarning() {
  const inPath = normalizePathText(inputDir.value);
  const outPath = normalizePathText(outputBox.value);
  const mode = outputMode();
  const sourceWithUploaded = mode === "source" && inputMode() !== "folder";
  const sameCustomFolder = inputMode() === "folder" && mode !== "default" && mode !== "source" && inPath && outPath && inPath === outPath;
  sourceWarning.classList.toggle("strong", sameCustomFolder);
  if (sourceWithUploaded) {
    sourceWarning.classList.add("strong");
    sourceWarning.textContent = "提醒：源文件位置输出只支持自定义输入目录；拖入/选择列表无法读取源图真实文件夹。";
  } else if (sameCustomFolder) {
    sourceWarning.textContent = "提醒：当前自定义输入目录和输出目录看起来相同，同名输出文件可能覆盖源文件。";
  } else {
    sourceWarning.textContent = "提醒：自定义输入目录只读取源图；拖入/选择使用临时缓存，任务完成后自动删除。请避免把自定义输出目录设为源图目录，以免同名文件被覆盖。";
  }
}
function log(text) {
  logBox.classList.remove("log-idle");
  logBox.classList.add("log-active");
  logBox.textContent += "\n" + text;
  logBox.scrollTop = logBox.scrollHeight;
}
function resetLog(text) {
  logBox.textContent = text;
  logBox.classList.remove("log-active");
  logBox.classList.add("log-idle");
}
function setPreviewImage(img, dataUrl) {
  if (dataUrl) {
    img.src = dataUrl;
    img.classList.remove("preview-empty");
  } else {
    img.removeAttribute("src");
    img.classList.add("preview-empty");
  }
}
function fileSizeLabel(size) {
  return `${Math.round((size || 0) / 1024)} KB`;
}
function uploadedFileLabel(file, i) {
  return `${i + 1}. ${file.webkitRelativePath || file.name} (${Math.round(file.size / 1024)} KB)`;
}
function folderFileLabel(item, i) {
  return `${i + 1}. ${item.relative || item.name} (${fileSizeLabel(item.size)})`;
}
function workflowInputItems() {
  return inputMode() === "folder"
    ? folderFiles.map((item, i) => ({ name: item.relative || item.name, size: item.size, index: i + 1, source: "自定义目录" }))
    : files.map((file, i) => ({ name: file.webkitRelativePath || file.name, size: file.size, index: i + 1, source: "拖入/选择" }));
}
const workflowStepDefinitions = {
  resize: {
    label: "缩放尺寸",
    summary: "选择目标尺寸，生成多级贴图输出。",
    detail: "复用图像大小模块的尺寸、缩放配置、输出格式、锁定比例和尺寸后缀参数。"
  },
  export: {
    label: "格式与压缩",
    summary: "设置输出格式、无损优先和有损质量。",
    detail: "复用格式转换和高质量压缩模块的输出格式、质量和无损优先策略。"
  },
  crop: {
    label: "图片裁切",
    summary: "记录裁切框和多图同位置裁切策略。",
    detail: "参数占位：单图/多图同位置、自由框选、1:1、自定义像素、九宫格吸附、裁切命名。"
  },
  normal: {
    label: "法线/黑白调整",
    summary: "调整法线强度或黑白图色阶曲线。",
    detail: "参数占位：法线 OpenGL/DX、强度、黑白强度、色阶、Gamma、曲线、反相。"
  },
  pbr: {
    label: "PBR辅助生成",
    summary: "当前开发轮次暂不纳入工作流推进。",
    detail: "PBR辅助继续保留在快速工具模式；工作流接入会等后续算法和默认预设单独优化后再恢复。"
  },
  split: {
    label: "通道拆分",
    summary: "拆出 L/R/G/B/A 通道贴图。",
    detail: "参数占位：启用通道、通道命名模板、输出格式。后续复用通道拆分模块。"
  },
  merge: {
    label: "通道合并/打包",
    summary: "将多张图或指定通道打包为 RGB/RGBA。",
    detail: "参数占位：基础图、目标 R/G/B/A 来源、默认黑白通道、合成图命名。"
  },
  rename: {
    label: "命名规则",
    summary: "为最终输出文件叠加命名规则。",
    detail: "复用批量重命名模块的步骤叠加规则，保存查找替换、前缀、后缀和中间插入参数。"
  }
};
const workflowSizeValues = [8192, 4096, 2048, 1024, 512, 256];
const workflowFormatValues = ["psd", "png", "tga", "tif", "tiff", "jpg", "jpeg", "dds", "webp", "bmp"];
const workflowFormatLabels = {
  keep: "保持原格式",
  psd: "PSD",
  png: "PNG",
  tga: "TGA",
  tif: "TIF",
  tiff: "TIFF",
  jpg: "JPG",
  jpeg: "JPEG",
  dds: "DDS",
  webp: "WEBP",
  bmp: "BMP",
};
const workflowProfileLabels = {
  detail: "detail - 颜色贴图/细节保留",
  data: "data - 法线/遮罩/数据贴图",
  pixel: "pixel - 像素风/硬边",
};
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}
function workflowOptionHtml(values, labels, selected) {
  return values.map(value => `<option value="${escapeHtml(value)}"${String(selected) === String(value) ? " selected" : ""}>${escapeHtml(labels[value] || String(value).toUpperCase())}</option>`).join("");
}
function workflowFormatOptionHtml(selected, includeKeep = true) {
  return workflowOptionHtml(includeKeep ? ["keep", ...workflowFormatValues] : workflowFormatValues, workflowFormatLabels, selected);
}
function workflowSizeLabel(size) {
  const labels = { 8192: "8K", 4096: "4K", 2048: "2K", 1024: "1K", 512: "512", 256: "256" };
  return labels[size] || `${size}`;
}
function workflowNormalizeSizes(value) {
  if (!Array.isArray(value)) return [];
  const seen = new Set();
  const sizes = [];
  for (const item of value) {
    const size = Number(item);
    if (Number.isFinite(size) && size > 0 && !seen.has(size)) {
      seen.add(size);
      sizes.push(size);
    }
  }
  return sizes;
}
function workflowDefaultRenameStep() {
  return { op: "replace", find: "", replace: "", prefix: "", suffix: "", left: "", right: "", insert: "" };
}
function workflowDefaultOptions(type) {
  if (type === "resize") {
    return { sizes: [], custom: "", profile: "detail", format: "keep", preserve: true, append_size_suffix: true };
  }
  if (type === "export") {
    return { format: "png", quality: 95, lossless: true };
  }
  if (type === "rename") {
    return { format: "keep", steps: [workflowDefaultRenameStep()] };
  }
  return {};
}
function workflowMergeOptions(type, options) {
  const defaults = workflowDefaultOptions(type);
  const merged = { ...defaults, ...(options && typeof options === "object" ? options : {}) };
  if (type === "resize") {
    merged.sizes = workflowNormalizeSizes(merged.sizes);
    merged.custom = String(merged.custom || "");
    merged.profile = workflowProfileLabels[merged.profile] ? merged.profile : "detail";
    merged.format = merged.format === "keep" || workflowFormatValues.includes(merged.format) ? merged.format : "keep";
    merged.preserve = merged.preserve !== false;
    merged.append_size_suffix = merged.append_size_suffix !== false;
  } else if (type === "export") {
    merged.format = workflowFormatValues.includes(merged.format) ? merged.format : "png";
    merged.quality = Math.max(80, Math.min(100, Math.round(Number(merged.quality) || 95)));
    merged.lossless = merged.lossless !== false;
  } else if (type === "rename") {
    merged.format = merged.format === "keep" || workflowFormatValues.includes(merged.format) ? merged.format : "keep";
    merged.steps = Array.isArray(merged.steps) && merged.steps.length ? merged.steps.map(step => ({ ...workflowDefaultRenameStep(), ...(step || {}) })) : [workflowDefaultRenameStep()];
  }
  return merged;
}
function currentResizeWorkflowOptions() {
  return workflowMergeOptions("resize", {
    sizes: [...document.querySelectorAll('input[name="size"]:checked')].map(input => Number(input.value)),
    custom: document.getElementById("resize-custom").value.trim(),
    profile: document.getElementById("resize-profile").value,
    format: document.getElementById("resize-format").value,
    preserve: document.getElementById("resize-preserve").checked,
    append_size_suffix: document.getElementById("resize-size-suffix").checked,
  });
}
function currentExportWorkflowOptions() {
  return workflowMergeOptions("export", {
    format: document.getElementById("convert-format").value || document.getElementById("compress-format").value,
    quality: Number(compressQuality.value) || 95,
    lossless: document.getElementById("compress-lossless").checked,
  });
}
function currentRenameWorkflowOptions() {
  return workflowMergeOptions("rename", {
    format: document.getElementById("rename-format").value,
    steps: getRenameSteps(),
  });
}
function workflowInitialOptions(type) {
  try {
    if (type === "resize") return currentResizeWorkflowOptions();
    if (type === "export") return currentExportWorkflowOptions();
    if (type === "rename") return currentRenameWorkflowOptions();
  } catch (_error) {
    return workflowDefaultOptions(type);
  }
  return workflowDefaultOptions(type);
}
function workflowStepDefinition(type) {
  return workflowStepDefinitions[type] || workflowStepDefinitions.resize;
}
function createWorkflowStep(type) {
  const definition = workflowStepDefinition(type);
  return {
    id: `workflow-step-${Date.now()}-${workflowStepSerial++}`,
    type,
    enabled: true,
    label: definition.label,
    summary: definition.summary,
    options: workflowInitialOptions(type),
  };
}
function normalizeWorkflowStep(raw, index) {
  const type = raw && workflowStepDefinitions[raw.type] ? raw.type : "resize";
  const definition = workflowStepDefinition(type);
  return {
    id: raw && typeof raw.id === "string" && raw.id ? raw.id : `workflow-step-loaded-${Date.now()}-${index}`,
    type,
    enabled: raw && typeof raw.enabled === "boolean" ? raw.enabled : true,
    label: raw && typeof raw.label === "string" && raw.label ? raw.label : definition.label,
    summary: raw && typeof raw.summary === "string" && raw.summary ? raw.summary : definition.summary,
    options: workflowMergeOptions(type, raw && raw.options && typeof raw.options === "object" ? raw.options : {}),
  };
}
function workflowResizeSizeParts(options) {
  const sizes = workflowNormalizeSizes(options.sizes).map(workflowSizeLabel);
  const custom = String(options.custom || "").split(/[;,]/).map(value => value.trim()).filter(Boolean);
  return sizes.concat(custom);
}
function workflowStepSummary(step) {
  const definition = workflowStepDefinition(step.type);
  const options = workflowMergeOptions(step.type, step.options);
  if (step.type === "resize") {
    const sizeText = workflowResizeSizeParts(options).join(" / ") || "未选择尺寸";
    const formatText = workflowFormatLabels[options.format] || options.format.toUpperCase();
    return `${sizeText}，${workflowProfileLabels[options.profile].split(" - ")[0]}，${formatText}${options.append_size_suffix ? "，尺寸后缀" : ""}`;
  }
  if (step.type === "export") {
    const formatText = workflowFormatLabels[options.format] || options.format.toUpperCase();
    return `${formatText}，质量 ${options.quality}，${options.lossless ? "无损优先" : "有损高质量"}`;
  }
  if (step.type === "rename") {
    return `${options.steps.length} 个命名步骤，${workflowFormatLabels[options.format] || options.format.toUpperCase()}`;
  }
  return step.summary || definition.summary;
}
function selectedWorkflowStep() {
  return workflowSteps.find(step => step.id === workflowSelectedStepId) || null;
}
function workflowStatus(text) {
  if (workflowJsonStatus) workflowJsonStatus.textContent = text;
}
function renderWorkflowSteps() {
  if (!workflowStepList) return;
  workflowStepList.innerHTML = "";
  if (!workflowSteps.length) {
    const empty = document.createElement("div");
    empty.className = "workflow-empty";
    empty.textContent = "尚未添加步骤。先选择一个步骤类型，再点击添加步骤。";
    workflowStepList.appendChild(empty);
    return;
  }
  workflowSteps.forEach((step, index) => {
    const definition = workflowStepDefinition(step.type);
    const card = document.createElement("div");
    card.className = `workflow-step-card${step.id === workflowSelectedStepId ? " active" : ""}`;
    card.onclick = event => {
      if (event.target.closest("button")) return;
      workflowSelectedStepId = step.id;
      renderWorkflowShell();
    };
    const head = document.createElement("div");
    head.className = "workflow-step-head";
    const title = document.createElement("div");
    title.className = "workflow-step-title";
    const number = document.createElement("span");
    number.className = "workflow-step-number";
    number.textContent = String(index + 1);
    const titleText = document.createElement("span");
    titleText.textContent = step.label || definition.label;
    title.appendChild(number);
    title.appendChild(titleText);
    const controls = document.createElement("div");
    controls.className = "workflow-step-controls";
    const toggle = document.createElement("button");
    toggle.className = "secondary";
    toggle.type = "button";
    toggle.textContent = step.enabled ? "启用" : "停用";
    toggle.onclick = () => {
      step.enabled = !step.enabled;
      workflowStatus(`${step.label || definition.label} 已${step.enabled ? "启用" : "停用"}。`);
      renderWorkflowShell();
    };
    const up = document.createElement("button");
    up.className = "secondary";
    up.type = "button";
    up.textContent = "上移";
    up.disabled = index === 0;
    up.onclick = () => {
      [workflowSteps[index - 1], workflowSteps[index]] = [workflowSteps[index], workflowSteps[index - 1]];
      workflowStatus("步骤顺序已调整。");
      renderWorkflowShell();
    };
    const down = document.createElement("button");
    down.className = "secondary";
    down.type = "button";
    down.textContent = "下移";
    down.disabled = index === workflowSteps.length - 1;
    down.onclick = () => {
      [workflowSteps[index], workflowSteps[index + 1]] = [workflowSteps[index + 1], workflowSteps[index]];
      workflowStatus("步骤顺序已调整。");
      renderWorkflowShell();
    };
    const duplicate = document.createElement("button");
    duplicate.className = "secondary";
    duplicate.type = "button";
    duplicate.textContent = "复制";
    duplicate.onclick = () => {
      const copy = normalizeWorkflowStep({ ...step, id: "", label: `${step.label || definition.label} 副本`, options: { ...step.options } }, workflowSteps.length);
      copy.id = `workflow-step-${Date.now()}-${workflowStepSerial++}`;
      workflowSteps.splice(index + 1, 0, copy);
      workflowSelectedStepId = copy.id;
      workflowStatus("步骤已复制。");
      renderWorkflowShell();
    };
    const del = document.createElement("button");
    del.className = "secondary";
    del.type = "button";
    del.textContent = "删除";
    del.onclick = () => {
      workflowSteps.splice(index, 1);
      if (workflowSelectedStepId === step.id) workflowSelectedStepId = workflowSteps[index]?.id || workflowSteps[index - 1]?.id || null;
      workflowStatus("步骤已删除。");
      renderWorkflowShell();
    };
    for (const button of [toggle, up, down, duplicate, del]) controls.appendChild(button);
    head.appendChild(title);
    head.appendChild(controls);
    const summary = document.createElement("div");
    summary.className = "muted";
    summary.textContent = `${step.enabled ? "参与流程" : "已停用"} | ${workflowStepSummary(step)}`;
    card.appendChild(head);
    card.appendChild(summary);
    workflowStepList.appendChild(card);
  });
}
function updateWorkflowSummary() {
  if (!workflowOutputSummary) return;
  const items = workflowInputItems();
  workflowSummaryInputs.textContent = String(items.length);
  workflowSummarySteps.textContent = String(workflowSteps.length);
  const activeSteps = workflowSteps.filter(step => step.enabled);
  let outputMultiplier = 1;
  for (const step of activeSteps) {
    if (step.type === "resize") {
      const options = workflowMergeOptions("resize", step.options);
      outputMultiplier = Math.max(outputMultiplier, Math.max(1, workflowResizeSizeParts(options).length));
    }
  }
  workflowSummaryOutputs.textContent = items.length ? `约 ${items.length * outputMultiplier} 个输出（Beta估算）` : "待接入";
  const renameStep = activeSteps.find(step => step.type === "rename");
  workflowSummaryNaming.textContent = renameStep ? workflowStepSummary(renameStep) : "待接入";
  workflowSummaryConflicts.textContent = activeSteps.length ? "执行前统一检查" : "待接入";
  const exportStep = activeSteps.find(step => step.type === "export");
  workflowSummaryExport.textContent = exportStep ? workflowStepSummary(exportStep) : "复用全局设置";
}
function refreshWorkflowAfterOptionChange(step, message = "工作流步骤参数已更新。") {
  step.options = workflowMergeOptions(step.type, step.options);
  step.summary = workflowStepSummary(step);
  renderWorkflowSteps();
  updateWorkflowSummary();
  if (message) workflowStatus(message);
}
function appendWorkflowDetailNote(definition) {
  const note = document.createElement("div");
  note.className = "workflow-detail-note";
  note.textContent = definition.detail;
  workflowDetailBody.appendChild(note);
}
function renderWorkflowResizeDetail(step) {
  step.options = workflowMergeOptions("resize", step.options);
  const options = step.options;
  const card = document.createElement("div");
  card.className = "workflow-param-card";
  const sizeControls = workflowSizeValues.map(size => `
    <label><input type="checkbox" data-workflow-size value="${size}"${options.sizes.includes(size) ? " checked" : ""}>${workflowSizeLabel(size)}</label>
  `).join("");
  card.innerHTML = `
    <div class="workflow-param-actions">
      <button class="secondary" type="button" data-workflow-sync>读取当前图像大小模块设置</button>
      <span class="muted">用于把快速工具里已经调好的参数同步进此步骤。</span>
    </div>
    <div class="workflow-size-options">
      <span class="row-title">目标尺寸</span>
      ${sizeControls}
    </div>
    <div class="workflow-param-grid">
      <label>自定义尺寸 <input data-workflow-custom type="text" value="${escapeHtml(options.custom)}" placeholder="1536,768"></label>
      <label>缩放配置
        <select data-workflow-profile>${workflowOptionHtml(Object.keys(workflowProfileLabels), workflowProfileLabels, options.profile)}</select>
      </label>
      <label>输出格式
        <select data-workflow-format>${workflowFormatOptionHtml(options.format, true)}</select>
      </label>
    </div>
    <div class="workflow-size-options">
      <label><input data-workflow-preserve type="checkbox"${options.preserve ? " checked" : ""}>锁定比例</label>
      <label><input data-workflow-size-suffix type="checkbox"${options.append_size_suffix ? " checked" : ""}>添加尺寸后缀</label>
    </div>
  `;
  const apply = () => {
    step.options = workflowMergeOptions("resize", {
      sizes: [...card.querySelectorAll("[data-workflow-size]:checked")].map(input => Number(input.value)),
      custom: card.querySelector("[data-workflow-custom]").value.trim(),
      profile: card.querySelector("[data-workflow-profile]").value,
      format: card.querySelector("[data-workflow-format]").value,
      preserve: card.querySelector("[data-workflow-preserve]").checked,
      append_size_suffix: card.querySelector("[data-workflow-size-suffix]").checked,
    });
    refreshWorkflowAfterOptionChange(step);
  };
  card.querySelector("[data-workflow-sync]").onclick = () => {
    step.options = currentResizeWorkflowOptions();
    workflowStatus("已读取当前图像大小模块设置。");
    renderWorkflowShell();
  };
  card.querySelectorAll("input, select").forEach(input => {
    input.oninput = apply;
    input.onchange = apply;
  });
  workflowDetailBody.appendChild(card);
}
function renderWorkflowExportDetail(step) {
  step.options = workflowMergeOptions("export", step.options);
  const options = step.options;
  const card = document.createElement("div");
  card.className = "workflow-param-card";
  card.innerHTML = `
    <div class="workflow-param-actions">
      <button class="secondary" type="button" data-workflow-sync>读取当前格式/压缩模块设置</button>
      <span class="muted">格式来自格式转换模块，质量和无损优先来自高质量压缩模块。</span>
    </div>
    <div class="workflow-param-grid">
      <label>输出格式
        <select data-workflow-format>${workflowFormatOptionHtml(options.format, false)}</select>
      </label>
      <label>有损格式质量
        <input data-workflow-quality type="range" min="80" max="100" step="1" value="${options.quality}">
        <strong data-workflow-quality-value>${options.quality}</strong>
      </label>
      <label><input data-workflow-lossless type="checkbox"${options.lossless ? " checked" : ""}>无损优先</label>
    </div>
    <div class="muted">JPG/JPEG 仍然是有损格式且不保留 Alpha；DDS 仍使用当前运行时能力，不承诺 BC 系列游戏压缩编码。</div>
  `;
  const qualityValue = card.querySelector("[data-workflow-quality-value]");
  const apply = () => {
    const quality = Math.round(Number(card.querySelector("[data-workflow-quality]").value) || 95);
    qualityValue.textContent = String(quality);
    step.options = workflowMergeOptions("export", {
      format: card.querySelector("[data-workflow-format]").value,
      quality,
      lossless: card.querySelector("[data-workflow-lossless]").checked,
    });
    refreshWorkflowAfterOptionChange(step);
  };
  card.querySelector("[data-workflow-sync]").onclick = () => {
    step.options = currentExportWorkflowOptions();
    workflowStatus("已读取当前格式转换和高质量压缩模块设置。");
    renderWorkflowShell();
  };
  card.querySelectorAll("input, select").forEach(input => {
    input.oninput = apply;
    input.onchange = apply;
  });
  workflowDetailBody.appendChild(card);
}
function workflowRenameOpLabel(op) {
  return {
    replace: "查找替换",
    prefix: "添加前缀/项目名",
    suffix: "添加后缀",
    insert: "中间插入文本",
  }[op] || "命名步骤";
}
function workflowRenameStepDescription(step) {
  if (step.op === "replace") return `${step.find || "空"} -> ${step.replace || "空"}`;
  if (step.op === "prefix") return `前缀：${step.prefix || "空"}`;
  if (step.op === "suffix") return `后缀：${step.suffix || "空"}`;
  if (step.op === "insert") return `${step.left || "左侧为空"} + ${step.insert || "插入为空"} + ${step.right || "右侧为空"}`;
  return "未设置";
}
function renderWorkflowRenameDetail(step) {
  step.options = workflowMergeOptions("rename", step.options);
  const options = step.options;
  const card = document.createElement("div");
  card.className = "workflow-param-card";
  card.innerHTML = `
    <div class="workflow-param-actions">
      <button class="secondary" type="button" data-workflow-sync>读取当前批量重命名模块规则</button>
      <span class="muted">先在快速工具模式的批量重命名里编辑步骤，再同步到工作流。</span>
    </div>
    <div class="workflow-param-grid">
      <label>输出格式
        <select data-workflow-format>${workflowFormatOptionHtml(options.format, true)}</select>
      </label>
    </div>
    <div class="workflow-param-list" data-workflow-rename-list></div>
  `;
  const list = card.querySelector("[data-workflow-rename-list]");
  options.steps.forEach((renameStep, index) => {
    const row = document.createElement("div");
    const label = document.createElement("span");
    label.textContent = `步骤 ${index + 1}：${workflowRenameOpLabel(renameStep.op)}`;
    const value = document.createElement("strong");
    value.textContent = workflowRenameStepDescription(renameStep);
    row.appendChild(label);
    row.appendChild(value);
    list.appendChild(row);
  });
  card.querySelector("[data-workflow-format]").onchange = event => {
    step.options = workflowMergeOptions("rename", { ...step.options, format: event.target.value });
    refreshWorkflowAfterOptionChange(step);
  };
  card.querySelector("[data-workflow-sync]").onclick = () => {
    step.options = currentRenameWorkflowOptions();
    workflowStatus("已读取当前批量重命名模块规则。");
    renderWorkflowShell();
  };
  workflowDetailBody.appendChild(card);
}
function renderWorkflowPendingDetail(step) {
  const options = step.options && Object.keys(step.options).length ? step.options : {};
  const card = document.createElement("div");
  card.className = "workflow-param-card";
  const title = document.createElement("strong");
  title.textContent = "后续阶段接入";
  const text = document.createElement("div");
  text.className = "muted";
  text.textContent = "这个步骤需要预览状态或中间图数据，当前先保留在工作流结构中，不开放真实参数编辑。";
  card.appendChild(title);
  card.appendChild(text);
  if (Object.keys(options).length) {
    const pre = document.createElement("pre");
    pre.className = "muted";
    pre.textContent = JSON.stringify(options, null, 2);
    card.appendChild(pre);
  }
  workflowDetailBody.appendChild(card);
}
function renderWorkflowDetail() {
  const step = selectedWorkflowStep();
  workflowDetailBody.innerHTML = "";
  if (!step) {
    workflowDetailTitle.textContent = "未选中步骤";
    const empty = document.createElement("div");
    empty.className = "workflow-detail-note";
    empty.textContent = workflowSteps.length ? "选择一个步骤后，这里会显示该步骤的参数设置。" : "添加一个步骤后，这里会显示该步骤的默认参数和后续实现范围。";
    workflowDetailBody.appendChild(empty);
    return;
  }
  const definition = workflowStepDefinition(step.type);
  workflowDetailTitle.textContent = `${step.label || definition.label}`;
  appendWorkflowDetailNote(definition);
  if (step.type === "resize") {
    renderWorkflowResizeDetail(step);
  } else if (step.type === "export") {
    renderWorkflowExportDetail(step);
  } else if (step.type === "rename") {
    renderWorkflowRenameDetail(step);
  } else {
    renderWorkflowPendingDetail(step);
  }
}
function workflowPayload() {
  return {
    version: 1,
    app: "TexCat",
    mode: "workflow-beta",
    saved_at: new Date().toISOString(),
    input: {
      mode: inputMode(),
      source: inputDir.value,
      count: workflowInputItems().length,
    },
    output: {
      mode: outputMode(),
      path: outputBox.value,
      channel_mode: channelMode.value,
    },
    steps: workflowSteps.map(step => ({
      id: step.id,
      type: step.type,
      enabled: step.enabled,
      label: step.label,
      summary: workflowStepSummary(step),
      options: workflowMergeOptions(step.type, step.options),
    })),
  };
}
function saveWorkflowJson() {
  const payload = workflowPayload();
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `TexCat_workflow_${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  workflowStatus(`已导出工作流 JSON：${payload.steps.length} 个步骤。`);
}
function loadWorkflowJsonFile(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(String(reader.result || "{}"));
      const steps = Array.isArray(data.steps) ? data.steps.map(normalizeWorkflowStep) : [];
      workflowSteps = steps;
      workflowSelectedStepId = workflowSteps[0]?.id || null;
      workflowStepSerial += workflowSteps.length + 1;
      workflowStatus(`已载入工作流 JSON：${workflowSteps.length} 个步骤。`);
      renderWorkflowShell();
    } catch (error) {
      workflowStatus(`载入失败：${error.message}`);
    }
  };
  reader.readAsText(file, "utf-8");
}
function appendWorkflowCommon(form) {
  form.append("input_mode", inputMode());
  form.append("input", inputDir.value);
  form.append("output_mode", outputMode());
  form.append("output", outputBox.value);
  form.append("channel_mode", channelMode.value);
  form.append("workflow", JSON.stringify(workflowPayload()));
  if (inputMode() === "uploaded") {
    for (const file of files) form.append("files", file, file.webkitRelativePath || file.name);
  }
}
async function chooseWorkflowOutputDirectoryIfNeeded() {
  if (outputMode() !== "ask") return true;
  workflowStatus("请选择本次工作流预览的输出文件夹。");
  const form = new FormData();
  form.append("current", askOutputValue || outputBox.value || outputBox.dataset.default);
  const response = await fetch("/choose-output-dir", { method: "POST", body: form });
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error || "选择输出目录失败");
  if (result.cancelled) return false;
  askOutputValue = result.path;
  outputBox.value = result.path;
  return true;
}
function appendWorkflowPreviewRow(parent, cells, className = "") {
  const row = document.createElement("div");
  row.className = `preview-row ${className}`.trim();
  for (const text of cells) {
    const cell = document.createElement("div");
    cell.textContent = text;
    row.appendChild(cell);
  }
  parent.appendChild(row);
}
function renderWorkflowPreview(result) {
  const items = result.items || [];
  const conflicts = items.filter(item => item.conflict).length;
  workflowPreviewList.innerHTML = "";
  appendWorkflowPreviewRow(workflowPreviewList, ["源图", "预计文件名", "格式", "状态", "输出路径"], "header");
  for (const item of items.slice(0, 120)) {
    appendWorkflowPreviewRow(
      workflowPreviewList,
      [
        item.source || "",
        item.target || "",
        item.format || "",
        item.conflict ? `冲突：${item.reason || "同名"}` : "可用",
        item.path || "",
      ],
      item.conflict ? "conflict" : ""
    );
  }
  if (items.length > 120) {
    appendWorkflowPreviewRow(workflowPreviewList, ["...", `还有 ${items.length - 120} 个输出未展开`, "", "", ""], "");
  }
  const warningText = (result.warnings || []).join("；");
  workflowSummaryOutputs.textContent = `${result.total || items.length} 个预计输出`;
  workflowSummaryConflicts.textContent = conflicts ? `${conflicts} 个冲突` : "未发现冲突";
  workflowPreviewInfo.textContent = `${result.total || items.length} 个预计输出，${conflicts ? `${conflicts} 个冲突` : "未发现冲突"}${warningText ? `；${warningText}` : ""}`;
}
async function previewWorkflowPlan() {
  let count = 0;
  if (inputMode() === "folder") {
    const ok = await refreshFolderFiles(false);
    count = folderFiles.length;
    if (!ok || !count) { log("请确认自定义输入目录里有支持格式图片。"); return; }
  } else {
    count = files.length;
    if (!count) { log("请先拖入或选择图片。"); return; }
  }
  if (!workflowSteps.length) {
    workflowStatus("请先添加至少一个工作流步骤。");
    return;
  }
  workflowPreviewRun.disabled = true;
  workflowPreviewInfo.textContent = "正在预览工作流输出...";
  try {
    const selectedOutput = await chooseWorkflowOutputDirectoryIfNeeded();
    if (!selectedOutput) {
      workflowPreviewInfo.textContent = "已取消预览。";
      workflowStatus("已取消工作流输出预览。");
      return;
    }
    const form = new FormData();
    appendWorkflowCommon(form);
    const response = await fetch("/preview-workflow", { method: "POST", body: form });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "预览失败");
    renderWorkflowPreview(result);
    workflowStatus(`已生成工作流输出预览：${result.total || 0} 个预计输出。`);
  } catch (error) {
    workflowPreviewInfo.textContent = `预览失败：${error.message}`;
    workflowStatus(`预览失败：${error.message}`);
    log(`工作流预览失败：${error.message}`);
  } finally {
    workflowPreviewRun.disabled = false;
  }
}
function renderWorkflowShell() {
  if (!workflowResourceSummary || !workflowResourceList) return;
  const items = workflowInputItems();
  const modeLabel = inputMode() === "folder" ? "自定义输入目录" : "拖入/选择列表";
  workflowResourceSummary.textContent = items.length
    ? `${modeLabel}：已准备 ${items.length} 张图片。`
    : `${modeLabel}：尚未添加图片。`;
  workflowResourceList.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "workflow-empty";
    empty.textContent = "拖入、批量选择或扫描目录后，这里会同步显示工作流输入资源。";
    workflowResourceList.appendChild(empty);
  } else {
    const shown = items.slice(0, 12);
    for (const item of shown) {
      const row = document.createElement("div");
      row.className = "workflow-row";
      const name = document.createElement("strong");
      name.className = "workflow-row-name";
      name.textContent = `${item.index}. ${item.name}`;
      const meta = document.createElement("span");
      meta.className = "muted";
      meta.textContent = `${item.source} | ${fileSizeLabel(item.size)}`;
      row.appendChild(name);
      row.appendChild(meta);
      workflowResourceList.appendChild(row);
    }
    if (items.length > shown.length) {
      const more = document.createElement("div");
      more.className = "workflow-row muted";
      more.textContent = `还有 ${items.length - shown.length} 张未展开显示。`;
      workflowResourceList.appendChild(more);
    }
  }
  updateWorkflowSummary();
  renderWorkflowSteps();
  renderWorkflowDetail();
}
function renderFiles() {
  if (inputMode() === "folder") {
    filesBox.textContent = folderFiles.length ? folderFiles.map(folderFileLabel).join("\n") : "自定义输入目录中尚未扫描到支持格式图片。";
  } else {
    filesBox.textContent = files.length ? files.map(uploadedFileLabel).join("\n") : "尚未添加图片。";
  }
  renderMergeSelectors();
  renderPreviewSelector();
  renderNormalPreviewSelector();
  renderPbrPreviewSelector();
  renderCropSelector();
  renderWorkflowShell();
  if (currentTool === "crop" && cropSourceFile.value !== "") loadCropPreview();
}
function renderMergeSelectors() {
  const names = inputMode() === "folder"
    ? folderFiles.map(item => item.relative || item.name)
    : files.map(file => file.webkitRelativePath || file.name);
  populateFileSelect(document.getElementById("merge-base"), names, "无基础图");
  for (const key of ["r", "g", "b", "a"]) {
    populateMergeModeSelect(document.getElementById(`merge-${key}-mode`), key);
    populateFileSelect(document.getElementById(`merge-${key}-file`), names, "未选择");
    populateSourceChannelSelect(document.getElementById(`merge-${key}-channel`));
    updateMergeControlState(key);
  }
  bindMergePreviewEvents();
}
function populateFileSelect(select, names, emptyText) {
  const prior = select.value;
  select.innerHTML = "";
  const none = document.createElement("option");
  none.value = "";
  none.textContent = emptyText;
  select.appendChild(none);
  names.forEach((name, i) => {
    const option = document.createElement("option");
    option.value = String(i);
    option.textContent = name;
    select.appendChild(option);
  });
  select.value = [...select.options].some(option => option.value === prior) ? prior : "";
}
function populateMergeModeSelect(select, key) {
  if (select.options.length) return;
  const defaults = [
    ["default0", "默认 0 / 黑"],
    ["default255", "默认 255 / 白"],
    ["base", "保留基础图通道"],
    ["file", "使用来源文件通道"],
  ];
  defaults.forEach(([value, text]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = text;
    select.appendChild(option);
  });
  select.value = key === "a" ? "default255" : "default0";
  select.onchange = () => {
    updateMergeControlState(key);
    scheduleMergePreview();
  };
}
function populateSourceChannelSelect(select) {
  if (select.options.length) return;
  [
    ["gray", "灰度/Luma"],
    ["r", "R"],
    ["g", "G"],
    ["b", "B"],
    ["a", "A/Alpha"],
  ].forEach(([value, text]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = text;
    select.appendChild(option);
  });
}
function updateMergeControlState(key) {
  const mode = document.getElementById(`merge-${key}-mode`).value;
  document.getElementById(`merge-${key}-file`).disabled = mode !== "file";
  document.getElementById(`merge-${key}-channel`).disabled = mode !== "file";
}
function applyBaseToMergeChannels() {
  const base = document.getElementById("merge-base").value;
  for (const key of ["r", "g", "b", "a"]) {
    const mode = document.getElementById(`merge-${key}-mode`);
    const file = document.getElementById(`merge-${key}-file`);
    const channel = document.getElementById(`merge-${key}-channel`);
    if (!mode || !file || !channel) continue;
    if (base !== "") {
      mode.value = "base";
      file.value = base;
      channel.value = key;
    } else {
      mode.value = key === "a" ? "default255" : "default0";
      file.value = "";
      channel.value = "gray";
    }
    updateMergeControlState(key);
  }
  scheduleMergePreview();
}
function bindMergePreviewEvents() {
  const baseElement = document.getElementById("merge-base");
  if (baseElement && baseElement.dataset.baseBound !== "1") {
    baseElement.dataset.baseBound = "1";
    baseElement.addEventListener("change", applyBaseToMergeChannels);
  }
  const ids = [];
  for (const key of ["r", "g", "b", "a"]) ids.push(`merge-${key}-file`, `merge-${key}-channel`);
  for (const id of ids) {
    const element = document.getElementById(id);
    if (!element || element.dataset.previewBound === "1") continue;
    element.dataset.previewBound = "1";
    element.addEventListener("change", scheduleMergePreview);
  }
}
function renderPreviewSelector() {
  const names = inputMode() === "folder"
    ? folderFiles.map(item => item.relative || item.name)
    : files.map(file => file.webkitRelativePath || file.name);
  populateFileSelect(previewFile, names, "选择图片");
}
function renderNormalPreviewSelector() {
  const names = inputMode() === "folder"
    ? folderFiles.map(item => item.relative || item.name)
    : files.map(file => file.webkitRelativePath || file.name);
  populateFileSelect(normalPreviewFile, names, "选择图片");
}
function renderPbrPreviewSelector() {
  const names = inputMode() === "folder"
    ? folderFiles.map(item => item.relative || item.name)
    : files.map(file => file.webkitRelativePath || file.name);
  populateFileSelect(pbrPreviewFile, names, "选择图片");
}
function renderCropSelector() {
  const names = inputMode() === "folder"
    ? folderFiles.map(item => item.relative || item.name)
    : files.map(file => file.webkitRelativePath || file.name);
  populateFileSelect(cropSourceFile, names, "选择图片");
  if (cropSourceFile.value === "" && names.length) cropSourceFile.value = "0";
}
function updateChannelPreviewVisibility() {
  const visible = currentTool === "split" || currentTool === "merge";
  channelPreviewPanel.style.display = visible ? "block" : "none";
}
function previewSourceForm(index, fieldName = "file") {
  const form = new FormData();
  form.append("input_mode", inputMode());
  form.append("input", inputDir.value);
  form.append("index", index);
  if (inputMode() === "uploaded") {
    const file = files[Number(index)];
    if (!file) throw new Error("预览图片索引无效，请重新选择。");
    form.append(fieldName, file, file.webkitRelativePath || file.name);
  }
  return form;
}
function renderChannelPreview(result) {
  previewInfo.textContent = `${result.name} | ${result.width}x${result.height} | 图像模式 ${result.mode} | ${result.channel_mode} | ${result.has_alpha ? "有 Alpha" : "无 Alpha"} | 实际通道：${result.available_channels.join(", ")}`;
  previewGrid.innerHTML = "";
  updateSplitPreviews(result.previews || []);
  for (const item of result.previews || []) {
    const tile = document.createElement("div");
    tile.className = "preview-tile";
    const img = document.createElement("img");
    img.src = item.data_url;
    img.alt = item.label;
    const caption = document.createElement("div");
    caption.className = "preview-caption";
    const title = document.createElement("strong");
    title.textContent = item.label;
    caption.appendChild(title);
    const stats = document.createElement("span");
    stats.textContent = item.stats || "";
    caption.appendChild(stats);
    tile.appendChild(img);
    tile.appendChild(caption);
    previewGrid.appendChild(tile);
  }
}
function updateSplitPreviews(items) {
  const byKey = { l: null, r: null, g: null, b: null, a: null };
  for (const item of items) {
    const label = (item.label || "").toLowerCase();
    if (label === "l" || label.includes("luma") || label.includes("灰度")) byKey.l = item;
    if (label === "r") byKey.r = item;
    if (label === "g") byKey.g = item;
    if (label === "b") byKey.b = item;
    if (label.includes("alpha") || label === "a") byKey.a = item;
  }
  for (const key of ["l", "r", "g", "b", "a"]) {
    const img = document.getElementById(`split-${key}-preview-img`);
    const info = document.getElementById(`split-${key}-preview-info`);
    const item = byKey[key];
    setPreviewImage(img, item && item.data_url ? item.data_url : "");
    info.textContent = item ? `${item.label} | ${item.stats || ""}` : "当前图片无该通道";
  }
}
async function previewSelectedChannels() {
  const index = previewFile.value;
  if (index === "") {
    log("请先在通道预览里选择图片。");
    return;
  }
  previewRun.disabled = true;
  previewInfo.textContent = "正在生成通道预览...";
  previewGrid.innerHTML = "";
  try {
    const form = previewSourceForm(index);
    const response = await fetch("/preview-channels", { method: "POST", body: form });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "预览失败");
    renderChannelPreview(result);
  } catch (error) {
    previewInfo.textContent = `预览失败：${error.message}`;
    log(`通道预览失败：${error.message}`);
  } finally {
    previewRun.disabled = false;
  }
}
function updateNormalStrengthLabel() {
  normalStrengthValue.textContent = Number(normalStrength.value).toFixed(1);
}
function setComparePosition(value) {
  comparePosition = Math.max(0, Math.min(100, value));
  normalPreviewAfter.style.clipPath = `inset(0 0 0 ${comparePosition}%)`;
  normalCompareDivider.style.left = `${comparePosition}%`;
}
function updateCompareFromPointer(event) {
  const rect = normalCompareStage.getBoundingClientRect();
  if (!rect.width) return;
  setComparePosition((event.clientX - rect.left) / rect.width * 100);
}
normalCompareStage.addEventListener("pointerdown", event => {
  normalCompareStage.setPointerCapture(event.pointerId);
  updateCompareFromPointer(event);
});
normalCompareStage.addEventListener("pointermove", event => {
  if (normalCompareStage.hasPointerCapture(event.pointerId)) updateCompareFromPointer(event);
});
normalCompareStage.addEventListener("pointerup", event => {
  if (normalCompareStage.hasPointerCapture(event.pointerId)) normalCompareStage.releasePointerCapture(event.pointerId);
});
function setPbrComparePosition(value) {
  pbrComparePosition = Math.max(0, Math.min(100, value));
  pbrPreviewAfter.style.clipPath = `inset(0 0 0 ${pbrComparePosition}%)`;
  pbrCompareDivider.style.left = `${pbrComparePosition}%`;
}
function updatePbrCompareFromPointer(event) {
  const rect = pbrCompareStage.getBoundingClientRect();
  if (!rect.width) return;
  setPbrComparePosition((event.clientX - rect.left) / rect.width * 100);
}
pbrCompareStage.addEventListener("pointerdown", event => {
  pbrCompareStage.setPointerCapture(event.pointerId);
  updatePbrCompareFromPointer(event);
});
pbrCompareStage.addEventListener("pointermove", event => {
  if (pbrCompareStage.hasPointerCapture(event.pointerId)) updatePbrCompareFromPointer(event);
});
pbrCompareStage.addEventListener("pointerup", event => {
  if (pbrCompareStage.hasPointerCapture(event.pointerId)) pbrCompareStage.releasePointerCapture(event.pointerId);
});
async function previewNormalEffect() {
  const index = normalPreviewFile.value;
  if (index === "") {
    log("请先选择要预览的图片。");
    return;
  }
  normalPreviewRun.disabled = true;
  normalPreviewInfo.textContent = "正在生成强度预览...";
  try {
    const form = previewSourceForm(index);
    let response;
    if (strengthKind.value === "roughness") {
      form.append("strength", Number(roughnessStrength.value).toFixed(1));
      form.append("contrast", Number(roughnessContrast.value).toFixed(1));
      form.append("bias", Number(roughnessBias.value).toFixed(1));
      form.append("black", Number(roughnessBlack.value).toFixed(2));
      form.append("white", Number(roughnessWhite.value).toFixed(2));
      form.append("gamma", Number(roughnessGamma.value).toFixed(2));
      form.append("curve", Number(roughnessCurve.value).toFixed(1));
      form.append("invert", document.getElementById("roughness-invert").checked ? "1" : "0");
      response = await fetch("/preview-roughness", { method: "POST", body: form });
    } else {
      form.append("strength", Number(normalStrength.value).toFixed(1));
      form.append("flip_g", normalMode.value === "directx" ? "1" : "0");
      form.append("normal_mode", normalMode.value);
      response = await fetch("/preview-normal", { method: "POST", body: form });
    }
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "预览失败");
    normalCompareStage.style.aspectRatio = `${result.width} / ${result.height}`;
    setPreviewImage(normalPreviewBefore, result.before);
    setPreviewImage(normalPreviewAfter, result.after);
    normalPreviewInfo.textContent = strengthKind.value === "roughness"
      ? `${result.name} | ${result.width}x${result.height} | 黑白/粗糙度 | 强度 ${Number(result.strength).toFixed(1)} | 对比 ${Number(result.contrast).toFixed(1)} | 色阶 ${Number(result.black).toFixed(2)}-${Number(result.white).toFixed(2)} | Gamma ${Number(result.gamma).toFixed(2)} | 曲线 ${Number(result.curve).toFixed(1)}${result.invert ? " | 已反相" : ""}`
      : `${result.name} | ${result.width}x${result.height} | 法线 | 强度 ${Number(result.strength).toFixed(1)} | ${result.flip_g ? "DirectX / DX 模式" : "OpenGL 模式"}`;
    setComparePosition(comparePosition);
  } catch (error) {
    normalPreviewInfo.textContent = `预览失败：${error.message}`;
    log(`强度预览失败：${error.message}`);
  } finally {
    normalPreviewRun.disabled = false;
  }
}
function updateRoughnessLabels() {
  roughnessStrengthValue.textContent = Number(roughnessStrength.value).toFixed(1);
  roughnessContrastValue.textContent = Number(roughnessContrast.value).toFixed(1);
  roughnessBiasValue.textContent = Number(roughnessBias.value).toFixed(1);
  roughnessBlackValue.textContent = Number(roughnessBlack.value).toFixed(2);
  roughnessWhiteValue.textContent = Number(roughnessWhite.value).toFixed(2);
  roughnessGammaValue.textContent = Number(roughnessGamma.value).toFixed(2);
  roughnessCurveValue.textContent = Number(roughnessCurve.value).toFixed(1);
}
function resetRoughnessSliders() {
  roughnessStrength.value = "1.0";
  roughnessContrast.value = "1.0";
  roughnessBias.value = "0";
  roughnessBlack.value = "0";
  roughnessWhite.value = "1";
  roughnessGamma.value = "1";
  roughnessCurve.value = "0";
  document.getElementById("roughness-invert").checked = false;
  updateRoughnessLabels();
  normalPreviewInfo.textContent = "黑白/粗糙度滑杆已恢复默认值，可重新预览。";
}
function updateCompressQualityLabel() {
  compressQualityValue.textContent = String(Math.round(Number(compressQuality.value)));
}
function updateStrengthMode() {
  const roughnessMode = strengthKind.value === "roughness";
  normalOptions.style.display = roughnessMode ? "none" : "block";
  roughnessOptions.style.display = roughnessMode ? "block" : "none";
  normalPreviewInfo.textContent = roughnessMode
    ? "黑白/粗糙度模式：色阶和曲线会参与预览与导出，不会影响法线模式。"
    : "法线模式：只调整法线强度和 OpenGL/DX 方向，不应用黑白色阶/曲线。";
}
function updatePbrLabels() {
  pbrStrengthValue.textContent = Number(pbrStrength.value).toFixed(1);
  pbrRadiusValue.textContent = String(Math.round(Number(pbrRadius.value)));
  pbrDetailValue.textContent = Number(pbrDetail.value).toFixed(1);
  pbrSmoothValue.textContent = Number(pbrSmooth.value).toFixed(1);
  pbrStackValue.textContent = Number(pbrStack.value).toFixed(1);
}
function resetPbrSliders() {
  pbrStrength.value = "3.0";
  pbrRadius.value = "10";
  pbrDetail.value = "1.4";
  pbrSmooth.value = "0.6";
  pbrStack.value = "1.3";
  updatePbrLabels();
  pbrPreviewInfo.textContent = "PBR 滑杆已恢复默认值，可重新预览辅助图。";
}
async function previewPbrEffect() {
  const index = pbrPreviewFile.value;
  if (index === "") {
    log("请先选择要预览的 PBR 来源图。");
    return;
  }
  pbrPreviewRun.disabled = true;
  pbrPreviewInfo.textContent = "正在生成 PBR 辅助预览...";
  try {
    const form = previewSourceForm(index);
    form.append("source_type", pbrSourceType.value);
    form.append("mode", pbrMode.value);
    form.append("strength", Number(pbrStrength.value).toFixed(1));
    form.append("radius", String(Math.round(Number(pbrRadius.value))));
    form.append("detail", Number(pbrDetail.value).toFixed(1));
    form.append("smooth", Number(pbrSmooth.value).toFixed(1));
    form.append("stack", Number(pbrStack.value).toFixed(1));
    form.append("normal_mode", pbrNormalMode.value);
    form.append("invert", document.getElementById("pbr-invert").checked ? "1" : "0");
    const response = await fetch("/preview-pbr", { method: "POST", body: form });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "预览失败");
    pbrCompareStage.style.aspectRatio = `${result.width} / ${result.height}`;
    setPreviewImage(pbrPreviewBefore, result.before);
    setPreviewImage(pbrPreviewAfter, result.after);
    pbrPreviewInfo.textContent = `${result.name} | ${result.width}x${result.height} | ${result.label} | 强度 ${Number(result.strength).toFixed(1)} | 半径 ${result.radius} | 细节 ${Number(result.detail).toFixed(1)} | 平滑 ${Number(result.smooth).toFixed(1)} | 叠加 ${Number(result.stack).toFixed(1)}`;
    setPbrComparePosition(pbrComparePosition);
  } catch (error) {
    pbrPreviewInfo.textContent = `预览失败：${error.message}`;
    log(`PBR 预览失败：${error.message}`);
  } finally {
    pbrPreviewRun.disabled = false;
  }
}
function appendMergeSources(form) {
  form.append("input_mode", inputMode());
  form.append("input", inputDir.value);
  if (inputMode() === "uploaded") {
    for (const file of files) form.append("files", file, file.webkitRelativePath || file.name);
  }
}
function appendMergeOptions(form) {
  form.append("base", document.getElementById("merge-base").value);
  form.append("channel_mode", channelMode.value);
  for (const key of ["r", "g", "b", "a"]) {
    form.append(`${key}_mode`, document.getElementById(`merge-${key}-mode`).value);
    form.append(`${key}_file`, document.getElementById(`merge-${key}-file`).value);
    form.append(`${key}_channel`, document.getElementById(`merge-${key}-channel`).value);
  }
}
function appendRenameOptions(form) {
  form.append("format", document.getElementById("rename-format").value);
  form.append("rename_steps", JSON.stringify(getRenameSteps()));
}
function updateRenameStepFields(card) {
  const op = (card.querySelector(".rename-step-op:checked") || {}).value || "";
  const visible = {
    find: op === "replace",
    replace: op === "replace",
    prefix: op === "prefix",
    suffix: op === "suffix",
    left: op === "insert",
    insert: op === "insert",
    right: op === "insert",
  };
  card.querySelectorAll("[data-field]").forEach(field => {
    field.style.display = visible[field.dataset.field] ? "inline-flex" : "none";
  });
}
function renumberRenameSteps() {
  [...renameSteps.querySelectorAll(".rename-step-card")].forEach((card, i) => {
    card.querySelector(".rename-step-title").textContent = `步骤 ${i + 1}`;
    card.querySelectorAll(".rename-step-op").forEach(radio => {
      radio.name = `rename-step-op-${i}`;
    });
    card.querySelector(".rename-step-delete").disabled = renameSteps.children.length <= 1;
  });
}
function addRenameStep(defaultOp = "replace") {
  const card = renameStepTemplate.content.firstElementChild.cloneNode(true);
  card.querySelectorAll(".rename-step-op").forEach(radio => {
    radio.checked = radio.value === defaultOp;
    radio.onchange = () => updateRenameStepFields(card);
  });
  card.querySelector(".rename-step-delete").onclick = () => {
    if (renameSteps.children.length <= 1) return;
    card.remove();
    renumberRenameSteps();
  };
  renameSteps.appendChild(card);
  updateRenameStepFields(card);
  renumberRenameSteps();
}
function getRenameSteps() {
  return [...renameSteps.querySelectorAll(".rename-step-card")].map(card => {
    const op = (card.querySelector(".rename-step-op:checked") || {}).value || "replace";
    return {
      op,
      find: card.querySelector(".rename-step-find").value,
      replace: card.querySelector(".rename-step-replace").value,
      prefix: card.querySelector(".rename-step-prefix").value,
      suffix: card.querySelector(".rename-step-suffix").value,
      left: card.querySelector(".rename-step-left").value,
      right: card.querySelector(".rename-step-right").value,
      insert: card.querySelector(".rename-step-insert").value,
    };
  });
}
function appendRenameRow(parent, cells, className = "") {
  const row = document.createElement("div");
  row.className = `preview-row ${className}`.trim();
  for (const text of cells) {
    const cell = document.createElement("div");
    cell.textContent = text;
    row.appendChild(cell);
  }
  parent.appendChild(row);
}
function renderRenamePreview(result) {
  renamePreviewList.innerHTML = "";
  appendRenameRow(renamePreviewList, ["原文件名", "新文件名", "贴图类型", "状态"], "header");
  for (const item of result.items || []) {
    appendRenameRow(
      renamePreviewList,
      [item.source, item.target, item.texture_type || "未识别", item.conflict ? "冲突" : "可用"],
      item.conflict ? "conflict" : ""
    );
  }
  const items = result.items || [];
  const conflicts = items.filter(item => item.conflict).length;
  renamePreviewInfo.textContent = conflicts ? `发现 ${conflicts} 个命名冲突，请调整规则后再执行。` : `已预览 ${items.length} 个文件，未发现命名冲突。`;
}
async function previewRenamePlan() {
  let count = 0;
  if (inputMode() === "folder") {
    await refreshFolderFiles(true);
    count = folderFiles.length;
  } else {
    count = files.length;
  }
  if (!count) {
    log("请先添加或扫描图片后再预览命名。");
    return;
  }
  renamePreviewRun.disabled = true;
  renamePreviewInfo.textContent = "正在生成命名预览...";
  try {
    const form = new FormData();
    appendCommon(form);
    appendRenameOptions(form);
    const response = await fetch("/preview-rename", { method: "POST", body: form });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "预览失败");
    renderRenamePreview(result);
  } catch (error) {
    renamePreviewInfo.textContent = `预览失败：${error.message}`;
    log(`重命名预览失败：${error.message}`);
  } finally {
    renamePreviewRun.disabled = false;
  }
}
async function loadCropPreview() {
  const index = cropSourceFile.value;
  if (index === "") {
    cropInfo.textContent = "请先选择要显示的裁切图片。";
    setPreviewImage(cropPreviewImg, "");
    cropPreviewMeta = null;
    return false;
  }
  cropLoadPreview.disabled = true;
  cropInfo.textContent = "正在加载裁切显示图...";
  try {
    const form = previewSourceForm(index);
    const response = await fetch("/preview-crop", { method: "POST", body: form });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "加载失败");
    cropPreviewMeta = result;
    setPreviewImage(cropPreviewImg, result.image);
    cropEditorImg.src = result.image;
    cropInfo.textContent = `${result.name} | ${result.width}x${result.height}`;
    if (cropPreviewImg.complete) renderCropCards();
    return true;
  } catch (error) {
    cropInfo.textContent = `裁切显示图加载失败：${error.message}`;
    log(`裁切显示图加载失败：${error.message}`);
    return false;
  } finally {
    cropLoadPreview.disabled = false;
  }
}
function renderCropCards() {
  cropCards.innerHTML = "";
  cropItems.forEach((item, i) => {
    const card = document.createElement("div");
    card.className = "crop-card";
    const head = document.createElement("div");
    head.className = "section-head";
    const title = document.createElement("strong");
    title.textContent = `裁切 ${i + 1}`;
    const del = document.createElement("button");
    del.className = "mini-button";
    del.type = "button";
    del.textContent = `删除裁切 ${i + 1}`;
    del.onclick = () => {
      cropItems.splice(i, 1);
      renderCropCards();
    };
    head.appendChild(title);
    head.appendChild(del);
    const body = document.createElement("div");
    body.className = "crop-card-body";
    const thumb = document.createElement("img");
    thumb.className = "crop-thumb";
    thumb.alt = `裁切 ${i + 1} 预览`;
    const thumbSrc = cropThumbFromDraft(item);
    if (thumbSrc) {
      thumb.src = thumbSrc;
      thumb.onclick = () => openCropZoom(cropThumbFromDraft(item) || thumbSrc);
    }
    const row = document.createElement("div");
    row.className = "row";
    const label = document.createElement("label");
    label.textContent = "命名模板 ";
    const input = document.createElement("input");
    input.type = "text";
    input.value = item.name;
    input.oninput = () => { item.name = input.value; };
    label.appendChild(input);
    const note = document.createElement("div");
    note.className = "template-note";
    note.textContent = "{name}占位符为源图原文件名；修改 crop1 会改变裁切编号或部位名，例如 {name}_face 会输出 原名_face。多图同位置裁切时，模板不含 {name} 会自动补源图名避免同格式图片互相覆盖。";
    const info = document.createElement("span");
    info.className = "muted";
    info.textContent = `位置 ${(item.x * 100).toFixed(1)}%, ${(item.y * 100).toFixed(1)}% | 大小 ${(item.w * 100).toFixed(1)}% x ${(item.h * 100).toFixed(1)}%`;
    row.appendChild(label);
    row.appendChild(note);
    row.appendChild(info);
    card.appendChild(head);
    body.appendChild(thumb);
    body.appendChild(row);
    card.appendChild(body);
    cropCards.appendChild(card);
  });
}
function cropEditorRect() {
  return cropEditor.getBoundingClientRect();
}
function cropImageRect() {
  return cropEditorImg.getBoundingClientRect();
}
function cropFitScale() {
  const editorRect = cropEditorRect();
  const natural = cropNaturalSize();
  const scale = Math.min(editorRect.width / natural.width, editorRect.height / natural.height, 1);
  return Math.max(0.01, Number.isFinite(scale) ? scale : 1);
}
function cropScaledSize(scale = cropView.scale) {
  const natural = cropNaturalSize();
  return {
    width: natural.width * scale,
    height: natural.height * scale,
  };
}
function cropClampedOffset(offset, viewportSize, contentSize) {
  const margin = 90;
  if (contentSize <= viewportSize) return (viewportSize - contentSize) / 2;
  return clampNumber(offset, viewportSize - contentSize - margin, margin);
}
function clampCropView() {
  const editorRect = cropEditorRect();
  const size = cropScaledSize();
  cropView.x = cropClampedOffset(cropView.x, editorRect.width, size.width);
  cropView.y = cropClampedOffset(cropView.y, editorRect.height, size.height);
}
function updateCropViewControls() {
  cropEditor.classList.toggle("pan-mode", cropView.panMode);
  cropEditor.classList.toggle("space-pan", cropSpacePan);
  cropViewPan.classList.toggle("active", cropView.panMode);
  cropViewPan.setAttribute("aria-pressed", cropView.panMode ? "true" : "false");
  cropViewStatus.textContent = `${Math.round(cropView.scale * 100)}%`;
  if (cropOverlay.classList.contains("open")) updateCropActionControls();
}
function applyCropView(renderDraft = true) {
  const size = cropScaledSize();
  cropEditorImg.style.width = `${Math.max(1, size.width)}px`;
  cropEditorImg.style.height = `${Math.max(1, size.height)}px`;
  cropEditorImg.style.transform = `translate(${cropView.x}px, ${cropView.y}px)`;
  updateCropViewControls();
  if (renderDraft) renderCropDraftBox();
}
function fitCropView() {
  const editorRect = cropEditorRect();
  cropView.fitScale = cropFitScale();
  cropView.scale = cropView.fitScale;
  const size = cropScaledSize();
  cropView.x = (editorRect.width - size.width) / 2;
  cropView.y = (editorRect.height - size.height) / 2;
  applyCropView();
}
function setCropViewScale(scale, clientX, clientY) {
  const editorRect = cropEditorRect();
  const oldScale = cropView.scale || cropView.fitScale || 1;
  const minScale = cropView.fitScale || cropFitScale();
  const maxScale = Math.max(8, minScale);
  const nextScale = clampNumber(scale, minScale, maxScale);
  const anchorX = Number.isFinite(clientX) ? clientX - editorRect.left : editorRect.width / 2;
  const anchorY = Number.isFinite(clientY) ? clientY - editorRect.top : editorRect.height / 2;
  const imageX = (anchorX - cropView.x) / oldScale;
  const imageY = (anchorY - cropView.y) / oldScale;
  cropView.scale = nextScale;
  cropView.x = anchorX - imageX * nextScale;
  cropView.y = anchorY - imageY * nextScale;
  clampCropView();
  applyCropView();
}
function setCropViewScaleFromCenter(scale) {
  const editorRect = cropEditorRect();
  setCropViewScale(scale, editorRect.left + editorRect.width / 2, editorRect.top + editorRect.height / 2);
}
function captureCropInput(event) {
  if (typeof event.pointerId === "number" && cropEditor.setPointerCapture) {
    cropEditor.setPointerCapture(event.pointerId);
  }
}
function releaseCropInput(event) {
  if (typeof event.pointerId === "number" && cropEditor.hasPointerCapture && cropEditor.hasPointerCapture(event.pointerId)) {
    cropEditor.releasePointerCapture(event.pointerId);
  }
}
function startCropPan(event) {
  event.preventDefault();
  captureCropInput(event);
  cropPanState = {
    x: cropView.x,
    y: cropView.y,
    clientX: event.clientX,
    clientY: event.clientY,
  };
  cropDragStart = null;
  cropResizeState = null;
  cropEditor.classList.add("panning");
}
function updateCropPan(event) {
  if (!cropPanState) return;
  cropView.x = cropPanState.x + event.clientX - cropPanState.clientX;
  cropView.y = cropPanState.y + event.clientY - cropPanState.clientY;
  clampCropView();
  applyCropView();
}
function finishCropPan() {
  cropPanState = null;
  cropEditor.classList.remove("panning");
}
function cropPanRequested(event) {
  return cropView.panMode || cropSpacePan || event.button === 1 || event.buttons === 4;
}
function updateCropDragFromEvent(event) {
  if (cropPanState) {
    updateCropPan(event);
    return;
  }
  const point = editorPoint(event);
  if (cropResizeState) {
    updateCropBoxFromResize(point);
  } else if (cropDragStart) {
    updateCropBoxFromPoints(cropDragStart, point);
  }
}
function editorPoint(event) {
  const rect = cropImageRect();
  return {
    x: Math.max(0, Math.min(rect.width, event.clientX - rect.left)),
    y: Math.max(0, Math.min(rect.height, event.clientY - rect.top)),
    rect,
  };
}
function cropDraftToPixels(draft, rect) {
  return {
    left: draft.x * rect.width,
    top: draft.y * rect.height,
    right: (draft.x + draft.w) * rect.width,
    bottom: (draft.y + draft.h) * rect.height,
  };
}
function clampNumber(value, low, high) {
  return Math.max(low, Math.min(high, value));
}
function cropShapeMode() {
  return document.querySelector('input[name="crop-shape-mode"]:checked')?.value || "free";
}
function cropNaturalSize() {
  return {
    width: Math.max(1, Number(cropPreviewMeta && cropPreviewMeta.width) || cropEditorImg.naturalWidth || 1),
    height: Math.max(1, Number(cropPreviewMeta && cropPreviewMeta.height) || cropEditorImg.naturalHeight || 1),
  };
}
function customCropNormalizedSize() {
  const natural = cropNaturalSize();
  const width = clampNumber(Math.round(Number(cropCustomWidth.value) || 1), 1, natural.width);
  const height = clampNumber(Math.round(Number(cropCustomHeight.value) || 1), 1, natural.height);
  cropCustomWidth.value = String(width);
  cropCustomHeight.value = String(height);
  return { w: width / natural.width, h: height / natural.height };
}
function clampCropDraft(draft) {
  const w = clampNumber(draft.w, 0.0001, 1);
  const h = clampNumber(draft.h, 0.0001, 1);
  return {
    x: clampNumber(draft.x, 0, 1 - w),
    y: clampNumber(draft.y, 0, 1 - h),
    w,
    h,
  };
}
function setCustomCropAtPoint(point) {
  const size = customCropNormalizedSize();
  const cx = point.x / point.rect.width;
  const cy = point.y / point.rect.height;
  cropDraft = clampCropDraft({ x: cx - size.w / 2, y: cy - size.h / 2, w: size.w, h: size.h });
  renderCropDraftBox(point.rect);
}
function updateCropActionControls() {
  const mode = cropShapeMode();
  cropCustomPixels.style.display = mode === "custom" ? "inline-flex" : "none";
  cropHint.style.display = cropDraft || cropView.panMode || cropSpacePan ? "none" : "block";
}
function applyCropShapeModeToDraft() {
  updateCropActionControls();
  if (!cropDraft) return;
  if (cropShapeMode() === "square") {
    const side = Math.min(cropDraft.w, cropDraft.h);
    const cx = cropDraft.x + cropDraft.w / 2;
    const cy = cropDraft.y + cropDraft.h / 2;
    cropDraft = clampCropDraft({ x: cx - side / 2, y: cy - side / 2, w: side, h: side });
  } else if (cropShapeMode() === "custom") {
    const size = customCropNormalizedSize();
    const cx = cropDraft.x + cropDraft.w / 2;
    const cy = cropDraft.y + cropDraft.h / 2;
    cropDraft = clampCropDraft({ x: cx - size.w / 2, y: cy - size.h / 2, w: size.w, h: size.h });
  }
  renderCropDraftBox();
}
function setCropDraftFromPixels(edges, rect) {
  cropDraft = clampCropDraft({
    x: edges.left / rect.width,
    y: edges.top / rect.height,
    w: (edges.right - edges.left) / rect.width,
    h: (edges.bottom - edges.top) / rect.height,
  });
}
function renderCropDraftBox(rect = cropImageRect()) {
  updateCropActionControls();
  if (!cropDraft || !rect.width || !rect.height) return;
  const editorRect = cropEditor.getBoundingClientRect();
  const box = cropDraftToPixels(cropDraft, rect);
  const x = box.left;
  const y = box.top;
  const w = box.right - box.left;
  const h = box.bottom - box.top;
  cropBox.style.display = w > 2 && h > 2 ? "block" : "none";
  cropBox.style.left = `${rect.left - editorRect.left + x}px`;
  cropBox.style.top = `${rect.top - editorRect.top + y}px`;
  cropBox.style.width = `${w}px`;
  cropBox.style.height = `${h}px`;
  const actionX = clampNumber(rect.left - editorRect.left + x + w / 2, 160, Math.max(160, editorRect.width - 160));
  const belowY = rect.top - editorRect.top + y + h + 10;
  const aboveY = rect.top - editorRect.top + y - 72;
  const actionY = belowY > editorRect.height - 86 && aboveY > 8
    ? aboveY
    : clampNumber(belowY, 8, Math.max(8, editorRect.height - 86));
  cropActions.style.left = `${actionX}px`;
  cropActions.style.top = `${actionY}px`;
  cropActions.style.display = w > 8 && h > 8 ? "flex" : "none";
}
function updateCropBoxFromPoints(start, point) {
  const rect = point.rect;
  if (cropShapeMode() === "custom") {
    setCustomCropAtPoint(point);
    return;
  }
  let x2 = point.x;
  let y2 = point.y;
  if (cropShapeMode() === "square") {
    const sx = x2 < start.x ? -1 : 1;
    const sy = y2 < start.y ? -1 : 1;
    const maxX = sx < 0 ? start.x : rect.width - start.x;
    const maxY = sy < 0 ? start.y : rect.height - start.y;
    const side = clampNumber(Math.max(Math.abs(x2 - start.x), Math.abs(y2 - start.y)), 0, Math.min(maxX, maxY));
    x2 = start.x + sx * side;
    y2 = start.y + sy * side;
  }
  const x = Math.min(start.x, x2);
  const y = Math.min(start.y, y2);
  const w = Math.abs(x2 - start.x);
  const h = Math.abs(y2 - start.y);
  cropDraft = {
    x: x / rect.width,
    y: y / rect.height,
    w: w / rect.width,
    h: h / rect.height,
  };
  renderCropDraftBox(rect);
}
function cropEdgeFromEvent(event) {
  if (cropShapeMode() === "custom") return "move";
  const rect = cropBox.getBoundingClientRect();
  const tolerance = 12;
  const nearLeft = Math.abs(event.clientX - rect.left) <= tolerance;
  const nearRight = Math.abs(event.clientX - rect.right) <= tolerance;
  const nearTop = Math.abs(event.clientY - rect.top) <= tolerance;
  const nearBottom = Math.abs(event.clientY - rect.bottom) <= tolerance;
  if (nearTop && nearLeft) return "nw";
  if (nearTop && nearRight) return "ne";
  if (nearBottom && nearLeft) return "sw";
  if (nearBottom && nearRight) return "se";
  if (nearLeft) return "w";
  if (nearRight) return "e";
  if (nearTop) return "n";
  if (nearBottom) return "s";
  return "";
}
function cropEdgeCursor(edge) {
  return ({
    n: "ns-resize",
    s: "ns-resize",
    e: "ew-resize",
    w: "ew-resize",
    ne: "nesw-resize",
    sw: "nesw-resize",
    nw: "nwse-resize",
    se: "nwse-resize",
  })[edge] || "move";
}
function updateCropBoxFromResize(point) {
  if (!cropResizeState) return;
  const rect = point.rect;
  const minSize = 8;
  const edge = cropResizeState.edge;
  if (cropShapeMode() === "custom" && edge !== "move") {
    cropResizeState.edge = "move";
    cropBox.style.cursor = "move";
    updateCropBoxFromResize(point);
    return;
  }
  if (edge === "move") {
    const dx = (point.x - cropResizeState.point.x) / rect.width;
    const dy = (point.y - cropResizeState.point.y) / rect.height;
    cropDraft = {
      ...cropResizeState.draft,
      x: Math.max(0, Math.min(1 - cropResizeState.draft.w, cropResizeState.draft.x + dx)),
      y: Math.max(0, Math.min(1 - cropResizeState.draft.h, cropResizeState.draft.y + dy)),
    };
    renderCropDraftBox(rect);
    return;
  }
  if (cropShapeMode() === "square") {
    const start = cropDraftToPixels(cropResizeState.draft, rect);
    let edges = { ...start };
    if (edge.length === 2) {
      const fixedX = edge.includes("w") ? start.right : start.left;
      const fixedY = edge.includes("n") ? start.bottom : start.top;
      const maxX = edge.includes("w") ? fixedX : rect.width - fixedX;
      const maxY = edge.includes("n") ? fixedY : rect.height - fixedY;
      const side = clampNumber(Math.max(Math.abs(point.x - fixedX), Math.abs(point.y - fixedY)), minSize, Math.min(maxX, maxY));
      edges.left = edge.includes("w") ? fixedX - side : fixedX;
      edges.right = edge.includes("w") ? fixedX : fixedX + side;
      edges.top = edge.includes("n") ? fixedY - side : fixedY;
      edges.bottom = edge.includes("n") ? fixedY : fixedY + side;
    } else if (edge === "e" || edge === "w") {
      const fixedX = edge === "w" ? start.right : start.left;
      const centerY = (start.top + start.bottom) / 2;
      const maxX = edge === "w" ? fixedX : rect.width - fixedX;
      const maxY = 2 * Math.min(centerY, rect.height - centerY);
      const side = clampNumber(Math.abs(point.x - fixedX), minSize, Math.min(maxX, maxY));
      edges.left = edge === "w" ? fixedX - side : fixedX;
      edges.right = edge === "w" ? fixedX : fixedX + side;
      edges.top = centerY - side / 2;
      edges.bottom = centerY + side / 2;
    } else {
      const fixedY = edge === "n" ? start.bottom : start.top;
      const centerX = (start.left + start.right) / 2;
      const maxY = edge === "n" ? fixedY : rect.height - fixedY;
      const maxX = 2 * Math.min(centerX, rect.width - centerX);
      const side = clampNumber(Math.abs(point.y - fixedY), minSize, Math.min(maxX, maxY));
      edges.top = edge === "n" ? fixedY - side : fixedY;
      edges.bottom = edge === "n" ? fixedY : fixedY + side;
      edges.left = centerX - side / 2;
      edges.right = centerX + side / 2;
    }
    setCropDraftFromPixels(edges, rect);
    renderCropDraftBox(rect);
    return;
  }
  const edges = cropDraftToPixels(cropResizeState.draft, rect);
  if (edge.includes("w")) edges.left = Math.min(Math.max(0, point.x), edges.right - minSize);
  if (edge.includes("e")) edges.right = Math.max(Math.min(rect.width, point.x), edges.left + minSize);
  if (edge.includes("n")) edges.top = Math.min(Math.max(0, point.y), edges.bottom - minSize);
  if (edge.includes("s")) edges.bottom = Math.max(Math.min(rect.height, point.y), edges.top + minSize);
  setCropDraftFromPixels(edges, rect);
  renderCropDraftBox(rect);
}
function alignCropDraft(anchor) {
  if (!cropDraft) return;
  const horizontal = anchor[1] || "c";
  const vertical = anchor[0] || "m";
  let x = cropDraft.x;
  let y = cropDraft.y;
  if (horizontal === "l") x = 0;
  else if (horizontal === "c") x = (1 - cropDraft.w) / 2;
  else if (horizontal === "r") x = 1 - cropDraft.w;
  if (vertical === "t") y = 0;
  else if (vertical === "m") y = (1 - cropDraft.h) / 2;
  else if (vertical === "b") y = 1 - cropDraft.h;
  cropDraft = clampCropDraft({ ...cropDraft, x, y });
  renderCropDraftBox();
}
function cropThumbFromDraft(draft) {
  const source = cropPreviewImg.naturalWidth ? cropPreviewImg : cropEditorImg;
  if (!draft || !source.naturalWidth || !source.naturalHeight) return "";
  const sx = Math.max(0, Math.round(draft.x * source.naturalWidth));
  const sy = Math.max(0, Math.round(draft.y * source.naturalHeight));
  const sw = Math.max(1, Math.round(draft.w * source.naturalWidth));
  const sh = Math.max(1, Math.round(draft.h * source.naturalHeight));
  const maxSize = 240;
  const scale = Math.min(maxSize / sw, maxSize / sh, 1);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(sw * scale));
  canvas.height = Math.max(1, Math.round(sh * scale));
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(source, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/png");
}
function openCropZoom(src) {
  if (!src) return;
  cropZoomImg.src = src;
  cropZoom.classList.add("open");
}
function closeCropEditor() {
  cropOverlay.classList.remove("open");
  cropBox.style.display = "none";
  cropActions.style.display = "none";
  cropHint.style.display = "none";
  cropDragStart = null;
  cropResizeState = null;
  finishCropPan();
  cropSpacePan = false;
  cropView.panMode = false;
  updateCropViewControls();
  cropDraft = null;
}
async function openCropEditor() {
  if (!cropPreviewMeta) {
    const ok = await loadCropPreview();
    if (!ok) return;
  }
  cropEditorImg.src = cropPreviewMeta.image;
  cropOverlay.classList.add("open");
  cropBox.style.display = "none";
  cropActions.style.display = "none";
  cropHint.style.display = "block";
  cropResizeState = null;
  cropDragStart = null;
  finishCropPan();
  cropSpacePan = false;
  cropView.panMode = false;
  cropDraft = null;
  updateCropActionControls();
  requestAnimationFrame(fitCropView);
}
function confirmCropDraft() {
  if (!cropDraft || cropDraft.w <= 0.002 || cropDraft.h <= 0.002) return;
  cropItems.push({
    ...cropDraft,
    name: `{name}_crop${cropItems.length + 1}`,
  });
  renderCropCards();
  closeCropEditor();
}
function appendCropOptions(form) {
  form.append("crop_mode", document.querySelector('input[name="crop-mode"]:checked').value);
  form.append("crop_source_index", cropSourceFile.value);
  form.append("format", document.getElementById("crop-format").value);
  form.append("crops", JSON.stringify(cropItems.map(item => ({
    x: item.x,
    y: item.y,
    w: item.w,
    h: item.h,
    name: item.name,
  }))));
}
function setInlinePreview(key, item) {
  const img = document.getElementById(`merge-${key}-preview-img`);
  const info = document.getElementById(`merge-${key}-preview-info`);
  setPreviewImage(img, item && item.data_url ? item.data_url : "");
  info.textContent = item && item.label ? `${item.label} | ${item.stats || ""}` : "未预览";
}
function renderMergePreview(result) {
  for (const key of ["r", "g", "b", "a"]) setInlinePreview(key, result.channels[key]);
  setPreviewImage(mergeCompositePreviewImg, result.composite.data_url);
  mergeCompositePreviewInfo.textContent = `${result.width}x${result.height} | ${result.composite.label}`;
}
async function previewMergeComposite(showLog = true) {
  const count = inputMode() === "folder" ? folderFiles.length : files.length;
  if (!count) {
    if (showLog) log("请先添加或扫描图片后再预览合成图。");
    return;
  }
  mergePreviewRun.disabled = true;
  try {
    const form = new FormData();
    appendMergeSources(form);
    appendMergeOptions(form);
    const response = await fetch("/preview-merge", { method: "POST", body: form });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "预览失败");
    renderMergePreview(result);
  } catch (error) {
    mergeCompositePreviewInfo.textContent = `预览失败：${error.message}`;
    if (showLog) log(`合成预览失败：${error.message}`);
  } finally {
    mergePreviewRun.disabled = false;
  }
}
function scheduleMergePreview() {
  if (currentTool !== "merge") return;
  clearTimeout(mergePreviewTimer);
  mergePreviewTimer = setTimeout(() => previewMergeComposite(false), 350);
}
function setInputMode(mode) {
  const radio = document.querySelector(`input[name="input-mode"][value="${mode}"]`);
  if (radio) radio.checked = true;
  updateInputMode();
}
function updateInputMode() {
  const folderMode = inputMode() === "folder";
  inputDir.disabled = !folderMode;
  refreshInput.disabled = !folderMode;
  renderFiles();
  updateSourceWarning();
}

function setAppMode(mode) {
  const workflow = mode === "workflow";
  quickModeView.hidden = workflow;
  workflowModeView.hidden = !workflow;
  quickModeView.classList.toggle("active", !workflow);
  workflowModeView.classList.toggle("active", workflow);
  modeButtons.forEach(button => {
    const active = button.dataset.mode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });
  if (workflow) renderWorkflowShell();
}

function rememberVisibleOutputPath() {
  if (outputBox.value && outputBox.value !== outputBox.dataset.default && outputBox.value !== "源文件所在文件夹") {
    customOutputValue = outputBox.value;
  }
}

function updateOutputMode() {
  const mode = outputMode();
  const customMode = mode === "custom";
  const askMode = mode === "ask";
  outputBox.disabled = !customMode;
  if (customMode) {
    outputBox.value = customOutputValue || outputBox.dataset.default;
  } else if (askMode) {
    rememberVisibleOutputPath();
    outputBox.value = askOutputValue || outputBox.dataset.default;
  } else if (mode === "source") {
    rememberVisibleOutputPath();
    outputBox.value = "源文件所在文件夹";
  } else {
    rememberVisibleOutputPath();
    outputBox.value = outputBox.dataset.default;
  }
  updateSourceWarning();
}

async function clearDefaultOutputFiles() {
  const ok = window.confirm("确认清空默认输出文件夹中的所有文件？\n不会影响源文件、自定义输出目录或源文件位置导出的文件。");
  if (!ok) return;
  try {
    clearDefaultOutput.disabled = true;
    const response = await fetch("/clear-default-output", { method: "POST" });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "清空默认输出文件夹失败");
    log(`已清空默认输出文件夹：${result.removed} 项。`);
  } catch (error) {
    log(`清空默认输出文件夹失败：${error.message}`);
  } finally {
    clearDefaultOutput.disabled = false;
  }
}

async function chooseOutputDirectoryIfNeeded() {
  if (outputMode() !== "ask") return true;
  setRunProgress(8, "请选择本次导出文件夹...");
  const form = new FormData();
  form.append("current", askOutputValue || outputBox.value || outputBox.dataset.default);
  const response = await fetch("/choose-output-dir", { method: "POST", body: form });
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error || "选择输出目录失败");
  if (result.cancelled) return false;
  askOutputValue = result.path;
  outputBox.value = result.path;
  return true;
}
async function refreshFolderFiles(silent = false) {
  if (inputMode() !== "folder") {
    folderFiles = [];
    renderFiles();
    return true;
  }
  const source = inputDir.value.trim();
  if (!source) {
    folderFiles = [];
    renderFiles();
    if (!silent) log("请先填写自定义输入目录。");
    return false;
  }
  const params = new URLSearchParams({ input: source });
  try {
    const response = await fetch(`/list-input?${params.toString()}`);
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "扫描失败");
    folderFiles = result.files || [];
    renderFiles();
    if (!silent) log(`已扫描 ${folderFiles.length} 个文件：${result.input}`);
    return folderFiles.length > 0;
  } catch (error) {
    folderFiles = [];
    renderFiles();
    if (!silent) log(`扫描失败：${error.message}`);
    return false;
  }
}
function addFiles(list) {
  let added = 0;
  for (const file of list) {
    const ext = file.name.split(".").pop().toLowerCase();
    if (!allowed.has(ext)) continue;
    const key = `${file.webkitRelativePath || file.name}|${file.size}|${file.lastModified}`;
    if (files.some(f => `${f.webkitRelativePath || f.name}|${f.size}|${f.lastModified}` === key)) continue;
    files.push(file);
    added++;
  }
  if (added) setInputMode("uploaded");
  renderFiles();
  log(added ? `已添加 ${added} 个文件。` : "没有发现新的支持格式图片。");
}
async function readEntry(entry) {
  if (entry.isFile) return await new Promise(resolve => entry.file(file => resolve([file]), () => resolve([])));
  if (!entry.isDirectory) return [];
  const reader = entry.createReader();
  const out = [];
  while (true) {
    const batch = await new Promise(resolve => reader.readEntries(resolve, () => resolve([])));
    if (!batch.length) break;
    for (const child of batch) out.push(...await readEntry(child));
  }
  return out;
}
function droppedFileKey(file) {
  return `${file.webkitRelativePath || file.name}|${file.size}|${file.lastModified}`;
}
function pushUniqueDroppedFile(out, seen, file) {
  if (!file || !file.name) return;
  const key = droppedFileKey(file);
  if (seen.has(key)) return;
  seen.add(key);
  out.push(file);
}
async function collectDropFiles(event) {
  const items = [...event.dataTransfer.items || []];
  const out = [];
  const seen = new Set();
  const entries = [];
  for (const item of items) {
    if (item.kind && item.kind !== "file") continue;
    const entry = item.webkitGetAsEntry && item.webkitGetAsEntry();
    if (entry && entry.isDirectory) {
      entries.push(entry);
    }
    else {
      pushUniqueDroppedFile(out, seen, item.getAsFile && item.getAsFile());
      if (entry && entry.isFile) entries.push(entry);
    }
  }
  for (const file of [...event.dataTransfer.files || []]) pushUniqueDroppedFile(out, seen, file);
  for (const entry of entries) {
    for (const file of await readEntry(entry)) pushUniqueDroppedFile(out, seen, file);
  }
  return out;
}
drop.addEventListener("dragover", event => {
  event.preventDefault();
  drop.classList.add("active");
});
drop.addEventListener("dragleave", () => drop.classList.remove("active"));
drop.addEventListener("drop", async event => {
  event.preventDefault();
  drop.classList.remove("active");
  addFiles(await collectDropFiles(event));
});
document.getElementById("pick").onclick = () => picker.click();
picker.onchange = () => {
  addFiles([...picker.files]);
  picker.value = "";
};
cropLoadPreview.onclick = loadCropPreview;
cropAdd.onclick = openCropEditor;
cropPreviewImg.addEventListener("load", renderCropCards);
cropSourceFile.onchange = () => {
  cropPreviewMeta = null;
  loadCropPreview();
};
document.querySelectorAll('input[name="crop-mode"]').forEach(radio => {
  radio.onchange = () => {
    cropInfo.textContent = radio.value === "batch"
      ? "多图模式只切换顶层显示参考图；执行时同一裁切位置会批量应用到所有同尺寸贴图，命名不含 {name} 时会自动补源图名避免覆盖。"
      : "单图模式只导出当前显示图片的裁切结果。";
  };
});
document.querySelectorAll('input[name="crop-shape-mode"]').forEach(radio => {
  radio.onchange = applyCropShapeModeToDraft;
});
cropCustomWidth.oninput = applyCropShapeModeToDraft;
cropCustomHeight.oninput = applyCropShapeModeToDraft;
cropAnchorGrid.querySelectorAll("button[data-anchor]").forEach(button => {
  button.onclick = () => alignCropDraft(button.dataset.anchor || "mc");
});
cropViewFit.onclick = fitCropView;
cropViewOut.onclick = () => setCropViewScaleFromCenter(cropView.scale / 1.18);
cropViewIn.onclick = () => setCropViewScaleFromCenter(cropView.scale * 1.18);
cropViewActual.onclick = () => setCropViewScaleFromCenter(1);
cropViewPan.onclick = () => {
  cropView.panMode = !cropView.panMode;
  updateCropViewControls();
};
cropEditorImg.addEventListener("load", () => {
  if (cropOverlay.classList.contains("open")) fitCropView();
});
cropEditor.addEventListener("pointerdown", event => {
  cropLastPointerTime = Date.now();
  if (event.target.closest(".crop-view-controls") || event.target.closest(".crop-actions")) return;
  if (cropPanRequested(event)) {
    startCropPan(event);
    return;
  }
  if (event.target === cropBox && cropDraft) {
    const edge = cropEdgeFromEvent(event) || "move";
    event.preventDefault();
    captureCropInput(event);
    cropResizeState = { edge, draft: { ...cropDraft }, point: editorPoint(event) };
    cropBox.style.cursor = cropEdgeCursor(edge);
    return;
  }
  if (event.target !== cropEditorImg && event.target !== cropEditor) return;
  event.preventDefault();
  captureCropInput(event);
  cropDragStart = editorPoint(event);
  cropResizeState = null;
  cropDraft = null;
  cropActions.style.display = "none";
  updateCropBoxFromPoints(cropDragStart, cropDragStart);
});
cropEditor.addEventListener("pointermove", event => {
  if (event.target === cropBox && !cropResizeState) {
    cropBox.style.cursor = cropEdgeCursor(cropEdgeFromEvent(event));
  }
  if (!cropEditor.hasPointerCapture(event.pointerId)) return;
  updateCropDragFromEvent(event);
});
cropEditor.addEventListener("pointerup", event => {
  releaseCropInput(event);
  finishCropPan();
  cropDragStart = null;
  cropResizeState = null;
});
cropEditor.addEventListener("pointercancel", event => {
  releaseCropInput(event);
  finishCropPan();
  cropDragStart = null;
  cropResizeState = null;
});
cropEditor.addEventListener("mousedown", event => {
  if (Date.now() - cropLastPointerTime < 600) return;
  if (event.target.closest(".crop-view-controls") || event.target.closest(".crop-actions")) return;
  if (cropPanRequested(event)) {
    startCropPan(event);
    return;
  }
  if (event.target === cropBox && cropDraft) {
    const edge = cropEdgeFromEvent(event) || "move";
    event.preventDefault();
    cropResizeState = { edge, draft: { ...cropDraft }, point: editorPoint(event) };
    cropBox.style.cursor = cropEdgeCursor(edge);
    return;
  }
  if (event.target !== cropEditorImg && event.target !== cropEditor) return;
  event.preventDefault();
  cropDragStart = editorPoint(event);
  cropResizeState = null;
  cropDraft = null;
  cropActions.style.display = "none";
  updateCropBoxFromPoints(cropDragStart, cropDragStart);
});
document.addEventListener("mousemove", event => {
  if (!cropOverlay.classList.contains("open")) return;
  if (!cropPanState && !cropResizeState && !cropDragStart) return;
  event.preventDefault();
  updateCropDragFromEvent(event);
});
document.addEventListener("mouseup", () => {
  finishCropPan();
  cropDragStart = null;
  cropResizeState = null;
});
cropEditor.addEventListener("wheel", event => {
  if (event.target.closest(".crop-view-controls") || event.target.closest(".crop-actions")) return;
  event.preventDefault();
  const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
  setCropViewScale(cropView.scale * factor, event.clientX, event.clientY);
}, { passive: false });
cropConfirm.onclick = confirmCropDraft;
cropCancel.onclick = closeCropEditor;
cropZoom.onclick = () => {
  cropZoom.classList.remove("open");
  cropZoomImg.src = "";
};
document.addEventListener("keydown", event => {
  const tag = event.target && event.target.tagName;
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(tag);
  if (cropOverlay.classList.contains("open") && event.code === "Space" && !typing) {
    cropSpacePan = true;
    updateCropViewControls();
    event.preventDefault();
  }
  if (event.key === "Escape" && cropOverlay.classList.contains("open")) closeCropEditor();
  if (event.key === "Escape" && cropZoom.classList.contains("open")) cropZoom.click();
});
document.addEventListener("keyup", event => {
  if (event.code === "Space") {
    cropSpacePan = false;
    updateCropViewControls();
  }
});
window.addEventListener("resize", () => {
  if (!cropOverlay.classList.contains("open")) return;
  cropView.fitScale = cropFitScale();
  clampCropView();
  applyCropView();
});
previewRun.onclick = previewSelectedChannels;
strengthKind.onchange = updateStrengthMode;
normalStrength.oninput = updateNormalStrengthLabel;
normalPreviewRun.onclick = previewNormalEffect;
roughnessStrength.oninput = updateRoughnessLabels;
roughnessContrast.oninput = updateRoughnessLabels;
roughnessBias.oninput = updateRoughnessLabels;
roughnessBlack.oninput = updateRoughnessLabels;
roughnessWhite.oninput = updateRoughnessLabels;
roughnessGamma.oninput = updateRoughnessLabels;
roughnessCurve.oninput = updateRoughnessLabels;
roughnessReset.onclick = resetRoughnessSliders;
compressQuality.oninput = updateCompressQualityLabel;
pbrStrength.oninput = updatePbrLabels;
pbrRadius.oninput = updatePbrLabels;
pbrDetail.oninput = updatePbrLabels;
pbrSmooth.oninput = updatePbrLabels;
pbrStack.oninput = updatePbrLabels;
pbrReset.onclick = resetPbrSliders;
pbrPreviewRun.onclick = previewPbrEffect;
renamePreviewRun.onclick = previewRenamePlan;
renameAddStep.onclick = () => addRenameStep();
mergePreviewRun.onclick = () => previewMergeComposite(true);
personalizeButton.onclick = () => {
  const open = settingsPanel.classList.toggle("open");
  personalizeButton.classList.toggle("active", open);
};
settingsClose.onclick = () => {
  settingsPanel.classList.remove("open");
  personalizeButton.classList.remove("active");
};
toneSelect.onchange = () => {
  applyUiSettings(selectedUiSettings());
  settingsStatus.textContent = "当前设置已生效，点击保存后下次启动继续使用。";
};
schemeSelect.onchange = () => {
  applyUiSettings(selectedUiSettings());
  settingsStatus.textContent = "当前设置已生效，点击保存后下次启动继续使用。";
};
radiusSlider.oninput = () => {
  applyUiSettings(selectedUiSettings());
  settingsStatus.textContent = "当前设置已生效，点击保存后下次启动继续使用。";
};
settingsSave.onclick = saveUiSettings;
settingsReset.onclick = resetUiSettings;
document.querySelectorAll('input[name="input-mode"]').forEach(radio => {
  radio.onchange = async () => {
    updateInputMode();
    if (inputMode() === "folder") await refreshFolderFiles(true);
  };
});
refreshInput.onclick = () => refreshFolderFiles(false);
inputDir.oninput = updateSourceWarning;
inputDir.onchange = () => {
  updateSourceWarning();
  if (inputMode() === "folder") refreshFolderFiles(false);
};
document.querySelectorAll('input[name="output-mode"]').forEach(radio => {
  radio.onchange = updateOutputMode;
});
outputBox.oninput = () => {
  if (outputMode() === "custom") customOutputValue = outputBox.value;
  updateSourceWarning();
};
clearDefaultOutput.onclick = clearDefaultOutputFiles;
document.getElementById("clear").onclick = () => {
  files = [];
  folderFiles = [];
  cropItems = [];
  cropPreviewMeta = null;
  setPreviewImage(cropPreviewImg, "");
  cropInfo.textContent = "默认显示第一张导入图；多图模式只切换顶层显示参考图，执行时会把同一裁切位置批量应用到所有同尺寸贴图；命名模板不含 {name} 时会自动补源图名避免覆盖。";
  renderCropCards();
  renderFiles();
  log("已清空列表。");
};
memoBox.oninput = saveMemo;
document.getElementById("clear-memo").onclick = clearMemo;
document.getElementById("clear-log").onclick = () => {
  resetLog("日志已清空。");
};
document.getElementById("shutdown").onclick = async () => {
  await fetch("/shutdown-all", { method: "POST" });
  log("工具箱已收到退出请求，可以关闭这个页面。");
};
function heartbeat() {
  fetch("/heartbeat", { method: "POST", keepalive: true }).catch(() => {});
}
heartbeat();
setInterval(heartbeat, 5000);
modeButtons.forEach(button => {
  button.onclick = () => setAppMode(button.dataset.mode || "quick");
});
workflowAddStep.onclick = () => {
  const step = createWorkflowStep(workflowStepType.value);
  workflowSteps.push(step);
  workflowSelectedStepId = step.id;
  workflowStatus(`已添加步骤：${step.label}。`);
  renderWorkflowShell();
};
workflowSave.onclick = saveWorkflowJson;
workflowLoad.onclick = () => workflowLoadInput.click();
workflowLoadInput.onchange = () => {
  loadWorkflowJsonFile(workflowLoadInput.files && workflowLoadInput.files[0]);
  workflowLoadInput.value = "";
};
workflowPreviewRun.onclick = previewWorkflowPlan;
document.querySelectorAll(".tab").forEach(tab => {
  tab.onclick = () => {
    currentTool = tab.dataset.tool;
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === tab));
    document.querySelectorAll(".tool").forEach(x => x.classList.toggle("active", x.id === `tool-${currentTool}`));
    updateChannelPreviewVisibility();
    if (currentTool === "crop" && cropSourceFile.value !== "") loadCropPreview();
  };
});
function appendCommon(form) {
  form.append("tool", currentTool);
  form.append("input_mode", inputMode());
  form.append("input", inputDir.value);
  form.append("output_mode", outputMode());
  form.append("output", outputBox.value);
  form.append("channel_mode", channelMode.value);
  if (inputMode() === "uploaded") {
    for (const file of files) form.append("files", file, file.webkitRelativePath || file.name);
  }
}
function appendToolOptions(form) {
  if (currentTool === "resize") {
    const sizes = [...document.querySelectorAll('input[name="size"]:checked')].map(x => x.value);
    const custom = document.getElementById("resize-custom").value.trim();
    if (custom) sizes.push(...custom.split(/[;,]/).map(x => x.trim()).filter(Boolean));
    form.append("sizes", sizes.join(","));
    form.append("profile", document.getElementById("resize-profile").value);
    form.append("format", document.getElementById("resize-format").value);
    form.append("preserve", document.getElementById("resize-preserve").checked ? "1" : "0");
    form.append("resize_size_suffix", document.getElementById("resize-size-suffix").checked ? "1" : "0");
  } else if (currentTool === "convert") {
    form.append("format", document.getElementById("convert-format").value);
  } else if (currentTool === "compress") {
    form.append("format", document.getElementById("compress-format").value);
    form.append("quality", compressQuality.value);
    form.append("lossless", document.getElementById("compress-lossless").checked ? "1" : "0");
  } else if (currentTool === "crop") {
    appendCropOptions(form);
  } else if (currentTool === "normal") {
    form.append("strength_mode", strengthKind.value);
    if (strengthKind.value === "roughness") {
      form.append("strength", roughnessStrength.value);
      form.append("contrast", roughnessContrast.value);
      form.append("bias", roughnessBias.value);
      form.append("black", roughnessBlack.value);
      form.append("white", roughnessWhite.value);
      form.append("gamma", roughnessGamma.value);
      form.append("curve", roughnessCurve.value);
      form.append("invert", document.getElementById("roughness-invert").checked ? "1" : "0");
    } else {
      form.append("strength", document.getElementById("normal-strength").value);
      form.append("flip_g", normalMode.value === "directx" ? "1" : "0");
      form.append("normal_mode", normalMode.value);
    }
    form.append("format", document.getElementById("normal-format").value);
  } else if (currentTool === "pbr") {
    form.append("source_type", pbrSourceType.value);
    form.append("mode", pbrMode.value);
    form.append("strength", pbrStrength.value);
    form.append("radius", pbrRadius.value);
    form.append("detail", pbrDetail.value);
    form.append("smooth", pbrSmooth.value);
    form.append("stack", pbrStack.value);
    form.append("normal_mode", pbrNormalMode.value);
    form.append("invert", document.getElementById("pbr-invert").checked ? "1" : "0");
    form.append("format", document.getElementById("pbr-format").value);
  } else if (currentTool === "split") {
    form.append("format", document.getElementById("split-format").value);
    for (const key of ["l", "r", "g", "b", "a"]) {
      form.append(`split_${key}_enabled`, document.getElementById(`split-${key}-enabled`).checked ? "1" : "0");
      form.append(`split_${key}_name`, document.getElementById(`split-${key}-name`).value);
    }
  } else if (currentTool === "merge") {
    form.append("base", document.getElementById("merge-base").value);
    for (const key of ["r", "g", "b", "a"]) {
      form.append(`${key}_mode`, document.getElementById(`merge-${key}-mode`).value);
      form.append(`${key}_file`, document.getElementById(`merge-${key}-file`).value);
      form.append(`${key}_channel`, document.getElementById(`merge-${key}-channel`).value);
    }
    form.append("name", document.getElementById("merge-name").value);
    form.append("format", document.getElementById("merge-format").value);
  } else if (currentTool === "rename") {
    appendRenameOptions(form);
  }
}

function setRunProgress(value, text, kind = "") {
  runProgressWrap.hidden = false;
  runProgress.value = Math.max(0, Math.min(100, value));
  runStatus.textContent = text;
  runStatus.className = `run-status muted${kind ? ` ${kind}` : ""}`;
}

function conflictLabel(item) {
  if (typeof item === "string") return item;
  const suffix = item.reason ? ` (${item.reason})` : "";
  return `${item.name || item.path || "同名文件"}${suffix}`;
}

function chooseConflictAction(conflicts) {
  const shown = conflicts.slice(0, 12).map(conflictLabel);
  const more = conflicts.length > shown.length ? [`...还有 ${conflicts.length - shown.length} 个`] : [];
  conflictList.textContent = shown.concat(more).join("\n");
  conflictModal.hidden = false;
  return new Promise(resolve => {
    const finish = action => {
      conflictModal.hidden = true;
      document.getElementById("conflict-overwrite").onclick = null;
      document.getElementById("conflict-suffix").onclick = null;
      document.getElementById("conflict-cancel").onclick = null;
      resolve(action);
    };
    document.getElementById("conflict-overwrite").onclick = () => finish("overwrite");
    document.getElementById("conflict-suffix").onclick = () => finish("suffix");
    document.getElementById("conflict-cancel").onclick = () => finish("cancel");
  });
}

async function checkExportConflicts(form) {
  const response = await fetch("/check-conflicts", { method: "POST", body: form });
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error || "导出检查失败");
  return result;
}

runButton.onclick = async () => {
  let count = 0;
  if (inputMode() === "folder") {
    const ok = await refreshFolderFiles(false);
    count = folderFiles.length;
    if (!ok || !count) { log("请确认自定义输入目录里有支持格式图片。"); return; }
  } else {
    count = files.length;
    if (!count) { log("请先拖入或选择图片。"); return; }
  }
  runButton.disabled = true;
  setRunProgress(4, "正在准备导出任务...");
  log(`开始执行：${currentTool}，文件数 ${count}...`);
  try {
    const selectedOutput = await chooseOutputDirectoryIfNeeded();
    if (!selectedOutput) {
      setRunProgress(100, "已取消导出。", "warn");
      log("已取消导出：没有选择输出文件夹。");
      return;
    }
    const form = new FormData();
    appendCommon(form);
    appendToolOptions(form);
    setRunProgress(18, "正在检查目标位置同名文件...");
    form.set("conflict_action", "cancel");
    const preflight = await checkExportConflicts(form);
    if (preflight.conflicts && preflight.conflicts.length) {
      setRunProgress(30, `发现 ${preflight.conflicts.length} 个同名目标文件，等待选择处理方式。`, "warn");
      const action = await chooseConflictAction(preflight.conflicts);
      if (action === "cancel") {
        setRunProgress(100, "已取消导出。", "warn");
        log("已取消导出：目标位置存在同名文件。");
        return;
      }
      form.set("conflict_action", action);
      if (action === "suffix") {
        setRunProgress(38, "正在检查 _TC 后缀目标名...");
        const suffixCheck = await checkExportConflicts(form);
        if (suffixCheck.conflicts && suffixCheck.conflicts.length) {
          const names = suffixCheck.conflicts.slice(0, 6).map(conflictLabel).join("、");
          throw new Error(`加 _TC 后仍有同名文件：${names}`);
        }
      }
    }
    setRunProgress(64, "正在执行并导出贴图...");
    const response = await fetch("/process", { method: "POST", body: form });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "处理失败");
    log(result.log.join("\n"));
    log(`完成，输出目录：${result.output}`);
    setRunProgress(100, `导出完成：${result.output}`, "ok");
  } catch (error) {
    log(`失败：${error.message}`);
    setRunProgress(100, `导出失败：${error.message}`, "error");
  } finally {
    runButton.disabled = false;
  }
};
loadUiSettings();
loadMemo();
initDailyWidget();
addRenameStep();
updateInputMode();
updateOutputMode();
updateChannelPreviewVisibility();
renderCropCards();
renderWorkflowShell();
updateNormalStrengthLabel();
updateRoughnessLabels();
updateCompressQualityLabel();
updateStrengthMode();
updatePbrLabels();
setComparePosition(50);
setPbrComparePosition(50);
</script>
</body>
</html>
"""


def safe_upload_name(value: str, index: int) -> str:
    name = Path(value.replace("\\", "/")).name
    stem = Path(name).stem or f"texture_{index}"
    suffix = Path(name).suffix.lower()
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".", " ") else "_" for ch in stem).strip()
    return f"{cleaned or f'texture_{index}'}{suffix}"


def safe_stem(value: str, fallback: str = "texture") -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".", " ") else "_" for ch in value).strip()
    return cleaned or fallback


def stem_with_suffix(stem: str, name_suffix: str) -> str:
    return f"{stem}{name_suffix}" if name_suffix else stem


def uploaded_files(form: cgi.FieldStorage) -> list[cgi.FieldStorage]:
    fields = form["files"] if "files" in form else []
    if not isinstance(fields, list):
        fields = [fields]
    return [field for field in fields if getattr(field, "filename", None)]


def uploaded_file_field(form: cgi.FieldStorage, name: str) -> cgi.FieldStorage | None:
    if name not in form:
        return None
    field = form[name]
    if isinstance(field, list):
        field = field[0] if field else None
    if field is None or not getattr(field, "filename", None):
        return None
    return field


def save_uploads(fields: Iterable[cgi.FieldStorage]) -> tuple[Path, list[Path]]:
    upload_dir = UPLOAD_ROOT / str(int(time.time() * 1000))
    upload_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, field in enumerate(fields, start=1):
        source_name = safe_upload_name(field.filename, index)
        item_dir = upload_dir / f"{index:04d}"
        item_dir.mkdir(parents=True, exist_ok=True)
        source_path = item_dir / source_name
        with source_path.open("wb") as handle:
            handle.write(field.file.read())
        if source_path.suffix.lower() in IMAGE_EXTENSIONS:
            paths.append(source_path)
    return upload_dir, paths


def save_preview_upload(field: cgi.FieldStorage) -> tuple[Path, Path]:
    upload_dir = UPLOAD_ROOT / f"preview_{int(time.time() * 1000)}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    source_name = safe_upload_name(field.filename, 1)
    source_path = upload_dir / source_name
    with source_path.open("wb") as handle:
        handle.write(field.file.read())
    return upload_dir, source_path


def cleanup_uploads(upload_dir: Path) -> None:
    if not upload_dir.exists():
        return
    for path in sorted(upload_dir.rglob("*"), reverse=True):
        try:
            if path.is_dir():
                path.rmdir()
            else:
                path.unlink()
        except OSError:
            pass
    for path in (upload_dir, upload_dir.parent):
        try:
            path.rmdir()
        except OSError:
            pass


def clean_path_text(value: str) -> str:
    return value.strip().strip('"')


def input_directory_from_text(value: str) -> Path:
    cleaned = clean_path_text(value)
    if not cleaned:
        raise ValueError("请填写自定义输入目录")
    path = Path(cleaned).expanduser()
    if not path.exists():
        raise ValueError(f"输入目录不存在：{path}")
    if not path.is_dir():
        raise ValueError(f"输入路径不是文件夹：{path}")
    return path


def output_directory_from_form(form: cgi.FieldStorage) -> Path:
    mode = form.getfirst("output_mode", "default")
    if mode == "source":
        return DEFAULT_OUTPUT_DIR
    if mode != "custom":
        if mode != "ask":
            return DEFAULT_OUTPUT_DIR
    cleaned = clean_path_text(form.getfirst("output", ""))
    if not cleaned:
        raise ValueError("请选择输出目录")
    return Path(cleaned).expanduser()


def source_output_enabled(form: cgi.FieldStorage) -> bool:
    return form.getfirst("output_mode", "default") == "source"


def validate_source_output_mode(form: cgi.FieldStorage) -> None:
    if source_output_enabled(form) and form.getfirst("input_mode", "uploaded") != "folder":
        raise ValueError("源文件位置输出只支持自定义输入目录；拖入/选择列表无法读取源图真实文件夹。")


def output_dir_for_source(source: Path, fallback_output_dir: Path, form: cgi.FieldStorage) -> Path:
    return source.parent if source_output_enabled(form) else fallback_output_dir


def output_label_from_form(form: cgi.FieldStorage, output_dir: Path) -> str:
    return "源文件位置" if source_output_enabled(form) else str(output_dir)


def list_directory_images(input_dir: Path) -> list[Path]:
    return core.iter_input_images([input_dir])


def directory_listing_payload(input_dir: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for path in list_directory_images(input_dir):
        try:
            relative = str(path.relative_to(input_dir))
        except ValueError:
            relative = path.name
        items.append(
            {
                "name": path.name,
                "relative": relative.replace("\\", "/"),
                "size": path.stat().st_size,
            }
        )
    return items


def collect_source_paths(form: cgi.FieldStorage) -> tuple[Path | None, list[Path]]:
    if form.getfirst("input_mode", "uploaded") == "folder":
        input_dir = input_directory_from_text(form.getfirst("input", ""))
        return None, list_directory_images(input_dir)

    fields = uploaded_files(form)
    if not fields:
        return None, []
    return save_uploads(fields)


def report_summary(reports: Iterable[core.SaveReport]) -> str:
    labels: list[str] = []
    warnings_seen: list[str] = []
    for report in reports:
        if report.output_label not in labels:
            labels.append(report.output_label)
        for warning in report.warnings:
            if warning not in warnings_seen:
                warnings_seen.append(warning)
    if not labels and not warnings_seen:
        return ""
    text = f" [输出: {' / '.join(labels)}]" if labels else ""
    if warnings_seen:
        text += "；提醒：" + "；".join(warnings_seen)
    return text


def split_options_from_form(form: cgi.FieldStorage) -> dict[str, dict[str, str]]:
    defaults = {"l": "{name}_L", "r": "{name}_R", "g": "{name}_G", "b": "{name}_B", "a": "{name}_A"}
    return {
        key: {
            "enabled": form.getfirst(f"split_{key}_enabled", "1"),
            "name": form.getfirst(f"split_{key}_name", defaults[key]),
        }
        for key in ("l", "r", "g", "b", "a")
    }


def merge_specs_from_form(form: cgi.FieldStorage) -> dict[str, dict[str, str]]:
    specs: dict[str, dict[str, str]] = {}
    for key, fallback in (("r", "default0"), ("g", "default0"), ("b", "default0"), ("a", "default255")):
        mode = form.getfirst(f"{key}_mode", fallback)
        if mode not in ("default0", "default255", "base", "file"):
            mode = fallback
        source_channel = form.getfirst(f"{key}_channel", "gray")
        if source_channel not in ("gray", "r", "g", "b", "a"):
            source_channel = "gray"
        specs[key] = {
            "mode": mode,
            "file": form.getfirst(f"{key}_file", ""),
            "channel": source_channel,
        }
    return specs


def inspect_copy_report(source: Path, destination: Path) -> core.SaveReport:
    with Image.open(source) as opened:
        label = core.image_mode_label(ImageOps.exif_transpose(opened))
    return core.SaveReport(destination, label, "保持源文件属性", [])


def save_tool_image(image: Image.Image, source: Path, output: Path, format_name: str, channel_mode: str) -> core.SaveReport:
    return core.save_image(image, source, output.with_suffix(f".{format_name}"), False, None, channel_mode)


def convert_one(source: Path, output_dir: Path, format_name: str, channel_mode: str, name_suffix: str = "") -> core.SaveReport:
    target_ext = source.suffix.lstrip(".").lower() if format_name == "keep" else format_name
    destination = output_dir / f"{stem_with_suffix(source.stem, name_suffix)}.{target_ext}"
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        return core.save_image(image, source, destination, format_name == "keep", opened.info.get("icc_profile"), channel_mode)


def save_compressed_image(
    image: Image.Image,
    source: Path,
    output_path: Path,
    keep_format: bool,
    icc_profile: bytes | None,
    channel_mode: str,
    quality: int,
    lossless: bool,
) -> core.SaveReport:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() if keep_format else output_path.suffix.lower()
    output_path = output_path.with_suffix(suffix)
    warnings_list: list[str] = []
    source_label = core.image_mode_label(image)

    if core.image_bit_depth(image) > 8:
        warnings_list.append("当前工具箱按 8位/通道 写出，16/32位每通道源图会被转换")

    image, _resolved_mode = core.convert_channel_mode(image, channel_mode)
    image, _resolved_mode = core.prepare_image_for_format(image, suffix, _resolved_mode, warnings_list)

    if suffix == ".psd":
        core.save_flat_psd(image, output_path)
        warnings_list.append("PSD 输出为扁平合成图，不能保留原 PSD 图层结构")
        return core.SaveReport(output_path, source_label, core.image_mode_label(image), warnings_list)

    params: dict[str, object] = {}
    if icc_profile:
        params["icc_profile"] = icc_profile

    quality = int(clamp_float(float(quality), 80.0, 100.0))
    if suffix in (".jpg", ".jpeg"):
        params.update({"quality": quality, "subsampling": 0, "optimize": True, "progressive": True})
        if lossless:
            warnings_list.append("JPG/JPEG 是有损格式；已使用 4:4:4 高质量参数尽量减少损失")
    elif suffix == ".png":
        params.update({"compress_level": 9, "optimize": True})
    elif suffix in (".tif", ".tiff"):
        params.update({"compression": "tiff_lzw"})
    elif suffix == ".tga":
        params.update({"compression": "tga_rle"})
    elif suffix == ".webp":
        if lossless:
            params.update({"lossless": True, "quality": 100, "method": 6, "exact": True})
        else:
            params.update({"lossless": False, "quality": quality, "method": 6, "exact": True})
    elif suffix == ".bmp":
        if image.mode not in ("RGB", "RGBA", "L"):
            image = image.convert("RGBA" if core.image_has_alpha(image) else "RGB")
        warnings_list.append("BMP 基本不压缩；已按兼容格式重写")
    elif suffix == ".dds":
        if image.mode not in ("L", "RGB", "RGBA"):
            image = image.convert("RGBA" if core.image_has_alpha(image) else "RGB")
        warnings_list.append("DDS 使用当前运行时默认写出能力，不等同 BC 系列专用贴图压缩")

    image.save(output_path, **params)
    return core.SaveReport(output_path, source_label, core.image_mode_label(image), warnings_list)


def compress_one(
    source: Path,
    output_dir: Path,
    format_name: str,
    channel_mode: str,
    quality: int,
    lossless: bool,
    name_suffix: str = "",
) -> core.SaveReport:
    target_ext = source.suffix.lstrip(".").lower() if format_name == "keep" else format_name
    destination = output_dir / f"{stem_with_suffix(f'{source.stem}_compressed', name_suffix)}.{target_ext}"
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        return save_compressed_image(image, source, destination, format_name == "keep", opened.info.get("icc_profile"), channel_mode, quality, lossless)


def adjusted_normal_image(source_image: Image.Image, strength: float, flip_g: bool) -> Image.Image:
    image = source_image.convert("RGBA")
    arr = np.asarray(image, dtype=np.float32) / 255.0
    x = arr[:, :, 0] * 2.0 - 1.0
    y = arr[:, :, 1] * 2.0 - 1.0
    if flip_g:
        y = -y
    x *= strength
    y *= strength
    z = np.sqrt(np.maximum(0.0, 1.0 - np.minimum(1.0, x * x + y * y)))
    length = np.sqrt(x * x + y * y + z * z)
    length = np.where(length > 0.00001, length, 1.0)
    out = np.zeros_like(arr)
    out[:, :, 0] = x / length * 0.5 + 0.5
    out[:, :, 1] = y / length * 0.5 + 0.5
    out[:, :, 2] = z / length * 0.5 + 0.5
    out[:, :, 3] = arr[:, :, 3]
    return Image.fromarray(np.clip(np.rint(out * 255.0), 0, 255).astype(np.uint8), mode="RGBA")


def adjust_normal_one(
    source: Path,
    output_dir: Path,
    strength: float,
    flip_g: bool,
    format_name: str,
    channel_mode: str,
    name_suffix: str = "",
) -> core.SaveReport:
    with Image.open(source) as opened:
        source_image = ImageOps.exif_transpose(opened)
        source_had_alpha = core.image_has_alpha(source_image)
        result = adjusted_normal_image(source_image, strength, flip_g)
        if core.normalize_channel_mode(channel_mode) == "auto" and not source_had_alpha:
            result = result.convert("RGB")
    destination = output_dir / f"{stem_with_suffix(f'{source.stem}_normal_{strength:g}', name_suffix)}.{format_name}"
    return core.save_image(result, source, destination, False, None, channel_mode)


def normal_flip_from_form(form: cgi.FieldStorage) -> bool:
    mode = form.getfirst("normal_mode", "").strip().lower()
    if mode in ("directx", "dx"):
        return True
    if mode == "opengl":
        return False
    return form.getfirst("flip_g", "0") == "1"


def clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def adjusted_roughness_image(
    source_image: Image.Image,
    strength: float,
    contrast: float,
    bias: float,
    invert: bool,
    black: float = 0.0,
    white: float = 1.0,
    gamma: float = 1.0,
    curve: float = 0.0,
) -> Image.Image:
    gray = ImageOps.grayscale(source_image)
    arr = np.asarray(gray, dtype=np.float32) / 255.0
    if invert:
        arr = 1.0 - arr
    black = clamp_float(black, 0.0, 0.95)
    white = clamp_float(white, 0.05, 1.0)
    if white <= black + 0.01:
        white = min(1.0, black + 0.01)
    arr = np.clip((arr - black) / (white - black), 0.0, 1.0)
    gamma = clamp_float(gamma, 0.2, 3.0)
    arr = np.power(arr, 1.0 / gamma)
    curve = clamp_float(curve, -1.0, 1.0)
    if abs(curve) > 0.0001:
        arr = arr + curve * (arr - 0.5) * 4.0 * arr * (1.0 - arr)
        arr = np.clip(arr, 0.0, 1.0)
    arr = (arr - 0.5) * contrast + 0.5
    arr = arr * strength + bias * 0.5
    return Image.fromarray(np.clip(np.rint(arr * 255.0), 0, 255).astype(np.uint8), mode="L")


def adjust_roughness_one(
    source: Path,
    output_dir: Path,
    strength: float,
    contrast: float,
    bias: float,
    invert: bool,
    black: float,
    white: float,
    gamma: float,
    curve: float,
    format_name: str,
    channel_mode: str,
    name_suffix: str = "",
) -> core.SaveReport:
    with Image.open(source) as opened:
        source_image = ImageOps.exif_transpose(opened)
        result = adjusted_roughness_image(source_image, strength, contrast, bias, invert, black, white, gamma, curve)
    destination = output_dir / f"{stem_with_suffix(f'{source.stem}_roughness_{strength:g}', name_suffix)}.{format_name}"
    return core.save_image(result, source, destination, False, None, channel_mode)


PBR_SOURCE_LABELS = {
    "color": "Photo / Diffuse / Color",
    "normal": "Normal Map",
    "height": "Height / Displacement",
}


PBR_MODE_LABELS = {
    "normal": "Color/Height To Normal",
    "derivative": "Derivative",
    "height": "Height",
    "displacement": "Displacement",
    "ao": "AO / Occ",
    "cavity": "Cavity",
    "concavity": "Concavity",
    "convexity": "Convexity",
    "curvature": "Curvature",
}


PBR_MODE_SUFFIXES = {
    "normal": "normal",
    "derivative": "derivative",
    "height": "height",
    "displacement": "displacement",
    "ao": "ao",
    "cavity": "cavity",
    "concavity": "concavity",
    "convexity": "convexity",
    "curvature": "curvature",
}


def normalized_pbr_source_type(value: str) -> str:
    value = (value or "color").strip().lower()
    return value if value in PBR_SOURCE_LABELS else "color"


def normalized_pbr_mode(value: str) -> str:
    value = (value or "normal").strip().lower()
    legacy = {
        "height_normal": "normal",
        "color_normal": "normal",
        "normal_cavity": "cavity",
        "normal_ao": "ao",
        "normal_bump_mask": "curvature",
    }
    value = legacy.get(value, value)
    return value if value in PBR_MODE_LABELS else "normal"


def array_to_l_image(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(np.rint(arr * 255.0), 0, 255).astype(np.uint8), mode="L")


def normalize_array(arr: np.ndarray, low_percentile: float = 1.0, high_percentile: float = 99.0) -> np.ndarray:
    arr = np.asarray(arr, dtype=np.float32)
    low = float(np.percentile(arr, low_percentile))
    high = float(np.percentile(arr, high_percentile))
    if high - low < 0.00001:
        return np.zeros_like(arr, dtype=np.float32)
    return np.clip((arr - low) / (high - low), 0.0, 1.0)


def soft_light(base: np.ndarray, blend: np.ndarray, amount: float) -> np.ndarray:
    base = np.clip(np.asarray(base, dtype=np.float32), 0.0, 1.0)
    blend = np.clip(np.asarray(blend, dtype=np.float32), 0.0, 1.0)
    soft = np.where(
        blend < 0.5,
        2.0 * base * blend + base * base * (1.0 - 2.0 * blend),
        2.0 * base * (1.0 - blend) + np.sqrt(np.clip(base, 0.0, 1.0)) * (2.0 * blend - 1.0),
    )
    return np.clip(base * (1.0 - amount) + soft * amount, 0.0, 1.0)


def blur_array(arr: np.ndarray, radius: float) -> np.ndarray:
    arr = np.asarray(arr, dtype=np.float32)
    if radius <= 0:
        return arr.copy()
    try:
        image = Image.fromarray(arr, mode="F")
        return np.asarray(image.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32)
    except Exception:
        image = array_to_l_image(normalize_array(arr))
        return np.asarray(image.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32) / 255.0


def sobel_gradients(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    work = np.asarray(arr, dtype=np.float32)
    padded = np.pad(work, ((1, 1), (1, 1)), mode="edge")
    tl = padded[:-2, :-2]
    tc = padded[:-2, 1:-1]
    tr = padded[:-2, 2:]
    ml = padded[1:-1, :-2]
    mr = padded[1:-1, 2:]
    bl = padded[2:, :-2]
    bc = padded[2:, 1:-1]
    br = padded[2:, 2:]
    gx = (tr + 2.0 * mr + br - tl - 2.0 * ml - bl) / 8.0
    gy = (bl + 2.0 * bc + br - tl - 2.0 * tc - tr) / 8.0
    return gy.astype(np.float32), gx.astype(np.float32)


def laplacian_array(arr: np.ndarray) -> np.ndarray:
    work = np.asarray(arr, dtype=np.float32)
    padded = np.pad(work, ((1, 1), (1, 1)), mode="edge")
    return (
        padded[:-2, 1:-1]
        + padded[2:, 1:-1]
        + padded[1:-1, :-2]
        + padded[1:-1, 2:]
        - 4.0 * work
    ).astype(np.float32)


def local_detail_layers(height: np.ndarray, radius: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    work = normalize_array(height, 0.25, 99.75)
    broad = blur_array(work, max(1.5, radius * 1.35))
    medium = blur_array(work, max(0.8, radius * 0.42))
    fine = blur_array(work, max(0.35, radius * 0.12))
    low_shape = medium - broad
    mid_detail = fine - medium
    micro_detail = work - fine
    return work, low_shape, mid_detail, micro_detail


def production_height_stack(height: np.ndarray, radius: int, detail: float, smooth: float, stack: float) -> np.ndarray:
    stack = clamp_float(stack, 0.0, 2.0)
    work, low_shape, mid_detail, micro_detail = local_detail_layers(height, radius)
    if stack <= 0.0001:
        return work
    structure = normalize_array(
        np.abs(low_shape) * 0.55 + np.abs(mid_detail) * 1.0 + np.abs(micro_detail) * 0.42,
        35.0,
        99.4,
    )
    structure = np.clip(blur_array(structure, max(0.25, radius * 0.035)) * 1.15, 0.0, 1.0)
    low_amount = (0.52 + detail * 0.13) * stack
    mid_amount = (0.72 + detail * 0.22) * stack
    micro_amount = (0.18 + detail * 0.16) * stack
    gated_micro = micro_detail * (0.35 + structure * 0.85)
    enhanced = work + low_shape * low_amount + mid_detail * mid_amount + gated_micro * micro_amount
    if smooth > 0:
        smoothed = blur_array(enhanced, max(0.12, smooth * 0.12))
        enhanced = enhanced * 0.88 + smoothed * 0.12
    enhanced = normalize_array(enhanced, 0.25, 99.75)
    contrast = 0.11 * stack
    enhanced = np.clip((enhanced - 0.5) * (1.0 + contrast) + 0.5, 0.0, 1.0)
    return soft_light(enhanced, structure, min(0.22, stack * 0.08))


def color_height_estimate(source_image: Image.Image, radius: int, detail: float, smooth: float, invert: bool) -> np.ndarray:
    rgb = np.asarray(source_image.convert("RGB"), dtype=np.float32) / 255.0
    gray = np.sum(rgb * np.array([0.2126, 0.7152, 0.0722], dtype=np.float32), axis=2)
    illumination = blur_array(gray, max(4.0, radius * 2.6))
    delit = normalize_array(gray - illumination + float(np.mean(illumination)), 0.5, 99.5)
    base = blur_array(delit, smooth * 0.45) if smooth > 0 else delit
    large = blur_array(delit, max(1.5, radius * 0.95))
    medium = blur_array(delit, max(0.75, radius * 0.30))
    small = blur_array(delit, max(0.35, radius * 0.075))
    chroma_blur = np.dstack([blur_array(rgb[:, :, channel], max(0.5, radius * 0.18)) for channel in range(3)])
    chroma_detail = normalize_array(np.mean(np.abs(rgb - chroma_blur), axis=2), 0.5, 99.5)
    broad_shape = medium - large
    fine_shape = small - medium
    micro_detail = delit - small
    height = (
        base * 0.58
        + medium * 0.22
        + broad_shape * (1.18 + detail * 0.34)
        + fine_shape * (0.78 + detail * 0.68)
        + micro_detail * detail * 0.42
        + (chroma_detail - 0.5) * detail * 0.16
    )
    height = normalize_array(height, 0.5, 99.5)
    return 1.0 - height if invert else height


def height_source_array(source_image: Image.Image, source_type: str, radius: int, detail: float, smooth: float, strength: float, flip_g: bool, invert: bool) -> np.ndarray:
    source_type = normalized_pbr_source_type(source_type)
    if source_type == "normal":
        height = height_from_normal_image(source_image, strength, smooth, flip_g)
    elif source_type == "height":
        height = np.asarray(ImageOps.grayscale(source_image), dtype=np.float32) / 255.0
        if detail > 0:
            small = blur_array(height, max(0.35, radius * 0.06))
            medium = blur_array(height, max(0.75, radius * 0.22))
            height = height + (small - medium) * detail * 0.85 + (height - small) * detail * 0.25
        if smooth > 0:
            height = blur_array(height, smooth * 0.45)
    else:
        height = color_height_estimate(source_image, radius, detail, smooth, invert=False)
    height = normalize_array(height)
    return 1.0 - height if invert else height


def normal_vectors_from_image(source_image: Image.Image, flip_g: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb = np.asarray(source_image.convert("RGB"), dtype=np.float32) / 255.0
    x = rgb[:, :, 0] * 2.0 - 1.0
    y = rgb[:, :, 1] * 2.0 - 1.0
    if flip_g:
        y = -y
    z = rgb[:, :, 2] * 2.0 - 1.0
    length = np.sqrt(x * x + y * y + z * z)
    length = np.where(length > 0.00001, length, 1.0)
    return x / length, y / length, z / length


def poisson_reconstruct(gx: np.ndarray, gy: np.ndarray) -> np.ndarray:
    height, width = gx.shape
    div = np.zeros_like(gx, dtype=np.float32)
    div[:, :-1] += gx[:, :-1]
    div[:, 1:] -= gx[:, :-1]
    div[:-1, :] += gy[:-1, :]
    div[1:, :] -= gy[:-1, :]

    fy = np.fft.fftfreq(height).reshape(-1, 1)
    fx = np.fft.fftfreq(width).reshape(1, -1)
    denom = (2.0 * np.cos(2.0 * np.pi * fx) - 2.0) + (2.0 * np.cos(2.0 * np.pi * fy) - 2.0)
    div_hat = np.fft.fft2(div)
    denom[0, 0] = 1.0
    height_hat = div_hat / denom
    height_hat[0, 0] = 0.0
    return normalize_array(np.real(np.fft.ifft2(height_hat)))


def height_from_normal_image(source_image: Image.Image, strength: float, smooth: float, flip_g: bool) -> np.ndarray:
    x, y, z = normal_vectors_from_image(source_image, flip_g)
    z = np.where(np.abs(z) > 0.0001, z, 0.0001)
    gx = -x / z * max(0.05, strength)
    gy = y / z * max(0.05, strength)
    height = poisson_reconstruct(gx, gy)
    if smooth > 0:
        height = normalize_array(blur_array(height, smooth * 0.35))
    return height


def normal_from_height_array(height: np.ndarray, strength: float, flip_g: bool) -> Image.Image:
    if height.shape[0] < 2 or height.shape[1] < 2:
        return Image.new("RGB", (height.shape[1], height.shape[0]), (128, 128, 255))
    work = normalize_array(height, 0.25, 99.75)
    grad_y, grad_x = sobel_gradients(work)
    gain = max(0.05, strength) * 12.0
    x = -grad_x * gain
    y = grad_y * gain
    if flip_g:
        y = -y
    z = np.ones_like(x)
    length = np.sqrt(x * x + y * y + z * z)
    length = np.where(length > 0.00001, length, 1.0)
    out = np.dstack((x / length * 0.5 + 0.5, y / length * 0.5 + 0.5, z / length * 0.5 + 0.5))
    return Image.fromarray(np.clip(np.rint(out * 255.0), 0, 255).astype(np.uint8), mode="RGB")


def derivative_from_height_array(height: np.ndarray, strength: float, flip_g: bool) -> Image.Image:
    grad_y, grad_x = sobel_gradients(normalize_array(height, 0.25, 99.75))
    gain = max(0.05, strength) * 4.0
    x = np.clip(grad_x * gain * 0.5 + 0.5, 0.0, 1.0)
    y = np.clip((-grad_y if flip_g else grad_y) * gain * 0.5 + 0.5, 0.0, 1.0)
    out = np.dstack((x, y, np.full_like(x, 0.5)))
    return Image.fromarray(np.clip(np.rint(out * 255.0), 0, 255).astype(np.uint8), mode="RGB")


def ao_from_height_array(height: np.ndarray, radius: int, strength: float) -> np.ndarray:
    height = normalize_array(height, 0.25, 99.75)
    occlusion = np.zeros_like(height, dtype=np.float32)
    total = 0.0
    for scale, weight in ((0.22, 0.25), (0.45, 0.28), (0.9, 0.28), (1.65, 0.19)):
        blurred = blur_array(height, max(1.0, radius * scale))
        occlusion += np.maximum(0.0, blurred - height) * weight
        total += weight
    occlusion = occlusion / max(total, 0.0001)
    amount = min(1.0, max(0.05, strength) / 3.6)
    ao = 1.0 - normalize_array(occlusion, 0.0, 99.7) * amount
    return np.clip(np.power(np.clip(ao, 0.0, 1.0), 1.0 + amount * 0.35), 0.0, 1.0)


def curvature_from_height_array(height: np.ndarray, radius: int, smooth: float) -> np.ndarray:
    work = normalize_array(height, 0.25, 99.75)
    work = blur_array(work, smooth * 0.25) if smooth > 0 else work
    fine = blur_array(work, max(0.35, radius * 0.08)) - blur_array(work, max(0.75, radius * 0.26))
    broad = blur_array(work, max(0.75, radius * 0.26)) - blur_array(work, max(1.5, radius * 0.9))
    lap = laplacian_array(blur_array(work, max(0.25, radius * 0.05)))
    convex_positive = fine * 0.45 + broad * 0.75 - lap * 0.55
    return -convex_positive


def pbr_adjusted_image(
    source_image: Image.Image,
    source_type: str,
    mode: str,
    strength: float,
    radius: int,
    detail: float,
    smooth: float,
    stack: float,
    flip_g: bool,
    invert: bool,
) -> tuple[Image.Image, str]:
    source_type = normalized_pbr_source_type(source_type)
    mode = normalized_pbr_mode(mode)
    stack = clamp_float(stack, 0.0, 2.0)
    raw_height = height_source_array(source_image, source_type, radius, detail, smooth, strength, flip_g, invert)
    height = production_height_stack(raw_height, radius, detail, smooth, stack)

    if mode == "normal":
        return normal_from_height_array(height, strength, flip_g), f"{PBR_SOURCE_LABELS[source_type]} -> Normal"
    if mode == "derivative":
        return derivative_from_height_array(height, strength, flip_g), f"{PBR_SOURCE_LABELS[source_type]} -> Derivative"
    if mode in ("height", "displacement"):
        if stack > 0.0001:
            curvature_for_height = normalize_array(np.abs(curvature_from_height_array(height, radius, smooth)), 0.25, 99.7)
            height = soft_light(height, curvature_for_height, min(0.55, stack * 0.18))
        return array_to_l_image(height), f"{PBR_SOURCE_LABELS[source_type]} -> {PBR_MODE_LABELS[mode]}"
    if mode == "ao":
        ao = ao_from_height_array(height, radius, strength)
        if stack > 0.0001:
            curvature = curvature_from_height_array(height, radius, smooth)
            cavity = normalize_array(np.maximum(0.0, curvature) * strength, 0.25, 99.7)
            ao = np.clip(soft_light(ao, 1.0 - cavity, min(0.5, stack * 0.18)), 0.0, 1.0)
        return array_to_l_image(ao), f"{PBR_SOURCE_LABELS[source_type]} -> AO / Occ"

    curvature = curvature_from_height_array(height, radius, smooth)
    ao_shadow = 1.0 - ao_from_height_array(height, radius, strength)
    if mode == "concavity":
        out = normalize_array(np.maximum(0.0, curvature) * strength + ao_shadow * stack * 0.28, 0.25, 99.7)
    elif mode == "convexity":
        out = normalize_array(np.maximum(0.0, -curvature) * strength + normalize_array(height, 0.5, 99.5) * stack * 0.08, 0.25, 99.7)
    elif mode == "curvature":
        signed = curvature * max(0.25, strength)
        out = np.clip(normalize_array(signed, 0.25, 99.75), 0.0, 1.0)
        if stack > 0.0001:
            edge_energy = normalize_array(np.abs(curvature), 0.25, 99.7)
            out = soft_light(out, edge_energy, min(0.45, stack * 0.14))
    else:
        cavity = np.maximum(0.0, curvature) * 0.82 + np.abs(curvature) * (0.24 + stack * 0.10)
        out = normalize_array(cavity * strength + ao_shadow * (0.42 + stack * 0.28), 0.25, 99.7)
    return array_to_l_image(1.0 - out if invert and mode not in ("height", "displacement") else out), f"{PBR_SOURCE_LABELS[source_type]} -> {PBR_MODE_LABELS[mode]}"


def pbr_convert_one(
    source: Path,
    output_dir: Path,
    source_type: str,
    mode: str,
    strength: float,
    radius: int,
    detail: float,
    smooth: float,
    stack: float,
    flip_g: bool,
    invert: bool,
    format_name: str,
    channel_mode: str,
    name_suffix: str = "",
) -> tuple[core.SaveReport, str]:
    source_type = normalized_pbr_source_type(source_type)
    mode = normalized_pbr_mode(mode)
    with Image.open(source) as opened:
        source_image = ImageOps.exif_transpose(opened)
        result, label = pbr_adjusted_image(source_image, source_type, mode, strength, radius, detail, smooth, stack, flip_g, invert)
    destination = output_dir / f"{stem_with_suffix(f'{source.stem}_{PBR_MODE_SUFFIXES[mode]}', name_suffix)}.{format_name}"
    return core.save_image(result, source, destination, False, None, channel_mode), label


def format_split_stem(template: str, source: Path, channel: str, format_name: str) -> str:
    value = (template or "").strip() or "{name}_{channel}"
    value = value.replace("{name}", source.stem).replace("{channel}", channel).replace("{ext}", format_name)
    return safe_stem(value, f"{source.stem}_{channel}")


def save_split_channel(
    channel_image: Image.Image,
    source: Path,
    output_dir: Path,
    format_name: str,
    channel_mode: str,
    channel_label: str,
    template: str,
    name_suffix: str = "",
) -> core.SaveReport:
    destination = output_dir / f"{stem_with_suffix(format_split_stem(template, source, channel_label, format_name), name_suffix)}.{format_name}"
    return core.save_image(channel_image.convert("L"), source, destination, False, None, channel_mode)


def split_channels_one(
    source: Path,
    output_dir: Path,
    format_name: str,
    channel_mode: str,
    split_options: dict[str, dict[str, str]],
    name_suffix: str = "",
) -> list[core.SaveReport]:
    reports: list[core.SaveReport] = []
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        if core.is_gray_mode(image) and not core.image_has_alpha(image):
            if split_options["l"]["enabled"] == "1":
                reports.append(save_split_channel(image.convert("L"), source, output_dir, format_name, channel_mode, "L", split_options["l"]["name"], name_suffix))
            return reports

        if image.mode == "LA":
            l_channel, a_channel = image.convert("LA").split()
            if split_options["l"]["enabled"] == "1":
                reports.append(save_split_channel(l_channel, source, output_dir, format_name, channel_mode, "L", split_options["l"]["name"], name_suffix))
            if split_options["a"]["enabled"] == "1":
                reports.append(save_split_channel(a_channel, source, output_dir, format_name, channel_mode, "A", split_options["a"]["name"], name_suffix))
            return reports

        rgba = image.convert("RGBA")
        channels = dict(zip(("R", "G", "B", "A"), rgba.split()))
        for key, label in (("r", "R"), ("g", "G"), ("b", "B")):
            if split_options[key]["enabled"] == "1":
                reports.append(save_split_channel(channels[label], source, output_dir, format_name, channel_mode, label, split_options[key]["name"], name_suffix))
        if core.image_has_alpha(image) and split_options["a"]["enabled"] == "1":
            reports.append(save_split_channel(channels["A"], source, output_dir, format_name, channel_mode, "A", split_options["a"]["name"], name_suffix))
    return reports


def extract_channel_image(image: Image.Image, channel: str, size: tuple[int, int] | None = None) -> Image.Image:
    if size is not None and image.size != size:
        image = image.resize(size, Image.Resampling.LANCZOS)

    if channel == "a":
        if core.image_has_alpha(image):
            return image.convert("RGBA").split()[3]
        return Image.new("L", image.size, 255)

    if core.is_gray_mode(image) and not core.image_has_alpha(image):
        return image.convert("L")
    if image.mode == "LA":
        gray, alpha = image.convert("LA").split()
        return alpha if channel == "a" else gray

    rgba = image.convert("RGBA")
    r, g, b, a = rgba.split()
    if channel == "r":
        return r
    if channel == "g":
        return g
    if channel == "b":
        return b
    arr = np.asarray(rgba, dtype=np.float32)
    luma = np.sum(arr[:, :, :3] * np.array([0.2126, 0.7152, 0.0722], dtype=np.float32), axis=2)
    return Image.fromarray(np.clip(np.rint(luma), 0, 255).astype(np.uint8), mode="L")


def extract_channel_from_path(path: Path, source_channel: str, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as opened:
        return extract_channel_image(ImageOps.exif_transpose(opened), source_channel, size)


def parse_index(value: str, paths: list[Path], label: str) -> int:
    try:
        index = int(value)
    except ValueError as exc:
        raise ValueError(f"{label} 没有选择有效文件") from exc
    if index < 0 or index >= len(paths):
        raise ValueError(f"{label} 文件索引无效")
    return index


def build_merge_result(
    paths: list[Path],
    base_value: str,
    specs: dict[str, dict[str, str]],
) -> tuple[Image.Image, dict[str, Image.Image], Path]:
    base_index: int | None = None
    base_image: Image.Image | None = None
    selected_indices = [int(spec["file"]) for spec in specs.values() if spec["mode"] == "file" and spec["file"] != ""]

    if base_value != "":
        base_index = parse_index(base_value, paths, "基础图")
        with Image.open(paths[base_index]) as opened:
            base_image = ImageOps.exif_transpose(opened).convert("RGBA")
        size = base_image.size
    elif selected_indices:
        first_index = selected_indices[0]
        with Image.open(paths[first_index]) as opened:
            size = ImageOps.exif_transpose(opened).size
    else:
        raise ValueError("通道合并至少需要基础图或一个来源文件通道")

    channels: dict[str, Image.Image] = {}
    for key, default in (("r", 0), ("g", 0), ("b", 0), ("a", 255)):
        spec = specs[key]
        mode = spec["mode"]
        if mode == "default255":
            channels[key] = Image.new("L", size, 255)
        elif mode == "base":
            if base_image is None:
                raise ValueError(f"目标 {key.upper()} 选择了保留基础图，但没有选择基础图")
            channels[key] = extract_channel_image(base_image, key, size)
        elif mode == "file":
            file_index = parse_index(spec["file"], paths, f"目标 {key.upper()}")
            channels[key] = extract_channel_from_path(paths[file_index], spec["channel"], size)
        else:
            channels[key] = Image.new("L", size, default)

    image = Image.merge("RGBA", (channels["r"], channels["g"], channels["b"], channels["a"]))
    source_for_report = paths[base_index] if base_index is not None else paths[selected_indices[0]]
    return image, channels, source_for_report


def merge_channels(
    paths: list[Path],
    output_dir: Path,
    base_value: str,
    specs: dict[str, dict[str, str]],
    output_name: str,
    format_name: str,
    channel_mode: str,
    name_suffix: str = "",
) -> core.SaveReport:
    image, _channels, source_for_report = build_merge_result(paths, base_value, specs)
    destination = output_dir / f"{stem_with_suffix(safe_stem(output_name, 'merged_rgba'), name_suffix)}.{format_name}"
    report = core.save_image(image, source_for_report, destination, False, None, channel_mode)
    return report


def preview_data_url(image: Image.Image, max_size: int = 220) -> str:
    preview = image.copy()
    preview.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    if preview.mode not in ("L", "RGB", "RGBA"):
        preview = preview.convert("RGBA" if core.image_has_alpha(preview) else "RGB")
    output = io.BytesIO()
    preview.save(output, format="PNG", optimize=True)
    data = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{data}"


def channel_stats(image: Image.Image) -> str:
    arr = np.asarray(image.convert("L"), dtype=np.uint8)
    return f"min {int(arr.min())} / max {int(arr.max())} / avg {float(arr.mean()):.1f}"


def preview_item(label: str, image: Image.Image, include_stats: bool = True) -> dict[str, str]:
    return {
        "label": label,
        "data_url": preview_data_url(image),
        "stats": channel_stats(image) if include_stats else "",
    }


def available_channel_labels(image: Image.Image) -> list[str]:
    if core.is_gray_mode(image) and not core.image_has_alpha(image):
        return ["L"]
    if image.mode == "LA":
        return ["L", "A"]
    labels = ["R", "G", "B"]
    if core.image_has_alpha(image):
        labels.append("A")
    return labels


def channel_preview_payload(source: Path) -> dict[str, object]:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        previews: list[dict[str, str]] = []
        original = image.convert("RGBA" if core.image_has_alpha(image) else "RGB")
        previews.append(preview_item("原图", original, False))

        if core.is_gray_mode(image) and not core.image_has_alpha(image):
            previews.append(preview_item("L", image.convert("L")))
        elif image.mode == "LA":
            gray, alpha = image.convert("LA").split()
            previews.append(preview_item("L", gray))
            previews.append(preview_item("A / Alpha", alpha))
        else:
            rgba = image.convert("RGBA")
            r, g, b, a = rgba.split()
            previews.append(preview_item("灰度 / Luma", extract_channel_image(image, "gray")))
            previews.append(preview_item("R", r))
            previews.append(preview_item("G", g))
            previews.append(preview_item("B", b))
            if core.image_has_alpha(image):
                previews.append(preview_item("A / Alpha", a))

        return {
            "ok": True,
            "name": source.name,
            "width": image.size[0],
            "height": image.size[1],
            "mode": image.mode,
            "channel_mode": core.image_mode_label(image),
            "has_alpha": core.image_has_alpha(image),
            "available_channels": available_channel_labels(image),
            "previews": previews,
        }


def normal_preview_payload(source: Path, strength: float, flip_g: bool) -> dict[str, object]:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        adjusted = adjusted_normal_image(image, strength, flip_g)
        return {
            "ok": True,
            "name": source.name,
            "width": image.size[0],
            "height": image.size[1],
            "strength": round(strength, 1),
            "flip_g": flip_g,
            "before": preview_data_url(image.convert("RGBA" if core.image_has_alpha(image) else "RGB"), 1400),
            "after": preview_data_url(adjusted, 1400),
        }


def roughness_preview_payload(
    source: Path,
    strength: float,
    contrast: float,
    bias: float,
    invert: bool,
    black: float,
    white: float,
    gamma: float,
    curve: float,
) -> dict[str, object]:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        adjusted = adjusted_roughness_image(image, strength, contrast, bias, invert, black, white, gamma, curve)
        return {
            "ok": True,
            "name": source.name,
            "width": image.size[0],
            "height": image.size[1],
            "strength": round(strength, 1),
            "contrast": round(contrast, 1),
            "bias": round(bias, 1),
            "black": round(black, 2),
            "white": round(white, 2),
            "gamma": round(gamma, 2),
            "curve": round(curve, 1),
            "invert": invert,
            "before": preview_data_url(image.convert("RGBA" if core.image_has_alpha(image) else "RGB"), 1400),
            "after": preview_data_url(adjusted, 1400),
        }


def pbr_preview_payload(
    source: Path,
    source_type: str,
    mode: str,
    strength: float,
    radius: int,
    detail: float,
    smooth: float,
    stack: float,
    flip_g: bool,
    invert: bool,
) -> dict[str, object]:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        adjusted, label = pbr_adjusted_image(image, source_type, mode, strength, radius, detail, smooth, stack, flip_g, invert)
        return {
            "ok": True,
            "name": source.name,
            "width": image.size[0],
            "height": image.size[1],
            "source_type": normalized_pbr_source_type(source_type),
            "mode": normalized_pbr_mode(mode),
            "label": label,
            "strength": round(strength, 1),
            "radius": int(radius),
            "detail": round(detail, 1),
            "smooth": round(smooth, 1),
            "stack": round(stack, 1),
            "flip_g": flip_g,
            "invert": invert,
            "before": preview_data_url(image.convert("RGBA" if core.image_has_alpha(image) else "RGB"), 1400),
            "after": preview_data_url(adjusted, 1400),
        }


def crop_preview_payload(source: Path) -> dict[str, object]:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        preview_image = image.convert("RGBA" if core.image_has_alpha(image) else "RGB")
        return {
            "ok": True,
            "name": source.name,
            "width": image.size[0],
            "height": image.size[1],
            "image": preview_data_url(preview_image, 1400),
        }


def merge_preview_payload(paths: list[Path], base_value: str, specs: dict[str, dict[str, str]]) -> dict[str, object]:
    image, channels, _source = build_merge_result(paths, base_value, specs)
    return {
        "ok": True,
        "width": image.size[0],
        "height": image.size[1],
        "channels": {
            key: preview_item(f"目标 {key.upper()}", channel)
            for key, channel in channels.items()
        },
        "composite": preview_item("合成 RGBA", image, False),
    }


def preview_source_from_form(form: cgi.FieldStorage) -> tuple[Path | None, Path]:
    if form.getfirst("input_mode", "uploaded") == "folder":
        input_dir = input_directory_from_text(form.getfirst("input", ""))
        paths = list_directory_images(input_dir)
        index = parse_index(form.getfirst("index", ""), paths, "预览图片")
        return None, paths[index]

    field = uploaded_file_field(form, "file")
    if field is None:
        raise ValueError("请选择要预览的上传图片")
    upload_dir, source = save_preview_upload(field)
    return upload_dir, source


TEXTURE_TYPE_ALIASES = {
    "normal": "Normal",
    "n": "Normal",
    "法线": "Normal",
    "normaldx": "NormalDX",
    "normalgl": "NormalGL",
    "ao": "AO",
    "ambientocclusion": "AO",
    "环境遮蔽": "AO",
    "roughness": "Roughness",
    "rough": "Roughness",
    "r": "Roughness",
    "粗糙度": "Roughness",
    "metallic": "Metallic",
    "metalness": "Metallic",
    "metal": "Metallic",
    "金属度": "Metallic",
    "basecolor": "BaseColor",
    "albedo": "Albedo",
    "diffuse": "Diffuse",
    "color": "Color",
    "颜色": "Color",
    "底色": "BaseColor",
    "漫反射": "Diffuse",
    "height": "Height",
    "displacement": "Displacement",
    "高度": "Height",
    "置换": "Displacement",
    "cavity": "Cavity",
    "cav": "Cavity",
    "凹槽": "Cavity",
    "opacity": "Opacity",
    "alpha": "Alpha",
    "透明度": "Opacity",
    "emissive": "Emissive",
    "emission": "Emissive",
    "自发光": "Emissive",
    "specular": "Specular",
    "glossiness": "Glossiness",
    "gloss": "Glossiness",
    "高光": "Specular",
    "光泽度": "Glossiness",
}


def split_name_tokens(stem: str) -> list[str]:
    return [part for part in re.split(r"[_\-.\s]+", stem) if part]


def detect_texture_type(stem: str, normalize_type: bool) -> tuple[str, str]:
    for token in split_name_tokens(stem):
        canonical = TEXTURE_TYPE_ALIASES.get(token.lower())
        if canonical:
            return (canonical if normalize_type else token), token
    lowered = stem.lower()
    for alias, canonical in sorted(TEXTURE_TYPE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if len(alias) <= 1:
            continue
        if alias in lowered:
            return (canonical if normalize_type else stem[lowered.index(alias): lowered.index(alias) + len(alias)]), alias
    return "", ""


def smart_base_name(stem: str, detected_token: str) -> str:
    tokens = split_name_tokens(stem)
    if detected_token:
        lowered = detected_token.lower()
        tokens = [token for token in tokens if token.lower() != lowered]
    return "_".join(tokens) or stem


def rename_options_from_form(form: cgi.FieldStorage) -> dict[str, object]:
    try:
        raw_steps = json.loads(form.getfirst("rename_steps", "[]"))
    except json.JSONDecodeError as exc:
        raise ValueError("重命名步骤格式无效") from exc
    steps: list[dict[str, str]] = []
    if isinstance(raw_steps, list):
        for item in raw_steps:
            if not isinstance(item, dict):
                continue
            op = str(item.get("op", "")).strip()
            if op not in ("replace", "prefix", "suffix", "insert"):
                continue
            steps.append(
                {
                    "op": op,
                    "find": str(item.get("find", "")),
                    "replace": str(item.get("replace", "")),
                    "prefix": str(item.get("prefix", "")).strip(),
                    "suffix": str(item.get("suffix", "")).strip(),
                    "left": str(item.get("left", "")),
                    "right": str(item.get("right", "")),
                    "insert": str(item.get("insert", "")).strip(),
                }
            )
    return {
        "format": form.getfirst("format", "keep"),
        "steps": steps,
    }


def insert_between_text(value: str, left: str, right: str, insert: str) -> str:
    left = left.strip()
    right = right.strip()
    insert = insert.strip()
    if not insert:
        return value
    if left and right:
        left_pos = value.find(left)
        search_from = left_pos + len(left) if left_pos >= 0 else 0
        right_pos = value.find(right, search_from)
        if left_pos >= 0 and right_pos >= 0:
            insert_at = left_pos + len(left)
            return f"{value[:insert_at]}{insert}{value[insert_at:]}"
    if left:
        left_pos = value.find(left)
        if left_pos >= 0:
            insert_at = left_pos + len(left)
            return f"{value[:insert_at]}{insert}{value[insert_at:]}"
    if right:
        right_pos = value.find(right)
        if right_pos >= 0:
            return f"{value[:right_pos]}{insert}{value[right_pos:]}"
    return f"{value}{insert}"


def render_rename_expression(expression: str, tokens: dict[str, str]) -> str:
    result = expression
    for key, value in tokens.items():
        result = result.replace(f"{{{key}}}", value)
    return result


def rename_target_stem(source: Path, index: int, options: dict[str, object]) -> tuple[str, str]:
    original_ext = source.suffix.lstrip(".").lower()
    texture_type, _detected_token = detect_texture_type(source.stem, True)
    expression = "{name}"
    tokens = {
        "name": source.stem,
        "index": str(index),
        "ext": original_ext,
        "type": texture_type,
    }
    for step in options.get("steps", []):
        if not isinstance(step, dict):
            continue
        op = step.get("op")
        if op == "replace":
            find_text = str(step.get("find", ""))
            if find_text:
                tokens["name"] = tokens["name"].replace(find_text, str(step.get("replace", "")))
        elif op == "prefix":
            prefix = str(step.get("prefix", "")).strip()
            if prefix:
                tokens["name"] = f"{render_rename_expression(prefix, tokens)}{tokens['name']}"
        elif op == "suffix":
            suffix = str(step.get("suffix", "")).strip()
            if suffix:
                tokens["name"] = f"{tokens['name']}{render_rename_expression(suffix, tokens)}"
        elif op == "insert":
            insert_text = render_rename_expression(str(step.get("insert", "")), tokens)
            tokens["name"] = insert_between_text(
                tokens["name"],
                str(step.get("left", "")),
                str(step.get("right", "")),
                insert_text,
            )
    target_stem = render_rename_expression(expression, tokens)
    target_stem = safe_stem(target_stem, source.stem or f"texture_{index}")
    return target_stem, texture_type


def rename_target_path(source: Path, output_dir: Path, index: int, options: dict[str, object], name_suffix: str = "") -> tuple[Path, str]:
    format_name = str(options["format"])
    original_ext = source.suffix.lstrip(".").lower()
    target_ext = original_ext if format_name == "keep" else format_name
    target_stem, texture_type = rename_target_stem(source, index, options)
    return output_dir / f"{stem_with_suffix(target_stem, name_suffix)}.{target_ext}", texture_type


def rename_plan(
    paths: list[Path],
    output_dir: Path,
    options: dict[str, object],
    name_suffix: str = "",
    source_output: bool = False,
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    seen: dict[str, int] = {}
    for index, source in enumerate(paths, start=1):
        target_dir = source.parent if source_output else output_dir
        destination, texture_type = rename_target_path(source, target_dir, index, options, name_suffix)
        key = destination.name.lower()
        seen[key] = seen.get(key, 0) + 1
        items.append(
            {
                "source_path": source,
                "destination": destination,
                "source": source.name,
                "target": destination.name,
                "texture_type": texture_type,
                "conflict": False,
            }
        )
    for item in items:
        destination = item["destination"]
        key = destination.name.lower()
        item["conflict"] = seen[key] > 1 or destination.exists()
    return items


def save_renamed_copy(source: Path, destination: Path, format_name: str, channel_mode: str) -> core.SaveReport:
    if format_name == "keep" and core.normalize_channel_mode(channel_mode) == "auto":
        shutil.copy2(source, destination)
        return inspect_copy_report(source, destination)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        return core.save_image(image, source, destination, format_name == "keep", opened.info.get("icc_profile"), channel_mode)


def crop_items_from_form(form: cgi.FieldStorage) -> list[dict[str, float | str]]:
    try:
        raw_items = json.loads(form.getfirst("crops", "[]"))
    except json.JSONDecodeError as exc:
        raise ValueError("裁切数据格式无效") from exc
    if not isinstance(raw_items, list):
        raise ValueError("裁切数据格式无效")
    crops: list[dict[str, float | str]] = []
    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue
        x = clamp_float(float(item.get("x", 0)), 0.0, 1.0)
        y = clamp_float(float(item.get("y", 0)), 0.0, 1.0)
        w = clamp_float(float(item.get("w", 0)), 0.0, 1.0)
        h = clamp_float(float(item.get("h", 0)), 0.0, 1.0)
        if w <= 0 or h <= 0:
            continue
        if x + w > 1.0:
            w = 1.0 - x
        if y + h > 1.0:
            h = 1.0 - y
        if w <= 0 or h <= 0:
            continue
        crops.append(
            {
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "name": str(item.get("name", f"{{name}}_crop{index}")).strip() or f"{{name}}_crop{index}",
            }
        )
    if not crops:
        raise ValueError("请先添加至少一个裁切框")
    return crops


def crop_pixel_box(size: tuple[int, int], crop: dict[str, float | str]) -> tuple[int, int, int, int]:
    width, height = size
    left = int(round(float(crop["x"]) * width))
    top = int(round(float(crop["y"]) * height))
    right = int(round((float(crop["x"]) + float(crop["w"])) * width))
    bottom = int(round((float(crop["y"]) + float(crop["h"])) * height))
    left = max(0, min(width - 1, left))
    top = max(0, min(height - 1, top))
    right = max(left + 1, min(width, right))
    bottom = max(top + 1, min(height, bottom))
    return left, top, right, bottom


def crop_output_stem(template: str, source: Path, crop_index: int, force_source_name: bool = False) -> str:
    ext = source.suffix.lstrip(".").lower()
    raw_template = template or f"{{name}}_crop{crop_index}"
    if force_source_name and "{name}" not in raw_template:
        raw_template = f"{{name}}_{raw_template}"
    value = (
        raw_template
        .replace("{name}", source.stem)
        .replace("{index}", str(crop_index).zfill(2))
        .replace("{ext}", ext)
    )
    return safe_stem(value, f"{source.stem}_crop{crop_index}")


def crop_output_path(
    source: Path,
    output_dir: Path,
    crop: dict[str, float | str],
    crop_index: int,
    format_name: str,
    force_source_name: bool = False,
    name_suffix: str = "",
) -> Path:
    target_ext = source.suffix.lstrip(".").lower() if format_name == "keep" else format_name
    stem = crop_output_stem(str(crop["name"]), source, crop_index, force_source_name)
    return output_dir / f"{stem_with_suffix(stem, name_suffix)}.{target_ext}"


def save_crop_one(
    source: Path,
    output_dir: Path,
    crop: dict[str, float | str],
    crop_index: int,
    format_name: str,
    channel_mode: str,
    force_source_name: bool = False,
    name_suffix: str = "",
) -> core.SaveReport:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        box = crop_pixel_box(image.size, crop)
        cropped = image.crop(box)
        destination = crop_output_path(source, output_dir, crop, crop_index, format_name, force_source_name, name_suffix)
        return core.save_image(cropped, source, destination, format_name == "keep", opened.info.get("icc_profile"), channel_mode)


def crop_target_sources_from_form(paths: list[Path], form: cgi.FieldStorage) -> tuple[list[Path], bool]:
    crop_mode = form.getfirst("crop_mode", "single")
    if crop_mode == "single":
        return [paths[parse_index(form.getfirst("crop_source_index", "0"), paths, "裁切显示图")]], False

    sizes: dict[tuple[int, int], list[str]] = {}
    for source in paths:
        with Image.open(source) as opened:
            sizes.setdefault(ImageOps.exif_transpose(opened).size, []).append(source.name)
    if len(sizes) > 1:
        detail = "; ".join(f"{size[0]}x{size[1]}: {len(names)}张" for size, names in sizes.items())
        raise ValueError(f"多图同位置裁切要求所有图片尺寸一致：{detail}")
    return paths, True


def split_output_paths_one(
    source: Path,
    output_dir: Path,
    format_name: str,
    split_options: dict[str, dict[str, str]],
    name_suffix: str = "",
) -> list[Path]:
    def channel_path(key: str, label: str) -> Path:
        stem = format_split_stem(split_options[key]["name"], source, label, format_name)
        return output_dir / f"{stem_with_suffix(stem, name_suffix)}.{format_name}"

    outputs: list[Path] = []
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        if core.is_gray_mode(image) and not core.image_has_alpha(image):
            if split_options["l"]["enabled"] == "1":
                outputs.append(channel_path("l", "L"))
            return outputs
        if image.mode == "LA":
            if split_options["l"]["enabled"] == "1":
                outputs.append(channel_path("l", "L"))
            if split_options["a"]["enabled"] == "1":
                outputs.append(channel_path("a", "A"))
            return outputs
        for key, label in (("r", "R"), ("g", "G"), ("b", "B")):
            if split_options[key]["enabled"] == "1":
                outputs.append(channel_path(key, label))
        if core.image_has_alpha(image) and split_options["a"]["enabled"] == "1":
            outputs.append(channel_path("a", "A"))
    return outputs


def merge_output_directory(paths: list[Path], fallback_output_dir: Path, form: cgi.FieldStorage) -> Path:
    if not source_output_enabled(form):
        return fallback_output_dir
    base_value = form.getfirst("base", "")
    if base_value != "":
        return paths[parse_index(base_value, paths, "基础图")].parent
    specs = merge_specs_from_form(form)
    for spec in specs.values():
        if spec["mode"] == "file" and spec["file"] != "":
            return paths[parse_index(spec["file"], paths, "通道来源")].parent
    return paths[0].parent


def normalized_output_format(value: object, allow_keep: bool = True, fallback: str = "png") -> str:
    text = str(value or "").strip().lower()
    if allow_keep and text == "keep":
        return "keep"
    return text if text in OUTPUT_FORMATS else fallback


def workflow_payload_from_form(form: cgi.FieldStorage) -> dict[str, object]:
    try:
        payload = json.loads(form.getfirst("workflow", "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("工作流 JSON 格式无效") from exc
    if not isinstance(payload, dict):
        raise ValueError("工作流 JSON 格式无效")
    return payload


def workflow_active_steps(payload: dict[str, object]) -> list[dict[str, object]]:
    raw_steps = payload.get("steps", [])
    if not isinstance(raw_steps, list):
        raise ValueError("工作流步骤数据无效")
    steps: list[dict[str, object]] = []
    for raw in raw_steps:
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        step_type = str(raw.get("type", "")).strip().lower()
        if not step_type:
            continue
        options = raw.get("options", {})
        steps.append({"type": step_type, "options": options if isinstance(options, dict) else {}})
    return steps


def workflow_resize_sizes(options: dict[str, object]) -> list[int]:
    values: list[str] = []
    raw_sizes = options.get("sizes", [])
    if isinstance(raw_sizes, list):
        values.extend(str(value) for value in raw_sizes)
    custom = str(options.get("custom", "")).strip()
    if custom:
        values.extend(part.strip() for part in re.split(r"[;,]", custom) if part.strip())
    sizes: list[int] = []
    seen: set[int] = set()
    for value in values:
        try:
            parsed = int(value)
        except ValueError:
            continue
        if parsed > 0 and parsed not in seen:
            seen.add(parsed)
            sizes.append(parsed)
    return sizes


def workflow_rename_stem(item: dict[str, object], source_index: int, options: dict[str, object]) -> str:
    source = item["source_path"]
    if not isinstance(source, Path):
        raise ValueError("工作流命名来源无效")
    texture_type = str(item.get("texture_type", ""))
    if not texture_type:
        texture_type, _detected_token = detect_texture_type(str(item.get("stem", source.stem)), True)
    tokens = {
        "name": str(item.get("stem", source.stem)),
        "index": str(source_index),
        "ext": str(item.get("ext", source.suffix.lstrip(".").lower())),
        "type": texture_type,
        "size": str(item.get("size_label", "")),
    }
    raw_steps = options.get("steps", [])
    rename_steps = raw_steps if isinstance(raw_steps, list) else []
    for step in rename_steps:
        if not isinstance(step, dict):
            continue
        op = step.get("op")
        if op == "replace":
            find_text = str(step.get("find", ""))
            if find_text:
                tokens["name"] = tokens["name"].replace(find_text, str(step.get("replace", "")))
        elif op == "prefix":
            prefix = str(step.get("prefix", "")).strip()
            if prefix:
                tokens["name"] = f"{render_rename_expression(prefix, tokens)}{tokens['name']}"
        elif op == "suffix":
            suffix = str(step.get("suffix", "")).strip()
            if suffix:
                tokens["name"] = f"{tokens['name']}{render_rename_expression(suffix, tokens)}"
        elif op == "insert":
            insert_text = render_rename_expression(str(step.get("insert", "")), tokens)
            tokens["name"] = insert_between_text(
                tokens["name"],
                str(step.get("left", "")),
                str(step.get("right", "")),
                insert_text,
            )
    return safe_stem(tokens["name"], source.stem or f"texture_{source_index}")


def workflow_preview_plan(paths: list[Path], output_dir: Path, form: cgi.FieldStorage, payload: dict[str, object]) -> dict[str, object]:
    validate_source_output_mode(form)
    steps = workflow_active_steps(payload)
    if not steps:
        raise ValueError("请先添加至少一个启用的工作流步骤")

    items: list[dict[str, object]] = []
    for source_index, source in enumerate(paths, start=1):
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened)
            texture_type, _detected_token = detect_texture_type(source.stem, True)
            items.append(
                {
                    "source_path": source,
                    "source_index": source_index,
                    "source": source.name,
                    "stem": source.stem,
                    "ext": source.suffix.lstrip(".").lower(),
                    "size": image.size,
                    "size_label": f"{image.size[0]}x{image.size[1]}",
                    "texture_type": texture_type,
                    "notes": [],
                }
            )

    warnings_list: list[str] = []
    unsupported_types: list[str] = []
    for step in steps:
        step_type = str(step["type"])
        options = step["options"] if isinstance(step["options"], dict) else {}
        if step_type == "resize":
            sizes = workflow_resize_sizes(options)
            if not sizes:
                raise ValueError("工作流缩放步骤未选择目标尺寸")
            preserve = options.get("preserve", True) is not False
            append_size_suffix = options.get("append_size_suffix", True) is not False
            output_format = normalized_output_format(options.get("format", "keep"), allow_keep=True, fallback="keep")
            resized_items: list[dict[str, object]] = []
            for item in items:
                source = item["source_path"]
                if not isinstance(source, Path):
                    continue
                original_size = item.get("size", (1, 1))
                if not isinstance(original_size, tuple):
                    original_size = (1, 1)
                for size in sizes:
                    dimensions = core.target_dimensions(original_size, int(size), preserve)
                    next_item = dict(item)
                    next_item["size"] = dimensions
                    next_item["size_label"] = f"{dimensions[0]}x{dimensions[1]}"
                    next_item["stem"] = f"{item['stem']}_{dimensions[0]}x{dimensions[1]}" if append_size_suffix else str(item["stem"])
                    if output_format != "keep":
                        next_item["ext"] = output_format
                    next_item["notes"] = [*item.get("notes", []), f"缩放 {dimensions[0]}x{dimensions[1]}"]
                    resized_items.append(next_item)
            items = resized_items
        elif step_type == "export":
            output_format = normalized_output_format(options.get("format", "png"), allow_keep=False, fallback="png")
            for item in items:
                item["ext"] = output_format
                item["notes"] = [*item.get("notes", []), f"导出 {output_format.upper()}"]
        elif step_type == "rename":
            output_format = normalized_output_format(options.get("format", "keep"), allow_keep=True, fallback="keep")
            for item in items:
                source_index = int(item.get("source_index", 1))
                item["stem"] = workflow_rename_stem(item, source_index, options)
                if output_format != "keep":
                    item["ext"] = output_format
                item["notes"] = [*item.get("notes", []), "命名规则"]
        else:
            label = {
                "crop": "图片裁切",
                "normal": "法线/黑白调整",
                "pbr": "PBR辅助生成",
                "split": "通道拆分",
                "merge": "通道合并/打包",
            }.get(step_type, step_type)
            if label not in unsupported_types:
                unsupported_types.append(label)

    if unsupported_types:
        warnings_list.append(f"{'、'.join(unsupported_types)}暂未参与输出预览")

    output_items: list[dict[str, object]] = []
    for item in items:
        source = item["source_path"]
        if not isinstance(source, Path):
            continue
        target_dir = output_dir_for_source(source, output_dir, form)
        ext = normalized_output_format(item.get("ext", source.suffix.lstrip(".").lower()), allow_keep=False, fallback=source.suffix.lstrip(".").lower() or "png")
        destination = target_dir / f"{safe_stem(str(item.get('stem', source.stem)), source.stem)}.{ext}"
        output_items.append(
            {
                "source": str(item.get("source", source.name)),
                "target": destination.name,
                "format": ext.upper(),
                "path": str(destination),
                "destination": destination,
                "notes": " / ".join(str(note) for note in item.get("notes", [])),
                "conflict": False,
                "reason": "",
            }
        )

    seen: dict[str, int] = {}
    for item in output_items:
        destination = item["destination"]
        if isinstance(destination, Path):
            key = path_key(destination)
            seen[key] = seen.get(key, 0) + 1
    for item in output_items:
        reasons: list[str] = []
        destination = item["destination"]
        if isinstance(destination, Path):
            if seen.get(path_key(destination), 0) > 1:
                reasons.append("本次预览内部重名")
            if destination.exists():
                reasons.append("目标位置已存在")
        item["conflict"] = bool(reasons)
        item["reason"] = "、".join(reasons)

    payload_items = [
        {
            "source": str(item["source"]),
            "target": str(item["target"]),
            "format": str(item["format"]),
            "path": str(item["path"]),
            "notes": str(item["notes"]),
            "conflict": bool(item["conflict"]),
            "reason": str(item["reason"]),
        }
        for item in output_items
    ]
    return {
        "ok": True,
        "total": len(payload_items),
        "items": payload_items,
        "conflicts": sum(1 for item in payload_items if item["conflict"]),
        "warnings": warnings_list,
        "output": output_label_from_form(form, output_dir),
    }


def planned_output_paths(paths: list[Path], output_dir: Path, form: cgi.FieldStorage, name_suffix: str = "") -> list[Path]:
    validate_source_output_mode(form)
    tool = form.getfirst("tool", "resize")
    if tool == "resize":
        sizes = core.parse_sizes(form.getfirst("sizes", ""))
        if not sizes:
            raise ValueError("请至少选择一个图像大小。")
        output_format = form.getfirst("format", "keep")
        keep_format = output_format == "keep"
        format_ext = f".{output_format}" if not keep_format else ".png"
        preserve_aspect = form.getfirst("preserve", "1") == "1"
        append_size_suffix = resize_append_size_suffix(form)
        outputs: list[Path] = []
        for source in paths:
            target_dir = output_dir_for_source(source, output_dir, form)
            with Image.open(source) as opened:
                image = ImageOps.exif_transpose(opened)
                for size in sizes:
                    dimensions = core.target_dimensions(image.size, int(size), preserve_aspect)
                    outputs.append(core.output_name(source, dimensions, target_dir, keep_format, format_ext, name_suffix, append_size_suffix))
        return outputs

    if tool == "convert":
        fmt = form.getfirst("format", "png")
        return [
            output_dir_for_source(source, output_dir, form) / f"{stem_with_suffix(source.stem, name_suffix)}.{source.suffix.lstrip('.').lower() if fmt == 'keep' else fmt}"
            for source in paths
        ]

    if tool == "compress":
        fmt = form.getfirst("format", "keep")
        return [
            output_dir_for_source(source, output_dir, form) / f"{stem_with_suffix(f'{source.stem}_compressed', name_suffix)}.{source.suffix.lstrip('.').lower() if fmt == 'keep' else fmt}"
            for source in paths
        ]

    if tool == "crop":
        fmt = form.getfirst("format", "keep")
        crops = crop_items_from_form(form)
        target_paths, force_source_name = crop_target_sources_from_form(paths, form)
        return [
            crop_output_path(source, output_dir_for_source(source, output_dir, form), crop, index, fmt, force_source_name, name_suffix)
            for source in target_paths
            for index, crop in enumerate(crops, start=1)
        ]

    if tool == "normal":
        fmt = form.getfirst("format", "png")
        strength = float(form.getfirst("strength", "1.0"))
        if form.getfirst("strength_mode", "normal") == "roughness":
            return [output_dir_for_source(source, output_dir, form) / f"{stem_with_suffix(f'{source.stem}_roughness_{strength:g}', name_suffix)}.{fmt}" for source in paths]
        return [output_dir_for_source(source, output_dir, form) / f"{stem_with_suffix(f'{source.stem}_normal_{strength:g}', name_suffix)}.{fmt}" for source in paths]

    if tool == "roughness":
        fmt = form.getfirst("format", "png")
        strength = float(form.getfirst("strength", "1.0"))
        return [output_dir_for_source(source, output_dir, form) / f"{stem_with_suffix(f'{source.stem}_roughness_{strength:g}', name_suffix)}.{fmt}" for source in paths]

    if tool == "pbr":
        fmt = form.getfirst("format", "png")
        mode = normalized_pbr_mode(form.getfirst("mode", "normal"))
        return [output_dir_for_source(source, output_dir, form) / f"{stem_with_suffix(f'{source.stem}_{PBR_MODE_SUFFIXES[mode]}', name_suffix)}.{fmt}" for source in paths]

    if tool == "split":
        fmt = form.getfirst("format", "png")
        split_options = split_options_from_form(form)
        outputs: list[Path] = []
        for source in paths:
            outputs.extend(split_output_paths_one(source, output_dir_for_source(source, output_dir, form), fmt, split_options, name_suffix))
        return outputs

    if tool == "merge":
        fmt = form.getfirst("format", "png")
        stem = safe_stem(form.getfirst("name", "merged_rgba"), "merged_rgba")
        return [merge_output_directory(paths, output_dir, form) / f"{stem_with_suffix(stem, name_suffix)}.{fmt}"]

    if tool == "rename":
        options = rename_options_from_form(form)
        return [Path(item["destination"]) for item in rename_plan(paths, output_dir, options, name_suffix, source_output_enabled(form))]

    raise ValueError(f"Unknown tool: {tool}")


def path_key(path: Path) -> str:
    return str(path.resolve()).casefold()


def duplicate_output_conflicts(paths: list[Path]) -> list[dict[str, str]]:
    seen: dict[str, list[Path]] = {}
    for path in paths:
        seen.setdefault(path_key(path), []).append(path)
    conflicts: list[dict[str, str]] = []
    for duplicates in seen.values():
        if len(duplicates) > 1:
            for path in duplicates:
                conflicts.append({"name": path.name, "path": str(path), "reason": "本次导出内部重名"})
    return conflicts


def existing_output_conflicts(paths: list[Path]) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in paths:
        key = path_key(path)
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            conflicts.append({"name": path.name, "path": str(path), "reason": "目标位置已存在"})
    return conflicts


def conflict_name_suffix(form: cgi.FieldStorage) -> str:
    return "_TC" if form.getfirst("conflict_action", "cancel") == "suffix" else ""


def resize_append_size_suffix(form: cgi.FieldStorage) -> bool:
    return form.getfirst("resize_size_suffix", "1") == "1"


def validate_export_targets(paths: list[Path], allow_existing: bool) -> list[dict[str, str]]:
    duplicate_conflicts = duplicate_output_conflicts(paths)
    if duplicate_conflicts:
        names = "、".join(item["name"] for item in duplicate_conflicts[:6])
        raise ValueError(f"本次导出目标文件名有重复，请先调整命名：{names}")
    existing_conflicts = existing_output_conflicts(paths)
    if existing_conflicts and not allow_existing:
        names = "、".join(item["name"] for item in existing_conflicts[:6])
        raise FileExistsError(f"目标位置已有同名文件：{names}")
    return existing_conflicts


def choose_output_directory_dialog(initial_dir: Path) -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError(f"当前环境无法打开文件夹选择窗口：{exc}") from exc

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass
    selected = filedialog.askdirectory(
        title="选择 TexCat 导出文件夹",
        initialdir=str(initial_dir if initial_dir.exists() else DEFAULT_OUTPUT_DIR),
        mustexist=False,
        parent=root,
    )
    root.destroy()
    return Path(selected).expanduser() if selected else None


class ToolboxHandler(BaseHTTPRequestHandler):
    server_version = f"TexCat/{APP_VERSION}"

    def log_message(self, _format: str, *args: object) -> None:
        return

    def send_text(self, status: int, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status: int, payload: dict[str, object]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_bytes(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/assets/"):
            self.handle_asset(parsed.path)
            return
        if parsed.path == "/list-input":
            mark_browser_alive(self.server)
            self.handle_list_input(parsed.query)
            return
        if parsed.path not in ("/", "/index.html"):
            self.send_text(404, "Not found")
            return
        mark_browser_alive(self.server)
        page = (
            TOOLBOX_PAGE
            .replace("__OUTPUT_DIR__", html.escape(str(DEFAULT_OUTPUT_DIR)))
            .replace("__APP_VERSION__", html.escape(APP_VERSION))
        )
        self.send_text(200, page, "text/html; charset=utf-8")

    def handle_asset(self, request_path: str) -> None:
        name = Path(urllib.parse.unquote(request_path)).name
        asset = ASSETS_DIR / name
        if not asset.is_file():
            self.send_text(404, "Not found")
            return
        content_types = {
            ".png": "image/png",
            ".ico": "image/x-icon",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }
        self.send_bytes(200, asset.read_bytes(), content_types.get(asset.suffix.lower(), "application/octet-stream"))

    def handle_list_input(self, query: str) -> None:
        params = urllib.parse.parse_qs(query)
        try:
            input_dir = input_directory_from_text(params.get("input", [""])[0])
            self.send_json(
                200,
                {
                    "ok": True,
                    "input": str(input_dir),
                    "files": directory_listing_payload(input_dir),
                },
            )
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/heartbeat":
            mark_browser_alive(self.server)
            self.send_json(200, {"ok": True})
            return
        if path in ("/shutdown", "/shutdown-self"):
            self.send_json(200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if path == "/shutdown-all":
            self.send_json(200, {"ok": True})
            threading.Thread(target=shutdown_all_servers_from, args=(self.server,), daemon=True).start()
            return
        if path == "/choose-output-dir":
            mark_browser_alive(self.server)
            try:
                self.handle_choose_output_dir()
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return
        if path == "/clear-default-output":
            mark_browser_alive(self.server)
            try:
                removed = clear_default_output_dir()
                self.send_json(200, {"ok": True, "removed": removed, "path": str(DEFAULT_OUTPUT_DIR)})
            except ValueError as exc:
                self.send_json(400, {"ok": False, "error": str(exc)})
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return
        if path == "/preview-channels":
            mark_browser_alive(self.server)
            try:
                self.handle_preview_channels()
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return
        if path == "/preview-normal":
            mark_browser_alive(self.server)
            try:
                self.handle_preview_normal()
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return
        if path == "/preview-roughness":
            mark_browser_alive(self.server)
            try:
                self.handle_preview_roughness()
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return
        if path == "/preview-pbr":
            mark_browser_alive(self.server)
            try:
                self.handle_preview_pbr()
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return
        if path == "/preview-crop":
            mark_browser_alive(self.server)
            try:
                self.handle_preview_crop()
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return
        if path == "/preview-merge":
            mark_browser_alive(self.server)
            try:
                self.handle_preview_merge()
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return
        if path == "/preview-rename":
            mark_browser_alive(self.server)
            try:
                self.handle_preview_rename()
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return
        if path == "/preview-workflow":
            mark_browser_alive(self.server)
            try:
                self.handle_preview_workflow()
            except ValueError as exc:
                self.send_json(400, {"ok": False, "error": str(exc)})
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return
        if path == "/check-conflicts":
            mark_browser_alive(self.server)
            try:
                self.handle_check_conflicts()
            except FileExistsError as exc:
                self.send_json(409, {"ok": False, "error": str(exc)})
            except ValueError as exc:
                self.send_json(400, {"ok": False, "error": str(exc)})
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return
        if path != "/process":
            self.send_json(404, {"ok": False, "error": "Not found"})
            return
        try:
            self.handle_process()
        except FileExistsError as exc:
            self.send_json(409, {"ok": False, "error": str(exc)})
        except ValueError as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})

    def parse_form(self) -> cgi.FieldStorage:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("Expected multipart form data")
        return cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
        )

    def handle_choose_output_dir(self) -> None:
        form = self.parse_form()
        initial_text = clean_path_text(form.getfirst("current", ""))
        initial_dir = Path(initial_text).expanduser() if initial_text else DEFAULT_OUTPUT_DIR
        selected = choose_output_directory_dialog(initial_dir)
        if selected is None:
            self.send_json(200, {"ok": True, "cancelled": True})
            return
        self.send_json(200, {"ok": True, "cancelled": False, "path": str(selected)})

    def handle_preview_channels(self) -> None:
        form = self.parse_form()
        upload_dir: Path | None = None
        try:
            upload_dir, source = preview_source_from_form(form)
            payload = channel_preview_payload(source)
            if upload_dir is not None:
                cleanup_uploads(upload_dir)
                upload_dir = None
            self.send_json(200, payload)
        finally:
            if upload_dir is not None:
                cleanup_uploads(upload_dir)

    def handle_preview_normal(self) -> None:
        form = self.parse_form()
        upload_dir: Path | None = None
        try:
            upload_dir, source = preview_source_from_form(form)
            strength = round(float(form.getfirst("strength", "1.5")), 1)
            flip_g = normal_flip_from_form(form)
            payload = normal_preview_payload(source, strength, flip_g)
            if upload_dir is not None:
                cleanup_uploads(upload_dir)
                upload_dir = None
            self.send_json(200, payload)
        finally:
            if upload_dir is not None:
                cleanup_uploads(upload_dir)

    def handle_preview_roughness(self) -> None:
        form = self.parse_form()
        upload_dir: Path | None = None
        try:
            upload_dir, source = preview_source_from_form(form)
            strength = clamp_float(round(float(form.getfirst("strength", "1.0")), 1), 0.0, 2.0)
            contrast = clamp_float(round(float(form.getfirst("contrast", "1.0")), 1), 0.0, 3.0)
            bias = clamp_float(round(float(form.getfirst("bias", "0")), 1), -1.0, 1.0)
            black = clamp_float(round(float(form.getfirst("black", "0")), 2), 0.0, 0.95)
            white = clamp_float(round(float(form.getfirst("white", "1")), 2), 0.05, 1.0)
            gamma = clamp_float(round(float(form.getfirst("gamma", "1")), 2), 0.2, 3.0)
            curve = clamp_float(round(float(form.getfirst("curve", "0")), 1), -1.0, 1.0)
            invert = form.getfirst("invert", "0") == "1"
            payload = roughness_preview_payload(source, strength, contrast, bias, invert, black, white, gamma, curve)
            if upload_dir is not None:
                cleanup_uploads(upload_dir)
                upload_dir = None
            self.send_json(200, payload)
        finally:
            if upload_dir is not None:
                cleanup_uploads(upload_dir)

    def handle_preview_pbr(self) -> None:
        form = self.parse_form()
        upload_dir: Path | None = None
        try:
            upload_dir, source = preview_source_from_form(form)
            source_type = normalized_pbr_source_type(form.getfirst("source_type", "color"))
            mode = normalized_pbr_mode(form.getfirst("mode", "normal"))
            strength = clamp_float(round(float(form.getfirst("strength", "3.0")), 1), 0.0, 8.0)
            radius = int(clamp_float(float(form.getfirst("radius", "10")), 1.0, 32.0))
            detail = clamp_float(round(float(form.getfirst("detail", "1.4")), 1), 0.0, 3.0)
            smooth = clamp_float(round(float(form.getfirst("smooth", "0.6")), 1), 0.0, 8.0)
            stack = clamp_float(round(float(form.getfirst("stack", "1.3")), 1), 0.0, 2.0)
            flip_g = normal_flip_from_form(form)
            invert = form.getfirst("invert", "0") == "1"
            payload = pbr_preview_payload(source, source_type, mode, strength, radius, detail, smooth, stack, flip_g, invert)
            if upload_dir is not None:
                cleanup_uploads(upload_dir)
                upload_dir = None
            self.send_json(200, payload)
        finally:
            if upload_dir is not None:
                cleanup_uploads(upload_dir)

    def handle_preview_crop(self) -> None:
        form = self.parse_form()
        upload_dir: Path | None = None
        try:
            upload_dir, source = preview_source_from_form(form)
            payload = crop_preview_payload(source)
            if upload_dir is not None:
                cleanup_uploads(upload_dir)
                upload_dir = None
            self.send_json(200, payload)
        finally:
            if upload_dir is not None:
                cleanup_uploads(upload_dir)

    def handle_preview_merge(self) -> None:
        form = self.parse_form()
        upload_dir, paths = collect_source_paths(form)
        try:
            if not paths:
                raise ValueError("没有可用于预览的图片")
            payload = merge_preview_payload(paths, form.getfirst("base", ""), merge_specs_from_form(form))
            if upload_dir is not None:
                cleanup_uploads(upload_dir)
                upload_dir = None
            self.send_json(200, payload)
        finally:
            if upload_dir is not None:
                cleanup_uploads(upload_dir)

    def handle_preview_rename(self) -> None:
        form = self.parse_form()
        upload_dir, paths = collect_source_paths(form)
        try:
            if not paths:
                raise ValueError("没有可用于预览的图片")
            validate_source_output_mode(form)
            output_dir = output_directory_from_form(form)
            options = rename_options_from_form(form)
            items = rename_plan(paths, output_dir, options, source_output=source_output_enabled(form))
            payload_items = [
                {
                    "source": str(item["source"]),
                    "target": str(item["target"]),
                    "texture_type": str(item["texture_type"]),
                    "conflict": bool(item["conflict"]),
                }
                for item in items
            ]
            if upload_dir is not None:
                cleanup_uploads(upload_dir)
                upload_dir = None
            self.send_json(200, {"ok": True, "items": payload_items})
        finally:
            if upload_dir is not None:
                cleanup_uploads(upload_dir)

    def handle_preview_workflow(self) -> None:
        form = self.parse_form()
        upload_dir, paths = collect_source_paths(form)
        try:
            if not paths:
                raise ValueError("没有可用于预览的图片")
            output_dir = output_directory_from_form(form)
            payload = workflow_payload_from_form(form)
            result = workflow_preview_plan(paths, output_dir, form, payload)
            if upload_dir is not None:
                cleanup_uploads(upload_dir)
                upload_dir = None
            self.send_json(200, result)
        finally:
            if upload_dir is not None:
                cleanup_uploads(upload_dir)

    def handle_check_conflicts(self) -> None:
        form = self.parse_form()
        upload_dir, paths = collect_source_paths(form)
        try:
            if not paths:
                raise ValueError("没有找到支持格式图片")
            output_dir = output_directory_from_form(form)
            name_suffix = conflict_name_suffix(form)
            planned = planned_output_paths(paths, output_dir, form, name_suffix)
            duplicate_conflicts = duplicate_output_conflicts(planned)
            if duplicate_conflicts:
                names = "、".join(item["name"] for item in duplicate_conflicts[:6])
                raise ValueError(f"本次导出目标文件名有重复，请先调整命名：{names}")
            self.send_json(
                200,
                {
                    "ok": True,
                    "total": len(planned),
                    "conflicts": existing_output_conflicts(planned),
                },
            )
        finally:
            if upload_dir is not None:
                cleanup_uploads(upload_dir)

    def handle_process(self) -> None:
        form = self.parse_form()
        upload_dir, paths = collect_source_paths(form)
        if not paths:
            if upload_dir is not None:
                cleanup_uploads(upload_dir)
            self.send_json(400, {"ok": False, "error": "没有找到支持格式图片"})
            return

        output_dir = output_directory_from_form(form)
        if not source_output_enabled(form):
            output_dir.mkdir(parents=True, exist_ok=True)
        tool = form.getfirst("tool", "resize")
        channel_mode = form.getfirst("channel_mode", "auto")
        conflict_action = form.getfirst("conflict_action", "cancel")
        name_suffix = conflict_name_suffix(form)
        log_lines: list[str] = []

        try:
            planned = planned_output_paths(paths, output_dir, form, name_suffix)
            validate_export_targets(planned, allow_existing=conflict_action == "overwrite")

            if tool == "resize":
                sizes = core.parse_sizes(form.getfirst("sizes", "2048,1024,512,256"))
                profile = core.PROFILES[form.getfirst("profile", "detail")]
                output_format = form.getfirst("format", "keep")
                keep_format = output_format == "keep"
                format_ext = f".{output_format}" if not keep_format else ".png"
                preserve_aspect = form.getfirst("preserve", "1") == "1"
                append_size_suffix = resize_append_size_suffix(form)
                for source in paths:
                    target_dir = output_dir_for_source(source, output_dir, form)
                    reports: list[core.SaveReport] = []
                    written = core.resize_one(
                        source,
                        target_dir,
                        sizes,
                        profile,
                        keep_format=keep_format,
                        format_ext=format_ext,
                        preserve_aspect=preserve_aspect,
                        channel_mode=channel_mode,
                        reports=reports,
                        name_suffix=name_suffix,
                        append_size_suffix=append_size_suffix,
                    )
                    log_lines.append(f"{source.name} -> " + ", ".join(path.name for path in written) + report_summary(reports))
            elif tool == "convert":
                fmt = form.getfirst("format", "png")
                for source in paths:
                    report = convert_one(source, output_dir_for_source(source, output_dir, form), fmt, channel_mode, name_suffix)
                    log_lines.append(f"{source.name} -> {report.path.name}" + report_summary([report]))
            elif tool == "compress":
                fmt = form.getfirst("format", "keep")
                quality = int(clamp_float(float(form.getfirst("quality", "95")), 80.0, 100.0))
                lossless = form.getfirst("lossless", "1") == "1"
                for source in paths:
                    report = compress_one(source, output_dir_for_source(source, output_dir, form), fmt, channel_mode, quality, lossless, name_suffix)
                    log_lines.append(f"{source.name} -> {report.path.name} [高质量压缩: 质量 {quality}; {'无损优先' if lossless else '有损高质量'}]" + report_summary([report]))
            elif tool == "crop":
                fmt = form.getfirst("format", "keep")
                crops = crop_items_from_form(form)
                crop_mode = form.getfirst("crop_mode", "single")
                if crop_mode == "single":
                    target_paths = [paths[parse_index(form.getfirst("crop_source_index", "0"), paths, "裁切显示图")]]
                    force_source_name = False
                else:
                    sizes: dict[tuple[int, int], list[str]] = {}
                    for source in paths:
                        with Image.open(source) as opened:
                            sizes.setdefault(ImageOps.exif_transpose(opened).size, []).append(source.name)
                    if len(sizes) > 1:
                        detail = "; ".join(f"{size[0]}x{size[1]}: {len(names)}张" for size, names in sizes.items())
                        raise ValueError(f"多图同位置裁切要求所有图片尺寸一致：{detail}")
                    target_paths = paths
                    force_source_name = True
                for source in target_paths:
                    target_dir = output_dir_for_source(source, output_dir, form)
                    reports = [save_crop_one(source, target_dir, crop, i, fmt, channel_mode, force_source_name, name_suffix) for i, crop in enumerate(crops, start=1)]
                    log_lines.append(f"{source.name} -> " + ", ".join(report.path.name for report in reports) + report_summary(reports))
            elif tool == "normal":
                fmt = form.getfirst("format", "png")
                if form.getfirst("strength_mode", "normal") == "roughness":
                    strength = clamp_float(float(form.getfirst("strength", "1.0")), 0.0, 2.0)
                    contrast = clamp_float(float(form.getfirst("contrast", "1.0")), 0.0, 3.0)
                    bias = clamp_float(float(form.getfirst("bias", "0")), -1.0, 1.0)
                    black = clamp_float(float(form.getfirst("black", "0")), 0.0, 0.95)
                    white = clamp_float(float(form.getfirst("white", "1")), 0.05, 1.0)
                    gamma = clamp_float(float(form.getfirst("gamma", "1")), 0.2, 3.0)
                    curve = clamp_float(float(form.getfirst("curve", "0")), -1.0, 1.0)
                    invert = form.getfirst("invert", "0") == "1"
                    for source in paths:
                        report = adjust_roughness_one(source, output_dir_for_source(source, output_dir, form), strength, contrast, bias, invert, black, white, gamma, curve, fmt, channel_mode, name_suffix)
                        log_lines.append(f"{source.name} -> {report.path.name} [黑白/粗糙度: 强度 {strength:g}, 对比 {contrast:g}, 色阶 {black:g}-{white:g}, Gamma {gamma:g}, 曲线 {curve:g}]" + report_summary([report]))
                else:
                    strength = float(form.getfirst("strength", "1.5"))
                    flip_g = normal_flip_from_form(form)
                    normal_label = "DirectX / DX" if flip_g else "OpenGL"
                    for source in paths:
                        report = adjust_normal_one(source, output_dir_for_source(source, output_dir, form), strength, flip_g, fmt, channel_mode, name_suffix)
                        log_lines.append(f"{source.name} -> {report.path.name} [法线模式: {normal_label}]" + report_summary([report]))
            elif tool == "roughness":
                strength = clamp_float(float(form.getfirst("strength", "1.0")), 0.0, 2.0)
                contrast = clamp_float(float(form.getfirst("contrast", "1.0")), 0.0, 3.0)
                bias = clamp_float(float(form.getfirst("bias", "0")), -1.0, 1.0)
                black = clamp_float(float(form.getfirst("black", "0")), 0.0, 0.95)
                white = clamp_float(float(form.getfirst("white", "1")), 0.05, 1.0)
                gamma = clamp_float(float(form.getfirst("gamma", "1")), 0.2, 3.0)
                curve = clamp_float(float(form.getfirst("curve", "0")), -1.0, 1.0)
                invert = form.getfirst("invert", "0") == "1"
                fmt = form.getfirst("format", "png")
                for source in paths:
                    report = adjust_roughness_one(source, output_dir_for_source(source, output_dir, form), strength, contrast, bias, invert, black, white, gamma, curve, fmt, channel_mode, name_suffix)
                    log_lines.append(f"{source.name} -> {report.path.name} [粗糙度: 强度 {strength:g}, 对比 {contrast:g}, 倾向 {bias:g}]" + report_summary([report]))
            elif tool == "pbr":
                source_type = normalized_pbr_source_type(form.getfirst("source_type", "color"))
                mode = normalized_pbr_mode(form.getfirst("mode", "normal"))
                strength = clamp_float(float(form.getfirst("strength", "3.0")), 0.0, 8.0)
                radius = int(clamp_float(float(form.getfirst("radius", "10")), 1.0, 32.0))
                detail = clamp_float(float(form.getfirst("detail", "1.4")), 0.0, 3.0)
                smooth = clamp_float(float(form.getfirst("smooth", "0.6")), 0.0, 8.0)
                stack = clamp_float(float(form.getfirst("stack", "1.3")), 0.0, 2.0)
                flip_g = normal_flip_from_form(form)
                invert = form.getfirst("invert", "0") == "1"
                fmt = form.getfirst("format", "png")
                for source in paths:
                    report, label = pbr_convert_one(source, output_dir_for_source(source, output_dir, form), source_type, mode, strength, radius, detail, smooth, stack, flip_g, invert, fmt, channel_mode, name_suffix)
                    log_lines.append(f"{source.name} -> {report.path.name} [{label}; 半径 {radius}; 细节 {detail:g}; 叠加 {stack:g}]" + report_summary([report]))
            elif tool == "split":
                fmt = form.getfirst("format", "png")
                split_options = split_options_from_form(form)
                for source in paths:
                    reports = split_channels_one(source, output_dir_for_source(source, output_dir, form), fmt, channel_mode, split_options, name_suffix)
                    if reports:
                        log_lines.append(f"{source.name} -> " + ", ".join(report.path.name for report in reports) + report_summary(reports))
                    else:
                        log_lines.append(f"{source.name} -> 未输出通道，请检查拆分勾选项")
            elif tool == "merge":
                fmt = form.getfirst("format", "png")
                report = merge_channels(paths, merge_output_directory(paths, output_dir, form), form.getfirst("base", ""), merge_specs_from_form(form), form.getfirst("name", "merged_rgba"), fmt, channel_mode, name_suffix)
                log_lines.append(f"通道合并 -> {report.path.name}" + report_summary([report]))
            elif tool == "rename":
                options = rename_options_from_form(form)
                planned = rename_plan(paths, output_dir, options, name_suffix, source_output_enabled(form))
                fmt = str(options["format"])
                for item in planned:
                    source = item["source_path"]
                    destination = item["destination"]
                    report = save_renamed_copy(source, destination, fmt, channel_mode)
                    type_note = f" [贴图类型: {item['texture_type']}]" if item["texture_type"] else ""
                    log_lines.append(f"{source.name} -> {report.path.name}{type_note}" + report_summary([report]))
            else:
                raise ValueError(f"Unknown tool: {tool}")
        finally:
            if upload_dir is not None:
                cleanup_uploads(upload_dir)

        self.send_json(200, {"ok": True, "output": output_label_from_form(form, output_dir), "log": log_lines})


def run_web(port: int = 8765) -> int:
    ensure_default_dirs()
    base_port = port
    shutdown_existing_servers(port, 20)
    server: ThreadingHTTPServer | None = None
    last_error: OSError | None = None
    for candidate in range(port, port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), ToolboxHandler)
            port = candidate
            server.last_heartbeat = time.monotonic()
            server.browser_seen = False
            server.base_port = base_port
            break
        except OSError as exc:
            last_error = exc
    if server is None:
        raise RuntimeError(f"Cannot start local web server: {last_error}")

    url = f"http://127.0.0.1:{port}/"
    threading.Thread(target=browser_liveness_monitor, args=(server,), daemon=True).start()
    threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    print(f"TexCat toolbox: {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def shutdown_existing_servers(port: int, count: int) -> None:
    stopped = False
    for candidate in range(port, port + count):
        for endpoint in ("shutdown-self", "shutdown"):
            request = urllib.request.Request(
                f"http://127.0.0.1:{candidate}/{endpoint}",
                data=b"",
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=0.1):
                    stopped = True
                    break
            except (OSError, urllib.error.URLError):
                pass
    if stopped:
        time.sleep(0.5)


def mark_browser_alive(server: ThreadingHTTPServer) -> None:
    server.last_heartbeat = time.monotonic()
    server.browser_seen = True


def browser_liveness_monitor(server: ThreadingHTTPServer, timeout_seconds: float = 20.0) -> None:
    while True:
        time.sleep(2.0)
        if getattr(server, "browser_seen", False) and time.monotonic() - getattr(server, "last_heartbeat", 0.0) > timeout_seconds:
            server.shutdown()
            return


def shutdown_all_servers_from(server: ThreadingHTTPServer) -> None:
    port = int(getattr(server, "base_port", server.server_address[1]))
    current_port = int(server.server_address[1])
    for candidate in range(port, port + 20):
        if candidate == current_port:
            continue
        request = urllib.request.Request(
            f"http://127.0.0.1:{candidate}/shutdown-self",
            data=b"",
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=0.05):
                pass
        except (OSError, urllib.error.URLError):
            pass
    time.sleep(0.1)
    server.shutdown()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Texture toolbox web UI.")
    parser.add_argument("--web", action="store_true", help="Open the browser toolbox.")
    parser.add_argument("--port", type=int, default=8765, help="Web interface port.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_web(args.port)


if __name__ == "__main__":
    raise SystemExit(main())
