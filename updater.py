from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.request import Request, urlopen

CURRENT_VERSION = "v1.0"
DEFAULT_REPO = "ReinaldoAssis/ConciliaCaixa"
SETTINGS_FILE = "updater_config.json"


def _settings_path() -> Path:
    from utils import app_data_dir

    return app_data_dir() / SETTINGS_FILE


def load_settings() -> dict:
    path = _settings_path()
    if path.exists():
        try:
            with open(path, "r") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {"repo": DEFAULT_REPO, "check_on_startup": True}


def save_settings(settings: dict) -> None:
    with open(_settings_path(), "w") as fh:
        json.dump(settings, fh, indent=2)


def _get_latest_release(repo: str) -> dict | None:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "CaixaPos-Updater"})
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def check_for_updates(repo: str) -> dict | None:
    release = _get_latest_release(repo)
    if not release:
        return None
    tag = release.get("tag_name", "")
    if tag != CURRENT_VERSION:
        return {
            "version": tag,
            "url": release.get("html_url", ""),
            "assets": release.get("assets", []),
            "body": release.get("body", ""),
        }
    return None


def _download(url: str, dest: Path) -> None:
    req = Request(url, headers={"User-Agent": "CaixaPos-Updater"})
    with urlopen(req, timeout=300) as resp:
        dest.write_bytes(resp.read())


def apply_update(asset_url: str) -> None:
    ext = ".exe" if os.name == "nt" else ""
    current = Path(sys.executable)
    if getattr(sys, "frozen", False):
        binary = current
    else:
        messagebox.showinfo("Atualizacao", "Execute o aplicativo compilado para usar a atualizacao automatica.")
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        new_binary = tmp_dir / f"CaixaPos{ext}"
        _download(asset_url, new_binary)

        if os.name == "nt":
            old = binary.with_suffix(".old.exe")
            if old.exists():
                old.unlink()
            binary.rename(old)
            new_binary.rename(binary)
            messagebox.showinfo(
                "Atualizacao concluida",
                "O CaixaPos foi atualizado. Reinicie o aplicativo.",
            )
        else:
            os.chmod(new_binary, 0o755)
            old = binary.with_suffix(".old")
            if old.exists():
                old.unlink()
            binary.rename(old)
            new_binary.rename(binary)
            messagebox.showinfo(
                "Atualizacao concluida",
                "O CaixaPos foi atualizado. Reinicie o aplicativo.",
            )


class UpdateConfigDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Configuracoes de Atualizacao")
        self.geometry("520x340")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.settings = load_settings()
        self._build()

    def _build(self):
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Repositorio GitHub", font=("", 11, "bold")).pack(anchor="w")
        repo_row = ttk.Frame(frame)
        repo_row.pack(fill="x", pady=(4, 0))
        repo_prefix = ttk.Label(repo_row, text="github.com/")
        repo_prefix.pack(side="left")
        self.repo_var = tk.StringVar(value=self.settings.get("repo", DEFAULT_REPO))
        ttk.Entry(repo_row, textvariable=self.repo_var, width=36).pack(side="left")

        self.check_var = tk.BooleanVar(value=self.settings.get("check_on_startup", True))
        ttk.Checkbutton(
            frame, text="Verificar atualizacoes ao iniciar", variable=self.check_var
        ).pack(anchor="w", pady=(12, 0))

        ttk.Label(frame, text=f"Versao atual: {CURRENT_VERSION}", font=("", 10)).pack(anchor="w", pady=(12, 4))

        self.status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.status_var, wraplength=480).pack(anchor="w", pady=(4, 0))

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill="x", pady=(16, 0))
        ttk.Button(btn_row, text="Verificar Agora", command=self._check_now).pack(side="left")
        ttk.Button(btn_row, text="Salvar", command=self._save).pack(side="right")
        ttk.Button(btn_row, text="Fechar", command=self.destroy).pack(side="right", padx=6)

    def _check_now(self):
        self.status_var.set("Verificando...")
        repo = self.repo_var.get().strip() or DEFAULT_REPO

        def worker():
            update = check_for_updates(repo)
            self.after(0, lambda: self._on_check_result(update))

        threading.Thread(target=worker, daemon=True).start()

    def _on_check_result(self, update: dict | None):
        if update is None:
            self.status_var.set("Nenhuma atualizacao disponivel.")
        else:
            self.status_var.set(f"Nova versao disponivel: {update['version']}")

            def download():
                asset = None
                for a in update.get("assets", []):
                    name = a.get("name", "")
                    if os.name == "nt" and "windows" in name.lower():
                        asset = a
                        break
                    if os.name != "nt" and "macos" in name.lower():
                        asset = a
                        break
                if asset:
                    apply_update(asset["browser_download_url"])

            ttk.Button(
                self.status_var._tk_master if hasattr(self.status_var, "_tk_master") else self,
                text="Baixar e instalar",
                command=download,
            ).pack()

    def _save(self):
        self.settings["repo"] = self.repo_var.get().strip() or DEFAULT_REPO
        self.settings["check_on_startup"] = self.check_var.get()
        save_settings(self.settings)
        self.status_var.set("Configuracoes salvas.")
