import tkinter as tk
from tkinter import filedialog
import os
from dotenv import load_dotenv
import fnmatch
import sys, subprocess
from tkinter import ttk, messagebox
from AutoTestGen import TestGenerator, adapter_registry
from AutoTestGen.language_adapters import BaseAdapter
from typing import Type

class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto Test Generator")
        self.root.eval(f"tk::PlaceWindow {str(self.root)} center")
        style = ttk.Style()
        style.theme_use("clam")
        self.choice_var = tk.IntVar()
        # adapter_registry[self.choice_var.get()]
        self.repo_dir: str=None
        self.TestGenerator = TestGenerator
        self.adapter: Type[BaseAdapter]=None
        # Intro Frame
        self.intro_frame = ttk.Frame(root, width=500, height=500)
        # App Frame
        self.app_frame = tk.Frame(root, width=1028, height=500)
        self.load_intro()
        
    def open_repository(self):
        directory = filedialog.askdirectory()
        if directory:
            self.repo_dir = directory
            self.load_app()

    def load_intro(self):
        self._clear_widgets(self.app_frame)
        self.intro_frame.tkraise()
        self.intro_frame.pack_propagate(False)
        self.intro_frame.pack(fill="both", expand=True)
        self.load_intro_widgets()

    def load_intro_widgets(self):
        # Choose Language
        choices = adapter_registry.keys()
        choice_frame = ttk.LabelFrame(self.intro_frame, text="Select a Language")
        choice_frame.pack(padx=20, pady=10, fill="both", expand=True)
        for i, choice in enumerate(choices):
            ttk.Radiobutton(choice_frame, text=choice, variable=self.choice_var, value=i).pack(anchor="w", padx=10, pady=5)

        # create Open Repo Button
        ttk.Button(
            self.intro_frame,
            text="Open Repository",
            cursor="hand1",
            command=self.open_repository,
        ).pack(pady=15)
    
    def _logout(self):
        self.TestGenerator._api_key = None
        self.TestGenerator._org_key = None
        messagebox.showinfo(title="Status", message="Logged-out successfully")

    def _authenticate(self):
        if self.TestGenerator._api_key is None:
            env_file = os.path.join(self.repo_dir, ".env")
            if os.path.isfile(env_file):
                # Env file authentication
                _ = load_dotenv()
                org = os.getenv("OPENAI_ORG")
                api_key = os.getenv("OPENAI_API_KEY")
                self.TestGenerator.authenticate(org, api_key)
                messagebox.showinfo(title="Status", message="Authentication was done using .env file")
            else:
                # Authentication using GUI
                def _gui_auth(org, api_key):
                    self.TestGenerator.authenticate(org, api_key)
                    messagebox.showinfo(title="Status", message="Authentication completed successfully")
                    auth_window.destroy()
                auth_window = tk.Toplevel(self.root)
                auth_window.title("Authentication")
                api_key = tk.Label(auth_window, text="API Key")
                api_key.pack()
                api_key_entry = tk.Entry(auth_window, show="*")
                api_key_entry.pack()
                org = tk.Label(auth_window, text="Organization [Optional]")
                org.pack()
                org_entry = tk.Entry(auth_window, show="*")
                org_entry.pack()
                tk.Button(
                    auth_window,
                    text="Authenticate",
                    command=lambda: _gui_auth(org_entry.get(), api_key_entry.get())
                ).pack()
        else:
            messagebox.showinfo(title="Status", message="Application is already authenticated")

    def load_app(self):
        # Load Chat App
        # Set system path to repo directory
        sys.path.append(self.repo_dir)
        self._clear_widgets(self.intro_frame)
        self.intro_frame.pack_forget()
        self.app_frame.tkraise()
        self.app_frame.pack(fill="both", expand=True)
        self.app_frame.pack_propagate(False)
        # Add menu bar
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Authenticate", command=self._authenticate)
        file_menu.add_separator()
        file_menu.add_cascade(label="Logout", command=self._logout)
        menubar.add_cascade(label="Authenticate", menu=file_menu)
        self.root.config(menu=menubar)

        # Chat Frame
        chat_frame = ttk.Frame(self.app_frame, width=800, height=500)
        chat_frame.pack(fill="both", side="left", padx=10, pady=5, expand=True)
        chat_frame.configure(borderwidth=4, relief="groove")
        # Utils Frame
        utils_frame = ttk.Frame(self.app_frame, width=228, height=500)
        utils_frame.pack(fill="both", side="right", padx=10, pady=5, expand=True)
        utils_frame.configure(borderwidth=2, relief="groove")
        
        self.load_chat_widgets(chat_frame)
        self.load_utils_widgets(utils_frame)

    def load_chat_widgets(self, chat_frame):
        def send_prompt(event=None):
            user_prompt = chat_entry.get()
            if user_prompt:
                chat_history.config(state=tk.NORMAL)
                chat_history.insert(tk.END, "You: " + user_prompt + "\n")
                # Send Prompt Recieve response
                response = "Test Response"
                chat_history.insert(tk.END, "TestGenerator: " + response + "\n")
                chat_history.config(state=tk.DISABLED)
                chat_entry.delete(0, tk.END)

        chat_history = tk.Text(chat_frame, state=tk.DISABLED, bg="#B6CEB7")
        chat_history.pack(fill="both", expand=True)
        chat_entry = ttk.Entry(chat_frame)
        chat_entry.pack(fill="both", side="left", expand=True)
        
        ttk.Button(
            chat_frame,
            text="Send",
            command=send_prompt
        ).pack(fill="both", side="right")
    
        chat_entry.bind("<Return>", send_prompt)

    def load_utils_widgets(self, utils_frame):
        def _insert_directory(parent, current_path):
            items = [fn for fn in os.listdir(current_path)
                     # ToDo: Fix this later for other langauges as well
                     if (fn.endswith(".py") or os.path.isdir(os.path.join(current_path, fn))) and not self._is_ignored(fn)]
            for item in items:
                item_path = os.path.join(current_path, item)
                item_id = tree.insert(parent, "end", text=item, tags=(item_path,))
                is_directory = os.path.isdir(item_path)
                if is_directory:
                    _insert_directory(item_id, item_path)

        def _open_selected_item(event=None):
            selected_item = tree.focus()
            if selected_item:
                item_path = tree.item(selected_item)["tags"][0]
                if os.path.isfile(item_path):
                    self.open_file(item_path)
                else:
                    tree.item(selected_item, open=True)
        
        def _select_for_testing(event=None):
            selected_item = tree.focus()
            # ToDo: Fix this later for other langauges as well
            if not selected_item.endswith("py"):
                messagebox.showerror(
                    title="Error",
                    message=f"Please select a {self.choice_var.get()} file."
                )
                return
            self.adapter = adapter_registry[self.choice_var.get()]()
            workst_tree.insert("", "end", text=selected_item, values=(self.choice_var.get(), "0%"))

        # Tree
        tree = ttk.Treeview(utils_frame, columns=("File Name"), show="tree")
        # tree.heading("File Name", text="File Name")
        # tree.column("Size", width=80)
        tree.pack(fill="both", side="top", expand=True)
        # tree.delete(*tree.get_children())
        _insert_directory(parent="", current_path=self.repo_dir)
        
        # Workstation_tree
        workst_tree = ttk.Treeview(utils_frame, columns=("Type", "Cov"), show="tree")
        workst_tree.heading("#0", text="Definition")
        workst_tree.heading("Type", text="Type")
        workst_tree.heading("Cov", text="Cov")
        workst_tree.pack(fill="both", side="bottom", expand=True, pady=5)

        # Add Right Click Menu
        menu = tk.Menu(utils_frame, tearoff=0)
        menu.add_command(label="Open", command=_open_selected_item)
        menu.add_command(label="Select for Testing", command=_select_for_testing)
        tree.bind("<Button-2>", lambda event: menu.post(event.x_root, event.y_root))





    def _is_ignored(self, filename):
        if filename.startswith("."): return True
        gitignore_path = os.path.join(self.repo_dir, ".gitignore")
        if os.path.isfile(gitignore_path):
            with open(gitignore_path, "r") as f:
                for line in f:
                    pattern = line.strip()
                    if pattern and not pattern.startswith("#"):
                        if pattern.endswith("/"):
                            pattern = pattern[:-1]
                        if fnmatch.fnmatch(filename, pattern):
                            return True
        else:
            if filename.startswith(".") or filename == "__pycache__":
                return True
        return False

    def _clear_widgets(self, frame):
        # select all frame widgets and delete them
        for widget in frame.winfo_children():
            widget.destroy()
    

    def open_file(self, file_path):
        try:
            if sys.platform.startswith('darwin'):
                subprocess.call(('open', file_path))
        except Exception as e:
            print("Error:", e)



    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    app.run()
