#!/usr/bin/env python3
"""High-quality texture downscaler with a small Photoshop-like GUI."""

from __future__ import annotations

import argparse
import ctypes
import html
import json
import os
import struct
import sys
import threading
import time
import webbrowser
import warnings
from dataclasses import dataclass
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


def configure_tk_runtime() -> None:
    python_dir = Path(sys.executable).resolve().parent
    tcl_dir = python_dir / "tcl"
    tcl_library = tcl_dir / "tcl8.6"
    tk_library = tcl_dir / "tk8.6"
    if tcl_library.exists():
        os.environ.setdefault("TCL_LIBRARY", tcl_library.as_posix())
    if tk_library.exists():
        os.environ.setdefault("TK_LIBRARY", tk_library.as_posix())


configure_tk_runtime()

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception:  # pragma: no cover - CLI can still be used without tkinter.
    tk = None
    filedialog = None
    messagebox = None
    ttk = None


TARGET_SIZES = (16384, 8192, 4096, 2048, 1024, 512, 256)
DEFAULT_TARGET_SIZES = (2048, 1024, 512, 256)
IMAGE_EXTENSIONS = {".psd", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".tga", ".dds", ".webp", ".bmp"}
OUTPUT_FORMATS = (".psd", ".png", ".tga", ".tif", ".tiff", ".jpg", ".jpeg", ".dds", ".webp", ".bmp")
DEFAULT_OUTPUT_DIR = Path.cwd() / "resized_textures"
CHANNEL_MODES = ("auto", "rgb24", "rgba32", "gray8")
CHANNEL_MODE_LABELS = {
    "auto": "自动/跟随源图",
    "rgb24": "RGB 24位",
    "rgba32": "RGBA 32位",
    "gray8": "灰度 8位",
}


@dataclass
class SaveReport:
    path: Path
    source_label: str
    output_label: str
    warnings: list[str]


