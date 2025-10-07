from __future__ import annotations

import argparse
import ftplib
import os
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox
from typing import Iterable, List, Optional, Tuple

from bs4 import BeautifulSoup


USE_FTP = True
FTP_HOST = "31.31.196.76"
FTP_USER = "u3275410"
FTP_PASS = "f7V3ovB90qm4AOAw"
REMOTE_DIR = "www/bkbox.shop"
REMOTE_FILE = "page81046126.html"


class MenuEditor:
    """Editor class encapsulating all logic for modifying the menu HTML.

    When ``ftp_host`` is provided the editor will download the HTML
    document from the remote server before loading it and will upload
    the modified document back on save.
    """

    def __init__(
        self,
        root: tk.Tk,
        html_path: str,
        ftp_host: Optional[str] = None,
        ftp_user: Optional[str] = None,
        ftp_pass: Optional[str] = None,
        remote_dir: Optional[str] = None,
        remote_file: Optional[str] = None,
    ) -> None:
        self.root = root
        self.root.title("BKbox Menu Editor")
        # FTP configuration
        self.ftp_host = ftp_host
        self.ftp_user = ftp_user
        self.ftp_pass = ftp_pass
        self.remote_dir = remote_dir
        self.remote_file = remote_file

        # Determine the local HTML path.  When using FTP we
        # download to a temporary file so that edits occur on a
        # filesystem-backed file that can later be uploaded.
        if self.ftp_host and self.ftp_user and self.ftp_pass:
            # Use provided local path as a working copy or create a temp file
            # if the user passed a directory (e.g. '.' or none).  We retain
            # the extension for proper syntax highlighting by editors.
            if os.path.isdir(html_path):
                base_name = self.remote_file or "page81046126.html"
                fd, local_path = tempfile.mkstemp(prefix="bkbox_", suffix=os.path.splitext(base_name)[1])
                os.close(fd)
            else:
                local_path = html_path
            self.html_path = local_path
            try:
                self._ftp_download()
            except Exception as exc:
                messagebox.showerror("FTP download error", f"Failed to download remote file: {exc}")
        else:
            # operate on local file directly
            self.html_path = html_path

        # Initialise soup and UI
        self.reload_soup()
        self.create_widgets()
        self.refresh_lists()

    # ------------------------------------------------------------------
    # FTP helpers
    #
    def _ftp_connect(self) -> ftplib.FTP:
        """Establish and return an FTP connection using stored credentials."""
        if not (self.ftp_host and self.ftp_user and self.ftp_pass):
            raise ValueError("FTP credentials are incomplete")
        ftp = ftplib.FTP(self.ftp_host, timeout=30)
        ftp.login(self.ftp_user, self.ftp_pass)
        # Navigate to remote directory if specified
        if self.remote_dir:
            # Support nested path specification with forward slashes
            for part in self.remote_dir.split("/"):
                if part:
                    ftp.cwd(part)
        return ftp

    def _ftp_download(self) -> None:
        """Download the remote HTML file into self.html_path."""
        if not self.remote_file:
            raise ValueError("remote_file must be specified for FTP download")
        ftp = self._ftp_connect()
        try:
            with open(self.html_path, "wb") as f:
                ftp.retrbinary(f"RETR {self.remote_file}", f.write)
        finally:
            ftp.quit()

    def _ftp_upload(self) -> None:
        """Upload the local HTML file back to the remote server."""
        if not self.remote_file:
            raise ValueError("remote_file must be specified for FTP upload")
        ftp = self._ftp_connect()
        try:
            with open(self.html_path, "rb") as f:
                ftp.storbinary(f"STOR {self.remote_file}", f)
        finally:
            ftp.quit()

    # ------------------------------------------------------------------
    # Core HTML operations
    #
    def reload_soup(self) -> None:
        """Load the HTML file and parse it into BeautifulSoup."""
        try:
            with open(self.html_path, "r", encoding="utf-8") as f:
                contents = f.read()
        except FileNotFoundError:
            messagebox.showerror("File not found", f"Could not open file: {self.html_path}")
            sys.exit(1)
        # Parse the HTML
        self.soup = BeautifulSoup(contents, "html.parser")
        # Identify the sections; keep references for later modifications
        self.hits_catalog = self.soup.find("div", class_="hits-catalog")
        self.product_catalog = self.soup.find("div", class_="product-catalog")
        if not self.hits_catalog or not self.product_catalog:
            messagebox.showerror(
                "Invalid template",
                "The provided HTML file does not contain required sections."
            )
            sys.exit(1)

    def save_soup(self) -> None:
        """Write the current soup back to the HTML file and optionally upload via FTP."""
        # Write local file
        with open(self.html_path, "w", encoding="utf-8") as f:
            f.write(str(self.soup))
        # Upload if FTP is configured
        if self.ftp_host and self.ftp_user and self.ftp_pass:
            try:
                self._ftp_upload()
            except Exception as exc:
                messagebox.showerror("FTP upload error", f"Failed to upload remote file: {exc}")

    def extract_items(self, section: str) -> List[Tuple[str, BeautifulSoup]]:
        """Return a list of (name, element) pairs for a given section.

        :param section: either 'hits' or 'catalog'
        """
        container = self.hits_catalog if section == "hits" else self.product_catalog
        items: List[Tuple[str, BeautifulSoup]] = []
        # We use recursive=False so only direct product-item children are returned.
        for item_div in container.find_all("div", class_="product-item", recursive=False):
            name_tag = item_div.find("p", class_="product-name")
            name = name_tag.get_text(strip=True) if name_tag else "Unnamed"
            items.append((name, item_div))
        return items

    # ------------------------------------------------------------------
    # Tkinter GUI setup
    #
    def create_widgets(self) -> None:
        """Set up the Tkinter user interface."""
        # Parent frames for hits and catalog lists
        frame_hits = tk.LabelFrame(self.root, text="Наши хиты", padx=10, pady=10)
        frame_hits.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        frame_catalog = tk.LabelFrame(self.root, text="Весь каталог", padx=10, pady=10)
        frame_catalog.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        # Configure root grid to stretch frames evenly
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Hits Listbox and scroll
        self.hits_var = tk.StringVar(value=[])
        self.hits_listbox = tk.Listbox(frame_hits, listvariable=self.hits_var, height=15)
        self.hits_listbox.pack(fill="both", expand=True)
        # Buttons for hits actions
        btn_hits_add = tk.Button(frame_hits, text="Добавить", command=lambda: self.open_add_dialog("hits"))
        btn_hits_remove = tk.Button(frame_hits, text="Удалить", command=lambda: self.remove_selected("hits"))
        btn_hits_add.pack(side="left", padx=5, pady=5, expand=True, fill="x")
        btn_hits_remove.pack(side="right", padx=5, pady=5, expand=True, fill="x")

        # Catalog Listbox and scroll
        self.catalog_var = tk.StringVar(value=[])
        self.catalog_listbox = tk.Listbox(frame_catalog, listvariable=self.catalog_var, height=15)
        self.catalog_listbox.pack(fill="both", expand=True)
        # Buttons for catalog actions
        btn_catalog_add = tk.Button(frame_catalog, text="Добавить", command=lambda: self.open_add_dialog("catalog"))
        btn_catalog_remove = tk.Button(frame_catalog, text="Удалить", command=lambda: self.remove_selected("catalog"))
        btn_catalog_add.pack(side="left", padx=5, pady=5, expand=True, fill="x")
        btn_catalog_remove.pack(side="right", padx=5, pady=5, expand=True, fill="x")

        # Save button
        self.save_button = tk.Button(self.root, text="Сохранить изменения", command=self.save_changes)
        self.save_button.grid(row=1, column=0, columnspan=2, pady=(0, 10), padx=10, sticky="ew")

    def refresh_lists(self) -> None:
        """Refresh the contents of the listboxes from the current soup."""
        hits_names = [name for name, _ in self.extract_items("hits")]
        catalog_names = [name for name, _ in self.extract_items("catalog")]
        self.hits_var.set(hits_names)
        self.catalog_var.set(catalog_names)

    def open_add_dialog(self, section: str) -> None:
        """Open a pop‑up dialog to add a new item to the given section."""
        # Create a new top‑level window
        dialog = tk.Toplevel(self.root)
        dialog.title("Добавить блюдо")
        dialog.grab_set()  # modal
        # Form fields
        tk.Label(dialog, text="Название:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        name_entry = tk.Entry(dialog, width=40)
        name_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(dialog, text="Цена (например, 3 690 ₽):").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        price_entry = tk.Entry(dialog, width=40)
        price_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(dialog, text="URL изображения:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        img_entry = tk.Entry(dialog, width=40)
        img_entry.grid(row=2, column=1, padx=5, pady=5)

        tk.Label(dialog, text="Описание (каждый пункт на новой строке):").grid(row=3, column=0, sticky="ne", padx=5, pady=5)
        desc_text = tk.Text(dialog, width=30, height=6)
        desc_text.grid(row=3, column=1, padx=5, pady=5)

        def add_action() -> None:
            name = name_entry.get().strip()
            price = price_entry.get().strip()
            img_url = img_entry.get().strip()
            description = desc_text.get("1.0", "end").strip()
            if not (name and price and img_url and description):
                messagebox.showwarning("Поля не заполнены", "Заполните все поля для добавления блюда.")
                return
            desc_lines = [line.strip() for line in description.splitlines() if line.strip()]
            self.add_item(section, name, price, img_url, desc_lines)
            dialog.destroy()

        tk.Button(dialog, text="Добавить", command=add_action).grid(row=4, column=0, columnspan=2, pady=10)

    def add_item(self, section: str, name: str, price: str, img_url: str, description_lines: List[str]) -> None:
        """Insert a new product item into the specified section."""
        container = self.hits_catalog if section == "hits" else self.product_catalog
        # Build the new product item
        item_div = self.soup.new_tag("div", attrs={"class": "product-item"})
        # Image wrapper
        image_div = self.soup.new_tag("div", attrs={"class": "product-image"})
        img_tag = self.soup.new_tag("img", src=img_url, alt=name)
        image_div.append(img_tag)
        # Modal description
        modal_div = self.soup.new_tag("div", attrs={"class": "product-description-modal"})
        ul_tag = self.soup.new_tag("ul")
        for line in description_lines:
            li = self.soup.new_tag("li")
            li.string = line
            ul_tag.append(li)
        modal_div.append(ul_tag)
        image_div.append(modal_div)
        # Info button
        button_tag = self.soup.new_tag("button", attrs={"class": "info-btn"})
        button_tag.string = "Состав"
        image_div.append(button_tag)
        item_div.append(image_div)
        # Name and price
        name_p = self.soup.new_tag("p", attrs={"class": "product-name"})
        name_p.string = name
        price_p = self.soup.new_tag("p", attrs={"class": "product-price"})
        price_p.string = price
        item_div.append(name_p)
        item_div.append(price_p)
        # Insert into container
        container.append(item_div)
        # Save changes and refresh lists
        self.refresh_lists()

    def remove_selected(self, section: str) -> None:
        """Remove the currently selected item from the specified section."""
        if section == "hits":
            listbox = self.hits_listbox
            container = self.hits_catalog
        else:
            listbox = self.catalog_listbox
            container = self.product_catalog
        selection = listbox.curselection()
        if not selection:
            messagebox.showinfo("Не выбрано", "Сначала выберите пункт для удаления.")
            return
        index = selection[0]
        # Find all product-item divs directly under container
        items = container.find_all("div", class_="product-item", recursive=False)
        if index < 0 or index >= len(items):
            messagebox.showerror("Ошибка", "Выбранный индекс вне диапазона.")
            return
        # Confirm deletion
        name = listbox.get(index)
        if not messagebox.askyesno("Подтвердите удаление", f"Удалить '{name}' из секции?"):
            return
        # Remove the element
        items[index].extract()
        self.refresh_lists()

    def save_changes(self) -> None:
        """Write the updated soup back to the HTML file and upload via FTP if configured."""
        self.save_soup()
        messagebox.showinfo("Сохранено", "Изменения сохранены.")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    """Parse command‑line arguments for FTP configuration and local file path."""
    parser = argparse.ArgumentParser(description="BKbox Menu Editor with optional FTP support")
    parser.add_argument(
        "html_path",
        nargs="?",
        default="page81046126.html",
        help="Path to the HTML file to edit (local or used as working copy for FTP)",
    )
    return parser.parse_args(list(argv))


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = tk.Tk()
    # Instantiate editor with embedded FTP credentials if USE_FTP is True;
    # otherwise operate on a local file only.
    if USE_FTP:
        app = MenuEditor(
            root,
            html_path=args.html_path,
            ftp_host=FTP_HOST,
            ftp_user=FTP_USER,
            ftp_pass=FTP_PASS,
            remote_dir=REMOTE_DIR,
            remote_file=REMOTE_FILE,
        )
    else:
        app = MenuEditor(root, html_path=args.html_path)
    root.mainloop()


if __name__ == "__main__":
    main()
