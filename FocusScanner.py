import os
import cv2
import rawpy
import threading
import concurrent.futures
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import shutil
import multiprocessing

def get_focus_score(image_path):
    ext = os.path.splitext(image_path)[1].lower()
    standard_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}

    try:
        if ext in standard_formats:
            gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if gray is None or gray.size == 0:
                raise ValueError("OpenCV failed to read image")
        else:
            with rawpy.imread(image_path) as raw:
                rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8)
                gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return laplacian.var()

    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return 0.0

def find_all_images(folder_path):
    for root, _, files in os.walk(folder_path):
        for file in files:
            yield os.path.join(root, file)

class FocusDetectorApp:
    def __init__(self, master):
        self.master = master
        self.master.title("FocusScanner")
        self.image_refs = {}
        self.stop_requested = threading.Event()
        self.cpu_percent = tk.IntVar(value=100)
        self.selected_folder = None
        self.executor = None

        self.left_frame = ttk.Frame(master, padding=10)
        self.left_frame.grid(row=0, column=0, sticky="ns")
        self.right_frame = ttk.Frame(master, padding=10)
        self.right_frame.grid(row=0, column=1, sticky="nsew")

        self.threshold_label = ttk.Label(self.left_frame, text="Focus Threshold:")
        self.threshold_label.pack(anchor="w")
        self.threshold_var = tk.StringVar(value="200")
        self.threshold_entry = ttk.Entry(self.left_frame, textvariable=self.threshold_var, width=10)
        self.threshold_entry.pack(anchor="w", pady=(0, 10))

        ttk.Label(self.left_frame, text="CPU Usage:").pack(anchor="w", pady=(5, 0))
        for val in [25, 50, 75, 100]:
            ttk.Radiobutton(
                self.left_frame,
                text=f"{val}%",
                variable=self.cpu_percent,
                value=val
            ).pack(anchor="w")

        self.start_button = ttk.Button(self.left_frame, text="Start Scan", command=self.start_scan)
        self.start_button.pack(fill='x', pady=2)
        self.stop_button = ttk.Button(self.left_frame, text="Stop Scan", command=self.stop_scan)
        self.stop_button.pack(fill='x', pady=2)

        self.select_button = ttk.Button(self.left_frame, text="Select Folder", command=self.select_folder)
        self.select_button.pack(fill='x', pady=(10, 2))

        self.status_label = ttk.Label(self.left_frame, text="No folder selected", anchor="w")
        self.status_label.pack(fill='x', pady=5)

        self.progress = ttk.Progressbar(self.left_frame, mode='determinate')
        self.progress.pack(fill='x', pady=(0, 10))

        self.list_frame = ttk.Frame(self.left_frame)
        self.list_frame.pack(fill='both', expand=True)

        self.listbox = tk.Listbox(self.list_frame, height=30, width=60, selectmode=tk.EXTENDED)
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_image_select)

        self.scrollbar = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.listbox.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=self.scrollbar.set)

        self.copy_button = ttk.Button(self.left_frame, text="Copy Selected", command=self.copy_selected_images)
        self.copy_button.pack(fill='x', pady=5)

        self.thumbnail_label = ttk.Label(self.right_frame)
        self.thumbnail_label.pack()
        self.open_button = ttk.Button(self.right_frame, text="Open Image", command=self.open_selected_image)
        self.open_button.pack(pady=10)

        self.in_focus_images = []
        self.selected_image_path = None
        self.master.columnconfigure(1, weight=1)
        self.master.rowconfigure(0, weight=1)

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.selected_folder = folder
            self.status_label.config(text=f"Selected: {os.path.basename(folder)}")
        else:
            self.status_label.config(text="No folder selected")

    def start_scan(self):
        if not self.selected_folder:
            messagebox.showerror("Error", "Please select a folder first.")
            return

        try:
            threshold = float(self.threshold_var.get())
        except ValueError:
            messagebox.showerror("Invalid Threshold", "Please enter a valid number.")
            return

        self.stop_requested.clear()
        self.listbox.delete(0, tk.END)
        self.thumbnail_label.config(image="")
        self.progress["value"] = 0
        self.master.update_idletasks()

        all_images = list(find_all_images(self.selected_folder))
        total_images = len(all_images)
        if total_images == 0:
            self.status_label.config(text="No images found.")
            return

        max_workers = max(1, int(multiprocessing.cpu_count() * self.cpu_percent.get() / 125))
        self.status_label.config(text="Scanning...")

        def task():
            results = []
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
            futures = {self.executor.submit(get_focus_score, img): img for img in all_images}

            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                if self.stop_requested.is_set():
                    break
                score = future.result()
                if score >= threshold:
                    results.append((futures[future], score))
                self.master.after(0, self.update_progress, i + 1, total_images)
            if self.executor:
                self.executor.shutdown(wait=False, cancel_futures=True)
                self.executor = None
            if not self.stop_requested.is_set():
                self.master.after(0, self.display_results, results)
            else:
                self.master.after(0, lambda: self.status_label.config(text="Scan stopped."))

        threading.Thread(target=task, daemon=True).start()

    def stop_scan(self):
        self.stop_requested.set()
        self.status_label.config(text="Stopping scan...")
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.executor = None

    def update_progress(self, done, total):
        percent = int((done / total) * 100)
        self.progress["value"] = percent
        self.master.update_idletasks()

    def display_results(self, results):
        results.sort(key=lambda x: x[1], reverse=True)
        self.in_focus_images = results
        self.status_label.config(text=f"Found {len(results)} in-focus images.")
        self.path_by_index = {i: path for i, (path, _) in enumerate(results)}
        for i, (path, score) in enumerate(results):
            self.listbox.insert(tk.END, f"{score:.1f} - {os.path.basename(path)}")

    def on_image_select(self, event):
        if not self.listbox.curselection():
            return
        index = self.listbox.curselection()[0]
        self.selected_image_path = self.path_by_index.get(index)
        if self.selected_image_path:
            self.show_thumbnail(self.selected_image_path)

    def show_thumbnail(self, path):
        try:
            img = None
            try:
                with rawpy.imread(path) as raw:
                    rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8)
                    img = Image.fromarray(rgb)
            except rawpy.LibRawFileUnsupportedError:
                img = Image.open(path)
            except Exception as e:
                print(f"rawpy error for {path}: {e}")
                try:
                    img = Image.open(path)
                except Exception as e2:
                    print(f"PIL fallback also failed for {path}: {e2}")
                    return  

            if img:
                img.thumbnail((400, 400))
                img_tk = ImageTk.PhotoImage(img)
                self.image_refs[path] = img_tk
                self.thumbnail_label.config(image=img_tk)

        except Exception as e:
            print(f"Could not load thumbnail for {path}: {e}")


    def open_selected_image(self):
        if not self.selected_image_path:
            messagebox.showinfo("No Image", "Please select an image first.")
            return
        try:
            os.startfile(self.selected_image_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open image:\n{e}")

    def copy_selected_images(self):
        indices = self.listbox.curselection()
        if not indices:
            messagebox.showinfo("No Selection", "Please select one or more images to copy.")
            return

        dest_folder = filedialog.askdirectory(title="Select Destination Folder")
        if not dest_folder:
            return

        try:
            for index in indices:
                src_path = self.path_by_index.get(index)
                if src_path and os.path.exists(src_path):
                    dest_path = os.path.join(dest_folder, os.path.basename(src_path))
                    shutil.copy2(src_path, dest_path)
            messagebox.showinfo("Success", f"Copied {len(indices)} images to:\n{dest_folder}")
        except Exception as e:
            messagebox.showerror("Copy Failed", f"An error occurred:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = FocusDetectorApp(root)
    root.mainloop()
