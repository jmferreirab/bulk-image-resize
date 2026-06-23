# Bulk Image Resize

A simple, small utility for batch-resizing images using Pillow to optimize overly large images for general use.

**Quickstart**

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
python main.py PATH_TO_PROCESS
```

**Encoding defaults**

- JPEG defaults: `quality=80`, `optimize=True`, `progressive=False`, `subsampling=0`
