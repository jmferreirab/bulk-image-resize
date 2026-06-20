import argparse
import logging
import math
import multiprocessing as mp
import os
import shutil
from pathlib import Path

from PIL import Image
from send2trash import send2trash
from tqdm import tqdm

MAX_MP = 16
MAX_PIXELS = MAX_MP * 1_000_000

# Quality setting for JPEG encoder.
# "keep" will internally force reusing the original subsampling setting.
JPEG_QUALITY = [80, "medium", "keep"][0]
# 0 = no subsampling, 1 = medium, 2 = high, improves file size sacrificing quality.
SUBSAMPLING = [0, 1, 2][0]

Image.MAX_IMAGE_PIXELS = None


def configure_logging(log_file: Path):
    logging.basicConfig(
        filename=str(log_file),
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def format_size(bytes_size):
    return f"{bytes_size / 1024:.1f} KB"


def compute_target_size(width: int, height: int):
    pixels = width * height

    if pixels <= MAX_PIXELS:
        return None

    scale = math.sqrt(MAX_PIXELS / pixels)

    new_width = (round(width * scale) // 2) * 2

    new_height = round(new_width * height / width)

    return new_width, new_height


def process_image(task):
    source_file, destination_file = task
    original_size_bytes = source_file.stat().st_size

    try:
        with Image.open(source_file) as img:
            width, height = img.size
            pixels = width * height

            if pixels <= MAX_PIXELS:
                return {
                    "status": "skipped",
                    "file": str(source_file),
                    "reason": f"{pixels:,} pixels <= {MAX_PIXELS:,}",
                    "size_bytes": original_size_bytes,
                }

            exif_bytes = img.info.get("exif")

            target_size = compute_target_size(width, height)

            resized = img.resize(
                target_size,
                Image.Resampling.LANCZOS,
            )

            destination_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            save_kwargs = {
                "quality": JPEG_QUALITY,
                "optimize": True,
                "subsampling": SUBSAMPLING,
            }

            if exif_bytes:
                save_kwargs["exif"] = exif_bytes

            resized.save(
                destination_file,
                format="JPEG",
                **save_kwargs,
            )

            shutil.copystat(
                source_file,
                destination_file,
                follow_symlinks=True,
            )

            new_size_bytes = destination_file.stat().st_size

            return {
                "status": "resized",
                "file": str(destination_file),
                "old_size": (width, height),
                "new_size": target_size,
                "original_bytes": original_size_bytes,
                "new_bytes": new_size_bytes,
            }

    except Exception as exc:
        return {
            "status": "error",
            "file": str(source_file),
            "error": str(exc),
        }


def discover_jpegs(root: Path):
    extensions = {
        ".jpg",
        ".jpeg",
        ".JPG",
        ".JPEG",
    }

    return [
        p for p in root.rglob("*") if p.is_file() and p.suffix in extensions
    ]


def build_tasks(source_root: Path, destination_root: Path, suffix: str = ""):
    tasks = []

    for source_file in discover_jpegs(source_root):
        relative = source_file.relative_to(source_root)

        destination_file = destination_root / relative

        destination_file = destination_file.with_name(
            f"{destination_file.stem}{suffix}.jpg"
        )

        tasks.append(
            (
                source_file,
                destination_file,
            )
        )

    return tasks


def main(folder, jobs=8):
    if folder is None:
        parser = argparse.ArgumentParser(
            description="Resize JPEGs larger than 16 MP."
        )

        parser.add_argument(
            "folder",
            help="Source folder",
        )

        parser.add_argument(
            "-j",
            "--jobs",
            type=int,
            default=os.cpu_count(),
            help="Worker processes",
        )

        args = parser.parse_args()

    folder = folder or args.folder
    jobs = jobs or args.jobs

    source_root = Path(folder).resolve()

    if not source_root.exists():
        raise SystemExit(f"Folder not found: {source_root}")

    destination_root = source_root.parent / (source_root.name + "_resized")

    destination_root.mkdir(
        exist_ok=True,
        parents=True,
    )

    log_file = destination_root / "resize.log"

    configure_logging(log_file)

    tasks = build_tasks(
        source_root,
        destination_root,
        suffix=f"-subsampling-{SUBSAMPLING},qq-{JPEG_QUALITY}",
    )

    logging.info(
        "Found %d JPEG files",
        len(tasks),
    )

    resized_count = 0
    skipped_count = 0
    error_count = 0
    storage_saved = 0

    with mp.Pool(processes=jobs) as pool:
        for result in tqdm(
            pool.imap_unordered(
                process_image,
                tasks,
            ),
            total=len(tasks),
            desc="Processing",
        ):
            if result["status"] == "resized":
                ratio = 100 * (
                    1 - result["new_bytes"] / result["original_bytes"]
                )

                # delete file when the size reduction is less than 25%
                if ratio < 25:
                    skipped_count += 1
                    logging.info(
                        "REMOVED:\n %s | %s -> %s diff %.1f%%",
                        result["file"],
                        format_size(result["original_bytes"]),
                        format_size(result["new_bytes"]),
                        ratio,
                    )

                    send2trash(result["file"])
                    continue

                resized_count += 1
                storage_saved += result["original_bytes"] - result["new_bytes"]
                logging.info(
                    "RESIZED:\n %s | %s -> %s | %s -> %s saved %.1f%%",
                    result["file"],
                    result["old_size"],
                    result["new_size"],
                    format_size(result["original_bytes"]),
                    format_size(result["new_bytes"]),
                    ratio,
                )

            elif result["status"] == "skipped":
                skipped_count += 1

                logging.info(
                    "SKIPPED:\n %s | %s | size=%s",
                    result["file"],
                    result["reason"],
                    format_size(result["size_bytes"]),
                )

            else:
                error_count += 1

                logging.error(
                    "ERROR: %s | %s",
                    result["file"],
                    result["error"],
                )

    logging.info(
        "Finished. Resized=%d Skipped=%d Errors=%d KB saved=%.1f",
        resized_count,
        skipped_count,
        error_count,
        format_size(storage_saved),
    )

    print()
    print(f"Output folder : {destination_root}")
    print(f"Log file      : {log_file}")
    print(f"Resized       : {resized_count}")
    print(f"Skipped       : {skipped_count}")
    print(f"Errors        : {error_count}")
    print(f"Storage saved : {format_size(storage_saved)}")


if __name__ == "__main__":
    main()