WEB_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>贴图图像大小工具</title>
<style>
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
  color: #20242c;
  background: #f4f6f8;
}
main { max-width: 980px; margin: 0 auto; padding: 24px; }
h1 { margin: 0 0 18px; font-size: 26px; font-weight: 650; letter-spacing: 0; }
.panel {
  background: #fff;
  border: 1px solid #d8dde6;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 14px;
}
#drop {
  min-height: 220px;
  border: 2px dashed #7f8b9d;
  border-radius: 8px;
  background: #fbfcfd;
  display: grid;
  place-items: center;
  text-align: center;
  padding: 20px;
}
#drop.active { border-color: #1b73e8; background: #eef5ff; }
#drop strong { display: block; font-size: 20px; margin-bottom: 8px; }
.row { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; margin: 10px 0; }
label { display: inline-flex; align-items: center; gap: 6px; }
input[type="text"], select {
  height: 34px;
  border: 1px solid #c5ccd6;
  border-radius: 6px;
  padding: 0 10px;
  min-width: 220px;
}
input.path { flex: 1; min-width: 320px; }
button {
  height: 36px;
  border: 1px solid #1b73e8;
  background: #1b73e8;
  color: white;
  border-radius: 6px;
  padding: 0 14px;
  cursor: pointer;
}
button:disabled { opacity: .55; cursor: not-allowed; }
#files, #log {
  width: 100%;
  min-height: 110px;
  max-height: 220px;
  overflow: auto;
  border: 1px solid #d8dde6;
  border-radius: 6px;
  background: #fff;
  padding: 10px;
  font-family: Consolas, "Microsoft YaHei", monospace;
  font-size: 13px;
  white-space: pre-wrap;
}
.muted { color: #697386; font-size: 13px; }
</style>
</head>
<body>
<main>
  <h1>贴图图像大小工具</h1>
  <section id="drop" class="panel">
    <div>
      <strong>把 PSD / PNG / TGA / TIF / JPG / DDS / WEBP / BMP 图片或文件夹拖到这里</strong>
      <span class="muted">也可以点击选择文件；文件夹拖入在 Edge/Chrome 下支持递归读取。</span>
      <div style="margin-top:12px"><button id="pick" type="button">选择图片</button></div>
      <input id="picker" type="file" multiple hidden accept=".psd,.png,.tga,.tif,.tiff,.jpg,.jpeg,.dds,.webp,.bmp">
    </div>
  </section>
  <section class="panel">
    <div class="row">
      <label><input type="checkbox" name="size" value="2048" checked>2048</label>
      <label><input type="checkbox" name="size" value="1024" checked>1024</label>
      <label><input type="checkbox" name="size" value="512" checked>512</label>
      <label><input type="checkbox" name="size" value="256" checked>256</label>
      <label>自定义 <input id="custom" type="text" placeholder="1536,768"></label>
      <label><input id="preserve" type="checkbox" checked>锁定比例</label>
    </div>
    <div class="row">
      <label>配置
        <select id="profile">
          <option value="detail">detail - 颜色贴图/细节保留</option>
          <option value="data">data - 法线/遮罩/数据贴图</option>
          <option value="pixel">pixel - 像素风/硬边</option>
        </select>
      </label>
      <label>输出格式
        <select id="format">
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
      <label>输出目录 <input id="output" class="path" type="text" value="__OUTPUT_DIR__"></label>
    </div>
    <div class="row">
      <button id="run" type="button">开始缩放</button>
      <button id="clear" type="button">清空列表</button>
      <button id="shutdown" type="button">关闭工具</button>
      <span class="muted">输出会保存到上面的本机目录。</span>
    </div>
  </section>
  <section class="panel">
    <div class="muted">待处理文件</div>
    <div id="files">尚未添加图片。</div>
  </section>
  <section class="panel">
    <div class="muted">日志</div>
    <div id="log">浏览器拖放入口已就绪。</div>
  </section>
</main>
<script>
const allowed = new Set(["psd","png","tga","tif","tiff","jpg","jpeg","dds","webp","bmp"]);
const drop = document.getElementById("drop");
const picker = document.getElementById("picker");
const filesBox = document.getElementById("files");
const logBox = document.getElementById("log");
let files = [];

function log(text) {
  logBox.textContent += "\n" + text;
  logBox.scrollTop = logBox.scrollHeight;
}
function renderFiles() {
  filesBox.textContent = files.length ? files.map((f, i) => `${i + 1}. ${f.webkitRelativePath || f.name} (${Math.round(f.size / 1024)} KB)`).join("\n") : "尚未添加图片。";
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
  renderFiles();
  log(added ? `已添加 ${added} 个文件。` : "没有发现新的支持格式图片。");
}
async function readEntry(entry, prefix = "") {
  if (entry.isFile) {
    return await new Promise(resolve => entry.file(file => resolve([file]), () => resolve([])));
  }
  if (!entry.isDirectory) return [];
  const reader = entry.createReader();
  const out = [];
  while (true) {
    const batch = await new Promise(resolve => reader.readEntries(resolve, () => resolve([])));
    if (!batch.length) break;
    for (const child of batch) out.push(...await readEntry(child, prefix + entry.name + "/"));
  }
  return out;
}
async function collectDropFiles(event) {
  const items = [...event.dataTransfer.items || []];
  if (!items.length) return [...event.dataTransfer.files || []];
  const out = [];
  for (const item of items) {
    const entry = item.webkitGetAsEntry && item.webkitGetAsEntry();
    if (entry) out.push(...await readEntry(entry));
    else {
      const file = item.getAsFile && item.getAsFile();
      if (file) out.push(file);
    }
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
picker.onchange = () => addFiles([...picker.files]);
document.getElementById("clear").onclick = () => {
  files = [];
  renderFiles();
  log("已清空列表。");
};
document.getElementById("shutdown").onclick = async () => {
  await fetch("/shutdown", { method: "POST" });
  log("工具已收到关闭请求，可以关闭这个页面。");
};
document.getElementById("run").onclick = async () => {
  if (!files.length) { log("请先拖入或选择图片。"); return; }
  const sizes = [...document.querySelectorAll('input[name="size"]:checked')].map(x => x.value);
  const custom = document.getElementById("custom").value.trim();
  if (custom) sizes.push(...custom.split(/[;,]/).map(x => x.trim()).filter(Boolean));
  if (!sizes.length) { log("请至少选择一个尺寸。"); return; }
  const form = new FormData();
  for (const file of files) form.append("files", file, file.webkitRelativePath || file.name);
  form.append("sizes", sizes.join(","));
  form.append("profile", document.getElementById("profile").value);
  form.append("format", document.getElementById("format").value);
  form.append("preserve", document.getElementById("preserve").checked ? "1" : "0");
  form.append("output", document.getElementById("output").value);
  document.getElementById("run").disabled = true;
  log(`开始处理 ${files.length} 个文件...`);
  try {
    const response = await fetch("/process", { method: "POST", body: form });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "处理失败");
    log(result.log.join("\n"));
    log(`完成，输出目录：${result.output}`);
  } catch (error) {
    log(`失败：${error.message}`);
  } finally {
    document.getElementById("run").disabled = false;
  }
};
renderFiles();
</script>
</body>
</html>
"""


class WindowsFileDrop:
    """Windows Explorer file-drop bridge for Tk widgets."""

    GWLP_WNDPROC = -4
    WM_DROPFILES = 0x0233

    def __init__(self, root: tk.Tk, widgets: Iterable[tk.Widget], on_drop) -> None:
        self.root = root
        self.widgets = list(widgets)
        self.on_drop = on_drop
        self.enabled = False
        self.targets: list[tuple[int, int, object]] = []

    def install(self) -> bool:
        if sys.platform != "win32":
            return False

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        set_window_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        self._window_proc_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        )

        set_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        set_window_long.restype = ctypes.c_void_p
        user32.CallWindowProcW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        ]
        user32.CallWindowProcW.restype = ctypes.c_ssize_t
        user32.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        user32.DefWindowProcW.restype = ctypes.c_ssize_t
        shell32.DragAcceptFiles.argtypes = [ctypes.c_void_p, ctypes.c_bool]
        shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
        ctypes.windll.shell32.DragQueryFileW.restype = ctypes.c_uint
        shell32.DragFinish.argtypes = [ctypes.c_void_p]

        for widget in self.widgets:
            hwnd = int(widget.winfo_id())
            callback = self._window_proc_type(lambda window, message, wparam, lparam, hwnd=hwnd: self.window_proc(hwnd, window, message, wparam, lparam))
            old_proc = set_window_long(ctypes.c_void_p(hwnd), self.GWLP_WNDPROC, ctypes.cast(callback, ctypes.c_void_p))
            if old_proc:
                shell32.DragAcceptFiles(ctypes.c_void_p(hwnd), True)
                self.targets.append((hwnd, int(old_proc), callback))

        if self.targets:
            self.enabled = True
            self.root.bind("<Destroy>", self.destroy, add="+")
        return self.enabled

    def destroy(self, event: object | None = None) -> None:
        if sys.platform != "win32":
            return
        if event is not None and getattr(event, "widget", None) is not self.root:
            return

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        set_window_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        for hwnd, old_proc, _callback in self.targets:
            shell32.DragAcceptFiles(ctypes.c_void_p(hwnd), False)
            set_window_long(ctypes.c_void_p(hwnd), self.GWLP_WNDPROC, ctypes.c_void_p(old_proc))
        self.targets.clear()

    def read_paths(self, hdrop: int) -> list[Path]:
        shell32 = ctypes.windll.shell32
        try:
            count = shell32.DragQueryFileW(ctypes.c_void_p(hdrop), 0xFFFFFFFF, None, 0)
            paths: list[Path] = []
            for index in range(count):
                length = shell32.DragQueryFileW(ctypes.c_void_p(hdrop), index, None, 0)
                buffer = ctypes.create_unicode_buffer(length + 1)
                shell32.DragQueryFileW(ctypes.c_void_p(hdrop), index, buffer, length + 1)
                if buffer.value:
                    paths.append(Path(buffer.value))
            return paths
        finally:
            shell32.DragFinish(ctypes.c_void_p(hdrop))

    def accept(self, hdrop: int) -> None:
        paths = self.read_paths(hdrop)
        if paths:
            self.root.after(0, self.on_drop, paths)

    def window_proc(self, hwnd: int, window: int, message: int, wparam: int, lparam: int) -> int:
        if message == self.WM_DROPFILES:
            try:
                self.accept(wparam)
            except Exception as exc:
                self.root.after(0, self.on_drop_error, exc)
            return 0

        old_proc = next((old for target_hwnd, old, _callback in self.targets if target_hwnd == hwnd), None)
        if old_proc:
            return ctypes.windll.user32.CallWindowProcW(
                ctypes.c_void_p(old_proc),
                ctypes.c_void_p(window),
                message,
                wparam,
                lparam,
            )
        return ctypes.windll.user32.DefWindowProcW(ctypes.c_void_p(window), message, wparam, lparam)

    def on_drop_error(self, exc: Exception) -> None:
        if hasattr(self.on_drop, "__self__") and hasattr(self.on_drop.__self__, "write_log"):
            self.on_drop.__self__.write_log(f"拖放读取失败：{exc}\n")


@dataclass(frozen=True)
class ResizeProfile:
    key: str
    label: str
    gamma_correct: bool
    premultiply_alpha: bool
    default_sharpen: float
    resample: int


PROFILES = {
    "detail": ResizeProfile(
        key="detail",
        label="细节保留/颜色贴图 - Lanczos + 线性光 + Alpha边缘保护",
        gamma_correct=True,
        premultiply_alpha=True,
        default_sharpen=0.18,
        resample=Image.Resampling.LANCZOS,
    ),
    "data": ResizeProfile(
        key="data",
        label="数据/法线/遮罩贴图 - Lanczos，不做Gamma与锐化",
        gamma_correct=False,
        premultiply_alpha=True,
        default_sharpen=0.0,
        resample=Image.Resampling.LANCZOS,
    ),
    "pixel": ResizeProfile(
        key="pixel",
        label="像素风/硬边 - 最近邻",
        gamma_correct=False,
        premultiply_alpha=False,
        default_sharpen=0.0,
        resample=Image.Resampling.NEAREST,
    ),
}


def srgb_to_linear(values: np.ndarray) -> np.ndarray:
    return np.where(values <= 0.04045, values / 12.92, ((values + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, 0.0, 1.0)
    return np.where(values <= 0.0031308, values * 12.92, 1.055 * (values ** (1.0 / 2.4)) - 0.055)


def iter_input_images(paths: Iterable[Path]) -> list[Path]:
    images: list[Path] = []
    for path in paths:
        if path.is_dir():
            images.extend(
                p for p in sorted(path.rglob("*")) if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
            )
        elif path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(path)
    return images


def apply_unsharp_mask(image: Image.Image, amount: float) -> Image.Image:
    if amount <= 0:
        return image
    # Downscaling softens high-frequency texture detail; keep the mask subtle to avoid halos.
    percent = int(60 + amount * 220)
    return image.filter(ImageFilter.UnsharpMask(radius=0.65, percent=percent, threshold=3))


def target_dimensions(source_size: tuple[int, int], target_edge: int, preserve_aspect: bool) -> tuple[int, int]:
    if target_edge <= 0:
        return source_size
    if not preserve_aspect:
        return target_edge, target_edge
    width, height = source_size
    if width <= 0 or height <= 0:
        return target_edge, target_edge
    scale = target_edge / max(width, height)
    return max(1, round(width * scale)), max(1, round(height * scale))


def resize_srgb(image: Image.Image, size: tuple[int, int], resample: int) -> Image.Image:
    return image.resize(size, resample=resample)


def resize_float_channel(channel: np.ndarray, size: tuple[int, int], resample: int) -> np.ndarray:
    layer = Image.fromarray(channel.astype(np.float32), mode="F")
    return np.asarray(layer.resize(size, resample=resample), dtype=np.float32)


def resize_linear_rgb(image: Image.Image, size: tuple[int, int], resample: int) -> Image.Image:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    linear = srgb_to_linear(rgb)
    resized = np.dstack([resize_float_channel(linear[:, :, index], size, resample) for index in range(3)])
    srgb = linear_to_srgb(resized)
    return Image.fromarray(np.clip(np.rint(srgb * 255.0), 0, 255).astype(np.uint8), mode="RGB")


def resize_alpha_aware(image: Image.Image, size: tuple[int, int], profile: ResizeProfile) -> Image.Image:
    if profile.resample == Image.Resampling.NEAREST:
        return image.resize(size, resample=profile.resample)

    has_alpha = image.mode in ("RGBA", "LA") or ("transparency" in image.info)
    if not has_alpha and image.mode in ("1", "L"):
        return resize_srgb(image.convert("L"), size, profile.resample)
    if not has_alpha:
        return resize_linear_rgb(image, size, profile.resample) if profile.gamma_correct else resize_srgb(image, size, profile.resample)

    rgba = image.convert("RGBA")
    red, green, blue, alpha = rgba.split()

    if not profile.premultiply_alpha:
        resized_rgb = resize_linear_rgb(rgba.convert("RGB"), size, profile.resample) if profile.gamma_correct else rgba.convert("RGB").resize(size, profile.resample)
        resized_alpha = alpha.resize(size, resample=profile.resample)
        return Image.merge("RGBA", (*resized_rgb.split(), resized_alpha))

    rgba_array = np.asarray(Image.merge("RGBA", (red, green, blue, alpha)), dtype=np.float32) / 255.0
    rgb = rgba_array[:, :, :3]
    alpha_array = rgba_array[:, :, 3:4]
    if profile.gamma_correct:
        rgb = srgb_to_linear(rgb)

    rgb = rgb * alpha_array
    resized_rgb = np.dstack([resize_float_channel(rgb[:, :, index], size, profile.resample) for index in range(3)])
    resized_alpha = resize_float_channel(alpha_array[:, :, 0], size, profile.resample)

    safe_alpha = np.where(resized_alpha > 0.00001, resized_alpha, 1.0)
    straight_rgb = resized_rgb / safe_alpha[:, :, None]
    straight_rgb[resized_alpha <= 0.00001] = 0.0
    if profile.gamma_correct:
        straight_rgb = linear_to_srgb(straight_rgb)

    out = np.dstack((straight_rgb, resized_alpha))
    return Image.fromarray(np.clip(np.rint(out * 255.0), 0, 255).astype(np.uint8), mode="RGBA")


def image_has_alpha(image: Image.Image) -> bool:
    return image.mode in ("RGBA", "LA") or "A" in image.getbands() or "transparency" in image.info


def is_gray_mode(image: Image.Image) -> bool:
    return image.mode in ("1", "L", "LA", "I", "I;16", "I;16L", "I;16B", "F")


def image_bit_depth(image: Image.Image) -> int:
    if image.mode in ("I;16", "I;16L", "I;16B"):
        return 16
    if image.mode in ("I", "F"):
        return 32
    return 8


def practical_channel_mode(image: Image.Image) -> str:
    if image_has_alpha(image):
        return "rgba32"
    if is_gray_mode(image):
        return "gray8"
    return "rgb24"


def channel_mode_label(mode: str) -> str:
    return CHANNEL_MODE_LABELS.get(mode, CHANNEL_MODE_LABELS["auto"])


def image_mode_label(image: Image.Image) -> str:
    return channel_mode_label(practical_channel_mode(image))


def normalize_channel_mode(channel_mode: str | None) -> str:
    value = (channel_mode or "auto").strip().lower()
    return value if value in CHANNEL_MODES else "auto"


def convert_channel_mode(image: Image.Image, channel_mode: str) -> tuple[Image.Image, str]:
    normalized = normalize_channel_mode(channel_mode)
    target = practical_channel_mode(image) if normalized == "auto" else normalized
    if target == "gray8":
        return image.convert("L"), target
    if target == "rgba32":
        return image.convert("RGBA"), target
    return image.convert("RGB"), "rgb24"


def prepare_image_for_format(image: Image.Image, suffix: str, target_mode: str, warnings: list[str]) -> tuple[Image.Image, str]:
    if suffix in (".jpg", ".jpeg") and image_has_alpha(image):
        warnings.append("JPG/JPEG 不支持 Alpha，已按 RGB 24位写出，透明通道会丢失")
        return image.convert("RGB"), "rgb24"
    if suffix == ".bmp" and image_has_alpha(image):
        warnings.append("BMP 在当前运行时会丢弃 Alpha，已按 RGB 24位写出")
        return image.convert("RGB"), "rgb24"
    if suffix == ".webp" and image.mode == "L":
        warnings.append("WEBP 灰度图会被运行时写成 RGB 数据")
        return image.convert("RGB"), "rgb24"
    return image, target_mode


def save_flat_psd(image: Image.Image, output_path: Path) -> None:
    """Write an 8-bit flattened grayscale/RGB/RGBA PSD.

    Pillow can read PSD composites but cannot save PSD. This tiny writer covers
    the flattened texture case users need here; layered PSD data is intentionally
    not generated.
    """
    if image.mode == "L":
        flattened = image
        color_mode = 1
    else:
        flattened = image.convert("RGBA" if image_has_alpha(image) else "RGB")
        color_mode = 3
    width, height = flattened.size
    channels = flattened.split()

    if width > 30000 or height > 30000:
        raise ValueError("PSD format supports dimensions up to 30000 pixels per side.")

    with output_path.open("wb") as handle:
        handle.write(b"8BPS")
        handle.write(struct.pack(">H", 1))
        handle.write(b"\0" * 6)
        handle.write(struct.pack(">HIIHH", len(channels), height, width, 8, color_mode))
        handle.write(struct.pack(">I", 0))  # Color mode data.
        handle.write(struct.pack(">I", 0))  # Image resources.
        handle.write(struct.pack(">I", 0))  # Layer and mask info.
        handle.write(struct.pack(">H", 0))  # Raw image data, planar channel order.
        for channel in channels:
            handle.write(channel.tobytes())


def save_image(
    image: Image.Image,
    source: Path,
    output_path: Path,
    keep_format: bool,
    icc_profile: bytes | None,
    channel_mode: str = "auto",
) -> SaveReport:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() if keep_format else output_path.suffix.lower()
    output_path = output_path.with_suffix(suffix)
    params: dict[str, object] = {}
    warnings_list: list[str] = []
    source_label = image_mode_label(image)

    if image_bit_depth(image) > 8:
        warnings_list.append("当前工具箱按 8位/通道 写出，16/32位每通道源图会被转换")

    image, resolved_mode = convert_channel_mode(image, channel_mode)
    image, resolved_mode = prepare_image_for_format(image, suffix, resolved_mode, warnings_list)

    if suffix == ".psd":
        save_flat_psd(image, output_path)
        return SaveReport(output_path, source_label, image_mode_label(image), warnings_list)

    if icc_profile:
        params["icc_profile"] = icc_profile

    if suffix in (".jpg", ".jpeg"):
        params.update({"quality": 100, "subsampling": 0, "optimize": True})
    elif suffix == ".png":
        params.update({"compress_level": 6})
    elif suffix in (".tif", ".tiff"):
        params.update({"compression": "tiff_lzw"})
    elif suffix == ".tga":
        params.update({"compression": "tga_rle"})
    elif suffix == ".webp":
        params.update({"lossless": True, "quality": 100, "method": 6, "exact": True})
    elif suffix == ".bmp":
        if image.mode not in ("RGB", "RGBA", "L"):
            image = image.convert("RGBA" if ("A" in image.getbands()) else "RGB")
    elif suffix == ".dds":
        if image.mode not in ("L", "RGB", "RGBA"):
            image = image.convert("RGBA" if image_has_alpha(image) else "RGB")

    image.save(output_path, **params)
    return SaveReport(output_path, source_label, image_mode_label(image), warnings_list)


def output_name(
    source: Path,
    size: tuple[int, int],
    output_dir: Path,
    keep_format: bool,
    format_ext: str,
    name_suffix: str = "",
    append_size_suffix: bool = True,
) -> Path:
    suffix = source.suffix if keep_format else format_ext
    width, height = size
    size_suffix = f"_{width}x{height}" if append_size_suffix else ""
    return output_dir / f"{source.stem}{size_suffix}{name_suffix}{suffix}"


def resize_one(
    source: Path,
    output_dir: Path,
    sizes: Iterable[int],
    profile: ResizeProfile,
    sharpen: float | None = None,
    keep_format: bool = True,
    format_ext: str = ".png",
    preserve_aspect: bool = True,
    channel_mode: str = "auto",
    reports: list[SaveReport] | None = None,
    name_suffix: str = "",
    append_size_suffix: bool = True,
) -> list[Path]:
    sharpen_amount = profile.default_sharpen if sharpen is None else sharpen
    written: list[Path] = []
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        icc_profile = opened.info.get("icc_profile")
        if image.mode not in ("RGB", "RGBA", "L", "LA"):
            image = image.convert("RGBA" if ("A" in image.getbands() or "transparency" in opened.info) else "RGB")

        for size in sizes:
            target_edge = int(size)
            dimensions = target_dimensions(image.size, target_edge, preserve_aspect)
            if target_edge <= 0:
                resized = image.copy()
            else:
                resized = resize_alpha_aware(image, dimensions, profile)
                resized = apply_unsharp_mask(resized, sharpen_amount)
            destination = output_name(source, dimensions, output_dir, keep_format, format_ext, name_suffix, append_size_suffix)
            report = save_image(resized, source, destination, keep_format, icc_profile, channel_mode)
            if reports is not None:
                reports.append(report)
            written.append(destination)
    return written


class TextureResizeApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Texture Image Size - 贴图缩放")
        self.root.geometry("760x620")
        self.root.minsize(680, 560)

        self.files: list[Path] = []
        self.output_dir = tk.StringVar(value=str(Path.cwd() / "resized_textures"))
        self.profile_key = tk.StringVar(value="detail")
        self.keep_format = tk.BooleanVar(value=True)
        self.format_ext = tk.StringVar(value=".png")
        self.sharpen = tk.DoubleVar(value=PROFILES["detail"].default_sharpen)
        self.size_vars = {size: tk.BooleanVar(value=size in DEFAULT_TARGET_SIZES) for size in TARGET_SIZES}
        self.custom_sizes = tk.StringVar(value="")
        self.preserve_aspect = tk.BooleanVar(value=True)
        self.drop_bridge: WindowsFileDrop | None = None

        self.build_ui()
        self.profile_combo.bind("<<ComboboxSelected>>", self.on_profile_change)

    def build_ui(self) -> None:
        pad = {"padx": 14, "pady": 8}
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)

        file_frame = ttk.LabelFrame(main, text="源图片")
        file_frame.pack(fill="both", expand=True, **pad)
        toolbar = ttk.Frame(file_frame)
        toolbar.pack(fill="x", padx=10, pady=8)
        ttk.Button(toolbar, text="添加图片", command=self.add_files).pack(side="left")
        ttk.Button(toolbar, text="添加文件夹", command=self.add_folder).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="清空", command=self.clear_files).pack(side="left", padx=(8, 0))

        self.file_list = tk.Listbox(file_frame, height=8, activestyle="none")
        self.file_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        size_frame = ttk.LabelFrame(main, text="目标图像大小")
        size_frame.pack(fill="x", **pad)
        ttk.Label(size_frame, text="常用输出尺寸：").pack(side="left", padx=(10, 8), pady=10)
        for size in TARGET_SIZES:
            ttk.Checkbutton(size_frame, text=f"{size}x{size}", variable=self.size_vars[size]).pack(side="left", padx=6)
        ttk.Label(size_frame, text="自定义").pack(side="left", padx=(12, 4), pady=10)
        ttk.Entry(size_frame, textvariable=self.custom_sizes, width=16).pack(side="left", padx=(0, 10), pady=10)
        ttk.Checkbutton(size_frame, text="锁定比例", variable=self.preserve_aspect).pack(side="left", padx=(2, 10))

        option_frame = ttk.LabelFrame(main, text="重采样设置")
        option_frame.pack(fill="x", **pad)
        ttk.Label(option_frame, text="配置").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        self.profile_combo = ttk.Combobox(
            option_frame,
            textvariable=self.profile_key,
            values=list(PROFILES.keys()),
            state="readonly",
            width=12,
        )
        self.profile_combo.grid(row=0, column=1, sticky="w", padx=8, pady=8)
        self.profile_label = ttk.Label(option_frame, text=PROFILES["detail"].label)
        self.profile_label.grid(row=0, column=2, sticky="w", padx=8, pady=8)

        ttk.Label(option_frame, text="细节锐化").grid(row=1, column=0, sticky="w", padx=10, pady=8)
        ttk.Scale(option_frame, from_=0.0, to=0.6, variable=self.sharpen, orient="horizontal").grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=8, pady=8
        )
        option_frame.columnconfigure(2, weight=1)

        output_frame = ttk.LabelFrame(main, text="输出")
        output_frame.pack(fill="x", **pad)
        ttk.Entry(output_frame, textvariable=self.output_dir).grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        ttk.Button(output_frame, text="选择目录", command=self.choose_output).grid(row=0, column=1, padx=10, pady=8)
        ttk.Checkbutton(output_frame, text="保持原格式", variable=self.keep_format).grid(row=1, column=0, sticky="w", padx=10, pady=8)
        ttk.Label(output_frame, text="否则输出").grid(row=1, column=0, sticky="w", padx=(130, 0), pady=8)
        ttk.Combobox(output_frame, textvariable=self.format_ext, values=OUTPUT_FORMATS, state="readonly", width=8).grid(
            row=1, column=0, sticky="w", padx=(210, 0), pady=8
        )
        output_frame.columnconfigure(0, weight=1)

        action_frame = ttk.Frame(main)
        action_frame.pack(fill="x", padx=14, pady=(6, 14))
        ttk.Button(action_frame, text="开始缩放", command=self.start_resize).pack(side="right")
        self.progress = ttk.Progressbar(action_frame, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.log = tk.Text(main, height=8, wrap="word")
        self.log.pack(fill="both", expand=False, padx=14, pady=(0, 14))
        self.write_log("支持 PSD/PNG/TGA/TIF/JPG 输入输出。PSD 会按合成图读取，输出为缩放后的扁平 PSD。\n")
        self.write_log("选择一张或多张贴图，然后勾选要导出的尺寸。拖放请使用网页版入口，避免 Tk 在部分 Windows 环境中崩溃。\n")

    def on_profile_change(self, _event: object | None = None) -> None:
        profile = PROFILES[self.profile_key.get()]
        self.profile_label.configure(text=profile.label)
        self.sharpen.set(profile.default_sharpen)

    def write_log(self, text: str) -> None:
        self.log.insert("end", text)
        self.log.see("end")

    def add_files(self) -> None:
        filenames = filedialog.askopenfilenames(
            title="选择贴图",
            filetypes=[("Texture Images", "*.psd *.png *.jpg *.jpeg *.tif *.tiff *.tga *.dds *.webp *.bmp"), ("All files", "*.*")],
        )
        self.add_paths(Path(name) for name in filenames)

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="选择贴图文件夹")
        if folder:
            self.add_paths([Path(folder)])

    def enable_file_drop(self) -> None:
        self.drop_bridge = WindowsFileDrop(self.root, [self.root, self.file_list], self.add_paths)
        if self.drop_bridge.install():
            self.write_log("拖放已启用：可以把图片或文件夹直接拖到列表里。\n")
        else:
            self.write_log("当前环境未启用拖放，仍可使用“添加图片/添加文件夹”。\n")

    def add_paths(self, paths: Iterable[Path]) -> None:
        existing = set(self.files)
        before = len(self.files)
        for image in iter_input_images(paths):
            if image not in existing:
                self.files.append(image)
                self.file_list.insert("end", str(image))
                existing.add(image)
        added = len(self.files) - before
        if added:
            self.write_log(f"已添加 {added} 张图片，当前待处理图片：{len(self.files)}\n")
        else:
            self.write_log(f"没有发现新的支持格式图片，当前待处理图片：{len(self.files)}\n")

    def clear_files(self) -> None:
        self.files.clear()
        self.file_list.delete(0, "end")
        self.write_log("已清空列表。\n")

    def choose_output(self) -> None:
        folder = filedialog.askdirectory(title="选择输出目录")
        if folder:
            self.output_dir.set(folder)

    def selected_sizes(self) -> list[int]:
        sizes = [size for size in TARGET_SIZES if self.size_vars[size].get()]
        custom_text = self.custom_sizes.get().strip()
        if custom_text:
            sizes.extend(parse_sizes(custom_text))
        return sorted(set(sizes), reverse=True)

    def start_resize(self) -> None:
        if not self.files:
            messagebox.showwarning("缺少源图片", "请先添加图片或文件夹。")
            return
        try:
            sizes = self.selected_sizes()
        except ValueError:
            messagebox.showwarning("尺寸格式错误", "自定义尺寸请填写数字，用逗号分隔，例如：1536,768。")
            return
        if not sizes:
            messagebox.showwarning("缺少目标尺寸", "请至少选择一个导出尺寸。")
            return
        output_dir = Path(self.output_dir.get()).expanduser()
        profile = PROFILES[self.profile_key.get()]
        total = len(self.files) * len(sizes)
        self.progress.configure(maximum=total, value=0)
        self.write_log(f"开始处理：{len(self.files)} 张图片，尺寸 {', '.join(map(str, sizes))}\n")

        def worker() -> None:
            done = 0
            errors: list[str] = []
            for source in self.files:
                try:
                    written = resize_one(
                        source=source,
                        output_dir=output_dir,
                        sizes=sizes,
                        profile=profile,
                        sharpen=float(self.sharpen.get()),
                        keep_format=bool(self.keep_format.get()),
                        format_ext=self.format_ext.get(),
                        preserve_aspect=bool(self.preserve_aspect.get()),
                    )
                    done += len(written)
                    self.root.after(0, self.write_log, f"完成 {source.name} -> {len(written)} 个文件\n")
                except Exception as exc:  # pragma: no cover - GUI path.
                    errors.append(f"{source}: {exc}")
                    self.root.after(0, self.write_log, f"失败 {source.name}: {exc}\n")
                self.root.after(0, self.progress.configure, {"value": done})
            if errors:
                self.root.after(0, messagebox.showerror, "部分失败", "\n".join(errors[:8]))
            else:
                self.root.after(0, messagebox.showinfo, "完成", f"已输出到：{output_dir}")

        threading.Thread(target=worker, daemon=True).start()


def parse_sizes(text: str) -> list[int]:
    aliases = {
        "original": 0,
        "source": 0,
        "原尺寸": 0,
        "1k": 1024,
        "2k": 2048,
        "4k": 4096,
        "8k": 8192,
        "16k": 16384,
    }
    sizes = []
    for part in text.replace(";", ",").split(","):
        value = part.strip().lower()
        if not value:
            continue
        if value in aliases:
            number = aliases[value]
        else:
            number = int(value.replace("x", ""))
        if number < 0:
            raise ValueError("size must be positive")
        sizes.append(number)
    return sizes


def safe_upload_name(value: str, index: int) -> str:
    name = Path(value.replace("\\", "/")).name
    stem = Path(name).stem or f"texture_{index}"
    suffix = Path(name).suffix.lower()
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".", " ") else "_" for ch in stem).strip()
    return f"{cleaned or f'texture_{index}'}{suffix}"


class TextureWebHandler(BaseHTTPRequestHandler):
    server_version = "TextureResizer/1.0"

    def log_message(self, _format: str, *args: object) -> None:
        return

    def send_text(self, status: int, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status: int, payload: dict[str, object]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path not in ("/", "/index.html"):
            self.send_text(404, "Not found")
            return
        output = html.escape(str(DEFAULT_OUTPUT_DIR))
        self.send_text(200, WEB_PAGE.replace("__OUTPUT_DIR__", output), "text/html; charset=utf-8")

    def do_POST(self) -> None:
        if self.path == "/shutdown":
            self.send_json(200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path != "/process":
            self.send_json(404, {"ok": False, "error": "Not found"})
            return
        try:
            self.handle_process()
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})

    def handle_process(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_json(400, {"ok": False, "error": "Expected multipart form data"})
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
        )

        sizes = parse_sizes(form.getfirst("sizes", "2048,1024,512,256"))
        profile = PROFILES[form.getfirst("profile", "detail")]
        output_dir = Path(form.getfirst("output", str(DEFAULT_OUTPUT_DIR))).expanduser()
        output_format = form.getfirst("format", "keep")
        keep_format = output_format == "keep"
        format_ext = f".{output_format}" if not keep_format else ".png"
        preserve_aspect = form.getfirst("preserve", "1") == "1"

        fields = form["files"] if "files" in form else []
        if not isinstance(fields, list):
            fields = [fields]
        file_fields = [field for field in fields if getattr(field, "filename", None)]
        if not file_fields:
            self.send_json(400, {"ok": False, "error": "No uploaded images"})
            return

        upload_dir = Path.cwd() / ".texture_resizer_uploads" / str(int(time.time() * 1000))
        upload_dir.mkdir(parents=True, exist_ok=True)
        log_lines: list[str] = []
        try:
            for index, field in enumerate(file_fields, start=1):
                source_name = safe_upload_name(field.filename, index)
                if Path(source_name).suffix.lower() not in IMAGE_EXTENSIONS:
                    log_lines.append(f"跳过不支持格式：{field.filename}")
                    continue
                item_dir = upload_dir / f"{index:04d}"
                item_dir.mkdir(parents=True, exist_ok=True)
                source_path = item_dir / source_name
                with source_path.open("wb") as handle:
                    handle.write(field.file.read())
                written = resize_one(
                    source=source_path,
                    output_dir=output_dir,
                    sizes=sizes,
                    profile=profile,
                    keep_format=keep_format,
                    format_ext=format_ext,
                    preserve_aspect=preserve_aspect,
                )
                log_lines.append(f"{field.filename} -> " + ", ".join(path.name for path in written))
        finally:
            for path in sorted(upload_dir.rglob("*"), reverse=True):
                try:
                    if path.is_dir():
                        path.rmdir()
                    else:
                        path.unlink()
                except OSError:
                    pass
            try:
                upload_dir.rmdir()
            except OSError:
                pass
            try:
                upload_dir.parent.rmdir()
            except OSError:
                pass

        self.send_json(200, {"ok": True, "output": str(output_dir), "log": log_lines})


def run_web(port: int = 8765) -> int:
    server: ThreadingHTTPServer | None = None
    last_error: OSError | None = None
    for candidate in range(port, port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), TextureWebHandler)
            port = candidate
            break
        except OSError as exc:
            last_error = exc
    if server is None:
        raise RuntimeError(f"Cannot start local web server: {last_error}")

    url = f"http://127.0.0.1:{port}/"
    threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    print(f"Texture resizer web UI: {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="High-quality texture image-size tool.")
    parser.add_argument("inputs", nargs="*", type=Path, help="Image files or folders.")
    parser.add_argument("-o", "--output", type=Path, default=Path("resized_textures"), help="Output folder.")
    parser.add_argument("-s", "--sizes", default="2048,1024,512,256", help="Comma-separated square sizes.")
    parser.add_argument("-p", "--profile", choices=sorted(PROFILES), default="detail", help="Resize profile.")
    parser.add_argument("--sharpen", type=float, default=None, help="Sharpen amount, 0 to 0.6. Defaults to profile value.")
    parser.add_argument("--format", default="keep", choices=("keep", "psd", "png", "tga", "tif", "tiff", "jpg", "jpeg", "dds", "webp", "bmp"), help="Output format.")
    parser.add_argument("--stretch-square", action="store_true", help="Force exact square output instead of preserving aspect ratio.")
    parser.add_argument("--gui", action="store_true", help="Open the graphical interface.")
    parser.add_argument("--web", action="store_true", help="Open the browser drag-and-drop interface.")
    parser.add_argument("--port", type=int, default=8765, help="Web interface port.")
    return parser


def run_cli(args: argparse.Namespace) -> int:
    images = iter_input_images(args.inputs)
    if not images:
        print("No input images found. Use --gui for the graphical interface.", file=sys.stderr)
        return 2

    sizes = parse_sizes(args.sizes)
    profile = PROFILES[args.profile]
    keep_format = args.format == "keep"
    format_ext = f".{args.format}" if not keep_format else ".png"
    total = len(images) * len(sizes)
    current = 0

    for image in images:
        written = resize_one(
            source=image,
            output_dir=args.output,
            sizes=sizes,
            profile=profile,
            sharpen=args.sharpen,
            keep_format=keep_format,
            format_ext=format_ext,
            preserve_aspect=not args.stretch_square,
        )
        current += len(written)
        print(f"[{current}/{total}] {image.name}: " + ", ".join(path.name for path in written))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.web:
        return run_web(args.port)
    if args.gui or not args.inputs:
        if tk is None:
            print("Tkinter is not available; use command-line inputs instead.", file=sys.stderr)
            return 2
        root = tk.Tk()
        TextureResizeApp(root)
        root.mainloop()
        return 0
    return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
