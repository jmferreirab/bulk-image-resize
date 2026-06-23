# Bulk Image Resize

A simple, small utility for batch-resizing images using Pillow to optimize overly large images for general use.

**Quickstart**

- With UV:

```bash
uv sync
.venv\Scripts\Activate.ps1
python main.py FOLDER_WITH_IMAGES
```

- Without:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
python main.py FOLDER_WITH_IMAGES
```

**Safety**

Original images are not affected. Resized images are saved to a new folder named `{root}_resized` in a sibling folder to the given `root` directory.

By default all images will be name using a suffix and .jpg extension. For example, `image03.jpg` will be saved as `image03-subsampling-0,qq-80.jpg`

**Encoding settings**

A suggested, reasonable balance between quality and file size for JPEG images:

- `quality=80`
- `optimize=True`
- `progressive=False`
- `subsampling=0`
- `MAX_MEGAPIXELS`: 16

**Motivation**

Modern phones and cameras can produce images that are far larger than necessary for general use. For example, a 16MP image is often more than enough for most purposes, yet many devices produce images that are 60MP or larger, resulting in slower browsing and previews, higher bandwidth usage, and more storage space consumed.
