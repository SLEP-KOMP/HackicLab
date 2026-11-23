r"""Проверка EFI в виртуальной машине QEMU: доходит ли до меню OpenCore.

Скрипт делает то, что руками повторять долго: поднимает VHD с FAT32, кладёт
EFI, стартует QEMU с прошивкой OVMF, снимает экран и проверяет, что на нём
появилось меню загрузчика. Нужен установленный QEMU и права администратора
(diskpart).

    python tools/vm_boot_test.py --efi out\EFI
    python tools/vm_boot_test.py --efi out\EFI --keep     # оставить VHD и снимок
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

QEMU_CANDIDATES = (
    Path(os.environ.get("QEMU_DIR", r"C:\Program Files\qemu")),
    Path(r"C:\Program Files\qemu"),
    Path(r"C:\Program Files (x86)\qemu"),
)
VHD_MB = 256
DISKPART_TIMEOUT = 180


# ---------- QEMU и прошивка ----------
def find_qemu() -> tuple[Path, Path]:
    """Путь к qemu-system-x86_64.exe и к прошивке edk2-x86_64-code.fd."""
    for folder in QEMU_CANDIDATES:
        exe = folder / "qemu-system-x86_64.exe"
        fw = folder / "share" / "edk2-x86_64-code.fd"
        if exe.is_file() and fw.is_file():
            return exe, fw
    raise SystemExit("QEMU не найден: установите его (winget install SoftwareFreedomConservancy.QEMU)")


def find_vars(qemu_dir: Path) -> Path | None:
    """Шаблон NVRAM для OVMF; без него прошивка не сохранит настройки."""
    for name in ("edk2-i386-vars.fd", "edk2-x86_64-vars.fd"):
        candidate = qemu_dir / "share" / name
        if candidate.is_file():
            return candidate
    return None


# ---------- диск ----------
def _diskpart(script: str) -> None:
    work = Path(tempfile.mkdtemp(prefix="hl-diskpart-"))
    try:
        path = work / "script.txt"
        path.write_text(script, encoding="ascii")
        done = subprocess.run(["diskpart", "/s", str(path)], capture_output=True,
                              text=True, encoding="cp866", timeout=DISKPART_TIMEOUT)
        if done.returncode != 0:
            raise RuntimeError(f"diskpart: {done.stdout[-400:]}{done.stderr[-200:]}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _free_letter() -> str:
    """Свободная буква диска для VHD (Z, Y, X…)."""
    for letter in "ZYXWVU":
        if not Path(f"{letter}:\\").exists():
            return letter
    raise RuntimeError("нет свободной буквы диска для VHD")


def make_disk(vhd: Path, efi: Path, letter: str) -> None:
    """Создаёт VHD, размечает FAT32, копирует EFI и отключает диск."""
    _diskpart(
        f'create vdisk file="{vhd}" maximum={VHD_MB} type=fixed\n'
        f'select vdisk file="{vhd}"\n'
        "attach vdisk\n"
        "create partition primary\n"
        f"format fs=fat32 quick label=EFITEST\n"
        f"assign letter={letter}\n"
        "exit\n"
    )
    try:
        shutil.copytree(Path(efi) / "EFI", Path(f"{letter}:\\EFI"), dirs_exist_ok=True)
    finally:
        _diskpart(f'select vdisk file="{vhd}"\ndetach vdisk\nexit\n')


# ---------- экран ----------
def parse_ppm(data: bytes) -> tuple[int, int, bytes]:
    """Разбирает P6-PPM из screendump QEMU: ширина, высота, RGB-пиксели."""
    if not data.startswith(b"P6"):
        raise ValueError("не PPM P6")
    parts = []
    pos = 2
    while len(parts) < 3:
        while data[pos:pos + 1].isspace():
            pos += 1
        start = pos
        while not data[pos:pos + 1].isspace():
            pos += 1
        parts.append(int(data[start:pos]))
    pos += 1
    width, height, _maxval = parts
    return width, height, data[pos:pos + width * height * 3]


def menu_score(pixels: bytes, width: int, height: int) -> float:
    """Доля ярких пикселей в верхней четверти экрана.

    Меню OpenCore — светлый текст на чёрном в левом верхнем углу. QEMU
    отдаёт его серым (антиалиасинг, максимум около 190), поэтому порог 120,
    а не 255: на пустом экране ярких точек нет вовсе.
    """
    rows = max(1, height // 4)
    stride = width * 3
    bright = 0
    for row in range(rows):
        line = pixels[row * stride:(row + 1) * stride]
        for x in range(0, len(line), 3):
            if line[x] > 120 and line[x + 1] > 120 and line[x + 2] > 120:
                bright += 1
    return bright / float(rows * width)


def screendump(port: int, path: Path, timeout: float = 10.0) -> bool:
    """Просит монитор QEMU сохранить текущий экран в PPM."""
    path.unlink(missing_ok=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=3) as sock:
                stream = sock.makefile("w", encoding="ascii", newline="\n")
                stream.write(f"screendump {path.as_posix()}\n")
                stream.flush()
                time.sleep(2)
            return path.exists()
        except OSError:
            time.sleep(1)
    return False


def wait_for_menu(port: int, shot: Path, deadline_seconds: float,
                  threshold: float = 0.002) -> tuple[bool, float]:
    """Снимает экран, пока не появится меню загрузчика или не выйдет время."""
    deadline = time.time() + max(5.0, deadline_seconds)
    score = 0.0
    while time.time() < deadline:
        time.sleep(5)
        if not screendump(port, shot):
            continue
        width, height, pixels = parse_ppm(shot.read_bytes())
        score = menu_score(pixels, width, height)
        if score > threshold:
            return True, score
    return False, score


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ---------- запуск ----------
def boot_test(efi: Path, wait: float = 70.0, keep: bool = False) -> tuple[bool, Path | None]:
    if os.name != "nt":
        raise SystemExit("Проверка рассчитана на Windows: нужен diskpart и QEMU")
    efi = Path(efi).resolve()
    if not (efi / "EFI").is_dir():
        raise SystemExit(f"В {efi} нет папки EFI")

    qemu, firmware = find_qemu()
    work = Path(tempfile.mkdtemp(prefix="hl-vmboot-"))
    vhd = work / "efi-test.vhd"
    shot = work / "screen.ppm"
    vars_src = find_vars(qemu.parent)
    vars_file = work / "vars.fd"
    if vars_src:
        shutil.copy2(vars_src, vars_file)

    port = free_port()
    args = [str(qemu), "-m", "2048", "-smp", "2", "-machine", "q35",
            "-drive", f"if=pflash,format=raw,readonly=on,file={firmware}"]
    if vars_src:
        args += ["-drive", f"if=pflash,format=raw,file={vars_file}"]
    args += ["-drive", f"file={vhd},format=raw,if=ide",
             "-vga", "std", "-display", "none", "-net", "none",
             "-monitor", f"tcp:127.0.0.1:{port},server,nowait"]
    process = None
    ok = False
    try:
        letter = _free_letter()
        make_disk(vhd, efi, letter)
        process = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        time.sleep(8)
        if process.poll() is not None:
            raise RuntimeError("QEMU завершился сразу — проверьте прошивку и диск")
        ok, score = wait_for_menu(port, shot, wait)
        print(f"ярких пикселей в меню: {score:.4%}")
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        try:
            _diskpart(f'select vdisk file="{vhd}"\ndetach vdisk\nexit\n')
        except Exception:
            pass
        if not keep:
            shutil.rmtree(work, ignore_errors=True)
            shot = None
        else:
            print(f"файлы: {work}")
    return ok, shot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Прогон EFI в QEMU до меню OpenCore")
    parser.add_argument("--efi", required=True, help="папка EFI (внутри — EFI/BOOT и EFI/OC)")
    parser.add_argument("--wait", type=float, default=70.0,
                        help="сколько секунд ждать меню загрузчика")
    parser.add_argument("--keep", action="store_true", help="не удалять VHD и снимок")
    args = parser.parse_args(argv)

    ok, _shot = boot_test(Path(args.efi), wait=args.wait, keep=args.keep)
    print("РЕЗУЛЬТАТ:", "меню OpenCore найдено" if ok else "меню не найдено")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
