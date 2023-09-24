import tkinter as tk
from tkinter import filedialog
import os
from dotenv import load_dotenv
import fnmatch
import sys, subprocess
from tkinter import ttk, messagebox, font, scrolledtext
import sqlite3
from AutoTestGen import TestGenerator, MODELS, ADAPTERS
class ChatApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        # Set theme
        style = ttk.Style()
        style.theme_use("clam")
        # Main Technical variables
        self.choices = ADAPTERS.keys()
        self.choice_var = tk.StringVar()
        self.repo_dir: str=None
        self.suffix: str=None
        self.TestGenerator = TestGenerator
        
        # Intro Frame
        self.intro_frame = ttk.Frame(root, width=500, height=500)
        # App Frame
        self.app_frame = tk.Frame(root, width=1028, height=500)
        self.load_intro()
    
    def load_intro(self) -> None:
        self._center_window(self.root, 500, 500)
        self._clear_widgets(self.app_frame)
        self.intro_frame.tkraise()
        self.intro_frame.pack_propagate(False)
        self.intro_frame.pack(fill="both", expand=True)
        # Language Selection
        choice_frame = ttk.LabelFrame(self.intro_frame, text="Select a Language")
        choice_frame.pack(padx=20, pady=10, fill="both", expand=True)
        
        # Choice RadioButtons
        for choice in self.choices:
            ttk.Radiobutton(
                choice_frame,
                text=choice,
                variable=self.choice_var,
                value=choice
            ).pack(anchor="w", padx=10, pady=5)
        
        # Open Repo Button
        ttk.Button(
            self.intro_frame,
            text="Open Repository",
            cursor="hand1",
            command=self._open_repository
        ).pack(pady=15)

    def load_app(self) -> None:
        # Load Chat App
        # Set system path to repo directory
        sys.path[0] = self.repo_dir
        self._center_window(self.root, 1028, 500)
        self._clear_widgets(self.intro_frame)
        self.app_frame.tkraise()
        self.app_frame.pack(fill="both", expand=True)
        self.app_frame.pack_propagate(False)
        # Refresh Button
        tk.Button(
            self.app_frame,
            text="\u2190",
            command=self.load_intro,
            width=2,
            height=1
        ).pack(side="left", pady=1, anchor="nw")
        # Back Button
        tk.Button(
            self.app_frame,
            text="\u21BB",
            command=self._refresh_app,
            width=2,
            height=1
        ).pack(side="right", pady=1, anchor="ne")
        # Menu Bar
        MenuBar(self.root, self.repo_dir)
        # Chat Frame
        chat_frame = ChatFrame(self.app_frame)
        # Utils Frame
        UtilsFrame(
            self.app_frame,
            chat_frame,
            self.repo_dir,
            self.suffix,
            self.choice_var.get()
        )

    def _open_repository(self) -> None:
        directory = filedialog.askdirectory()
        if directory:
            self.repo_dir = directory
            print(directory)
            self.suffix = ADAPTERS[self.choice_var.get()].suffix
            self.load_app()

    def _clear_widgets(self, frame: tk.Frame) -> None:
        # select all frame widgets and delete them
        for widget in frame.winfo_children():
            widget.destroy()
        frame.pack_forget()

    def _refresh_app(self) -> None:
            self._clear_widgets(self.app_frame)
            self.load_app()
        
    def _center_window(self, window: tk.Tk, width, height) -> None:
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2        
        window.geometry(f"{width}x{height}+{x}+{y}") 

    def _prepare_db(self):
        """Prepare database if it does not exist yet for storing app state"""
        db_name = "app_state.db"
        if not os.path.exists(db_name):
            conn = sqlite3.connect(db_name)
            cursor = self.conn.cursor()
            cursor.execute("CREATE TABLE users (username text, password text)")
            conn.commit()

    def run(self):
        self.root.mainloop()


class MenuBar:
    def __init__(self, parent: tk.Tk, repo_dir: str):
        self.parent = parent
        self.repo_dir = repo_dir
        self.menubar = tk.Menu(self.parent)
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.file_menu.add_command(label="Authenticate", command=self.build_auth_window)
        self.file_menu.add_separator()
        self.file_menu.add_cascade(label="Logout", command=self.logout)
        self.menubar.add_cascade(label="Authenticate", menu=self.file_menu)
        self.parent.config(menu=self.menubar)
        self.auth_window: tk.Toplevel = None
        self.api_key_entry: ttk.Entry = None
        self.org_entry: ttk.Entry = None

    def build_auth_window(self):
        if TestGenerator._api_key:
            message = (
                "You are already authenticated.\n"
                "For re-authentication please logout first.\n"
            )
            messagebox.showinfo(title="Status", message=message)
            return
        self.auth_window = tk.Toplevel(self.parent)
        self.auth_window.title("Authentication")
        self.auth_window.resizable(False, False)
        tk.Label(
            self.auth_window,
            text="API Key"
        ).grid(row=0, column=0, padx=5, pady=5)
        self.api_key_entry = ttk.Entry(self.auth_window, show="*")
        self.api_key_entry.grid(row=0, column=1, padx=5, pady=5)
        tk.Label(
            self.auth_window,
            text="Organization [Optional]"
        ).grid(row=1, column=0, padx=5, pady=5)
        self.org_entry = ttk.Entry(self.auth_window, show="*")
        self.org_entry.grid(row=1, column=1, padx=5, pady=5)
        # Load Env Button
        ttk.Button(
            self.auth_window,
            text="Load .env",
            command=self.env_auth
        ).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        # Gui Authentication
        ttk.Button(
            self.auth_window,
            text="Authenticate",
            command=lambda: self.gui_auth(self.org_entry.get(), self.api_key_entry.get())
        ).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        # env help
        tk.Button(
            self.auth_window,
            text="?",
            command=self.env_help,
            width=2,
            height=1
        ).grid(row=2, column=2, padx=5, sticky="e")


    def logout(self):
        TestGenerator._api_key = None
        TestGenerator._org_key = None
        messagebox.showinfo(title="Status", message="Logged-out successfully")
    
    def env_auth(self):
        env_file = os.path.join(self.repo_dir, ".env")
        if os.path.isfile(env_file):
            _ = load_dotenv(env_file)
            variable_names = list(os.environ.keys())
            if not "OPENAI_API_KEY" in variable_names:
                messagebox.showerror(title="Error", message="No 'OPENAI_API_KEY' variable found in .env file")
            else:
                api_key = os.getenv("OPENAI_API_KEY")
                org = os.getenv("OPENAI_ORG")
                TestGenerator.authenticate(api_key, org)
                self.auth_window.destroy()
                messagebox.showinfo(title="Status", message="Authentication completed using .env file")
        else:
            messagebox.showerror(title="Error", message="No .env file found in selected repository")


    def env_help(self):
        text = (
            "For .env authentication\n"
            "place .env file in your selected directory.\n"
            "It should contain at least the 'OPENAI_API_KEY' variable.\n\n"
            "If you aditionally want to specify organization key, add the 'OPENAI_ORG' variable.\n"
        )
        messagebox.showinfo(".env authentication", text)


    def gui_auth(self, org: str, api_key: str):
        if api_key == "":
            messagebox.showerror(title="Error", message="Please enter an API Key")
            return
        TestGenerator.authenticate(org, api_key)
        self.auth_window.destroy()
        messagebox.showinfo(title="Status", message="Authentication completed successfully")

class ChatFrame:
    def __init__(self, app_frame: ttk.Frame):
        self.app_frame = app_frame
        self.chat_frame = ttk.Frame(self.app_frame, width=800, height=500)
        self.chat_frame.pack(fill="both", side="left", padx=10, pady=5, expand=True)
        self.chat_frame.configure(borderwidth=4, relief="groove")
        # Add Chat History
        self.chat_history = tk.Text(self.chat_frame, state=tk.DISABLED, bg="#B6CEB7")
        self.chat_history.pack(fill="both", expand=True)
        self.chat_history.tag_configure("User", foreground="black")
        self.chat_history.tag_configure("API", foreground="blue")
        # Add Chat Entry
        self.chat_entry = ttk.Entry(self.chat_frame)
        self.chat_entry.pack(fill="both", side="left", expand=True)
        # Add Send Button
        ttk.Button(
            self.chat_frame,
            text="Send",
            command=lambda event=None: self.send_message(self.chat_entry.get(), tag="User")
        ).pack(fill="both", side="right")
        # Add Enter binding for send
        self.chat_entry.bind(
            "<Return>",
            func=lambda event=None: self.send_message(self.chat_entry.get(), tag="User")
        )
        # ComboBox for selecting model
        model_var = tk.StringVar()
        self.combo_box = ttk.Combobox(
            self.chat_frame,
            textvariable=model_var,
            values=MODELS,
            state="readonly",
            width=5
        )
        self.combo_box.pack(fill="both", side="right", expand=True)
        self.combo_box.bind("<<ComboboxSelected>>", func=lambda event=None: self.select_model())


    def select_model(self):
        TestGenerator.set_model(self.combo_box.get())

    def send_message(self, text: str=None, tag: str="user"):
        if TestGenerator._api_key is None:
            messagebox.showwarning("Warning", "Please authenticate first!")
            return
        if TestGenerator._model is None:
            messagebox.showwarning("Warning", "Please select a model first!")
            return
        if text:
            self.chat_history.config(state=tk.NORMAL)
            self.chat_history.insert(tk.END, f"{tag}:\n{text}\n")
            self.chat_history.config(state=tk.DISABLED)
            self.chat_entry.delete(0, tk.END)

class UtilsFrame:
    def __init__(self, app_frame: ttk.Frame, chat_frame: ChatFrame, repo_dir: str, suffix: str, language: str):
        self.app_frame = app_frame
        self.chat_frame = chat_frame
        self.repo_dir = repo_dir
        self.suffix = suffix
        self.language = language
        self.utils_frame = ttk.Frame(self.app_frame, width=228, height=500)
        self.utils_frame.pack(fill="both", side="right", padx=10, pady=5, expand=True)
        self.utils_frame.configure(borderwidth=2, relief="groove")

        # Repository File Tree
        self.file_tree = ttk.Treeview(self.utils_frame, show="tree", columns=["Value"])
        self.file_tree.column("#0", width=200)
        self.file_tree.pack(fill="both", side="top", expand=True)
        self.insert_directory(parent="", current_path=self.repo_dir)
        # Add Workstation
        self.workstation = WorkStation(self.utils_frame, self.chat_frame)
        
        # Add Right Click Menu
        menu = tk.Menu(self.utils_frame, tearoff=0)
        menu.add_command(label="Open", command=self.open_selected_item)
        self.file_tree.bind("<Button-2>", lambda event: menu.post(event.x_root, event.y_root))
        menu.add_command(label="Select for Testing", command=lambda event=None: self.select_for_testing())
    

    def insert_directory(self, parent: str, current_path: str):
        items = [
            fn 
            for fn in os.listdir(current_path)
            if (fn.endswith(self.suffix) or os.path.isdir(os.path.join(current_path, fn))) and not self._is_ignored(fn)
        ]
        for item in items:
            item_path = os.path.relpath(os.path.join(current_path, item), self.repo_dir)
            item_id = self.file_tree.insert(parent, "end", text=item, tags=(item_path,), values=(item_path, ))
            is_directory = os.path.isdir(item_path)
            if is_directory:
                self.insert_directory(item_id, item_path)

    def open_selected_item(self):
        selected_item = self.file_tree.focus()
        if selected_item:
            item_path = self.file_tree.item(selected_item)["tags"][0]
            if os.path.isfile(item_path):
                self._open_file(item_path)
        
    def select_for_testing(self):
        # Clean Workstation tree
        self.workstation.workst_tree.delete(*self.workstation.workst_tree.get_children())
        selected_item = self.file_tree.focus()
        file_path = self.file_tree.item(selected_item)["tags"][0]
        print(file_path)
        if not file_path.endswith(self.suffix):
            messagebox.showerror(
                title="Error",
                message=f"Please select a {self.suffix} file."
            )
            return
        # Configure TestGenerator for selected module
        TestGenerator.configure_adapter(self.language, module=file_path)
        func_names = TestGenerator._adapter.retrieve_func_defs()
        class_names = TestGenerator._adapter.retrieve_class_defs()
        if func_names + class_names == []:
            messagebox.showinfo("Info", "No Function- or Class Definiton found in the selected file.")
            return
        for func_name in func_names:
            _ = self.workstation.workst_tree.insert("", "end", text=func_name, values=("function", "0%"))
        for class_name in class_names:
            item_id = self.workstation.workst_tree.insert("", "end", text=class_name, values=("class", "0%"))
            methods = TestGenerator._adapter.retrieve_class_methods(class_name)
            for method in methods:
                self.workstation.workst_tree.insert(item_id, "end", text=method, values=("class method", "0%"))


    def _open_file(self, file_path):
        """Opens file in default editor: should cover most platforms"""
        try:
            if sys.platform.startswith('darwin'):
                subprocess.call(('open', file_path))
            elif sys.platform.startswith('win32'):
                subprocess.call(('start', file_path), shell=True)
            elif sys.platform.startswith('linux'):
                subprocess.call(('xdg-open', file_path))
            else:
                print("Unsupported platform:", sys.platform)
        except Exception as e:
            print("Error:", e)

    def _is_ignored(self, fn: str):
        """Takes .gitignore into account"""
        if fn.startswith(".") or fn == "setup.py": return True
        gitignore_path = os.path.join(self.repo_dir, ".gitignore")
        if os.path.isfile(gitignore_path):
            with open(gitignore_path, "r") as f:
                for line in f:
                    pattern = line.strip()
                    if pattern and not pattern.startswith("#"):
                        if pattern.endswith("/"):
                            pattern = pattern[:-1]
                        if fnmatch.fnmatch(fn, pattern):
                            return True
        return False

class WorkStation:
    def __init__(self, utils_frame: ttk.Frame, chat_frame: ChatFrame):
        self.utils_frame = utils_frame
        self.chat_frame = chat_frame
        self.workst_tree = ttk.Treeview(self.utils_frame, columns=("Type", "Cov"))
        self.workst_tree.heading("#0", text="Definition", anchor="w")
        self.workst_tree.heading("Type", text="Type", anchor="w")
        self.workst_tree.heading("Cov", text="Cov", anchor="w")
        self.workst_tree.column("Type", width=80)
        self.workst_tree.column("Cov", width=30)
        self.workst_tree.pack(fill="both", expand=True, pady=5)
        # Add Right Click Menu
        menu = tk.Menu(self.utils_frame, tearoff=0)
        menu.add_command(label="See Tests", command=self.show_tests)
        menu.add_command(label="Open Coverage", command=self.open_cov_report)
        self.workst_tree.bind("<Button-2>", lambda event: menu.post(event.x_root, event.y_root))
        
        # Workstation config Button
        self.config_window = ConfigWindow(self.utils_frame)
        config_button = tk.Button(
            self.utils_frame,
            text="\u2699",
            width=3,
            height=2
        )
        config_button.bind(
            "<Button-1>",
            lambda event: self.config_window.build_window(event.x_root, event.y_root)
        )
        config_button.pack(side="left", pady=3, anchor="sw")

        # Workstation Generate Tests Button
        ttk.Button(
            self.utils_frame,
            text="Generate Tests",
            command=self.generate_tests,
        ).pack(side="left", padx=5, pady=5, anchor="sw")
        
        # Workstation Log Console
        self.log_console = scrolledtext.ScrolledText(
            self.utils_frame,
            wrap=tk.WORD,
            state=tk.NORMAL,
            font=("Courier", 13),
            width=40,
            height=10
        )
        self.log_console.insert(tk.END, "Log console:\n")
        self.log_console.config(state=tk.DISABLED, font=("Courier", 10))
        self.log_console.pack(fill="both", expand=True)


    def log_message(self, message: str) -> None:
        """Logs message to log console"""
        self.log_console.config(state=tk.NORMAL)
        self.log_console.insert(tk.END, message + '\n')
        self.log_console.see(tk.END)
        self.log_console.config(state=tk.DISABLED)

    def show_tests(self):
        # TODO: ListBox of avaliable tests with open, coverage and save buttons
        pass
    
    def generate_tests(self):
        # TODO: Main Test Generation method, Define Pipeline first in TestGenerator
        obj_type = self.workst_tree.item(self.workst_tree.focus())["values"][0]
        if obj_type == "function":
            func_name = self.workst_tree.item(self.workst_tree.focus())["text"]
            initial_prompt = TestGenerator.get_prompt(func_name)
        elif obj_type == "class method":
            class_name = self.workst_tree.item(self.workst_tree.parent(self.workst_tree.focus()))["text"]
            method_name = self.workst_tree.item(self.workst_tree.focus())["text"]
            initial_prompt = TestGenerator.get_prompt(class_name, method_name)
        initial_message = "\n".join([message["content"] for message in initial_prompt])
        
        self.chat_frame.send_message(initial_message, tag="User")
        self.log_message("Sending Initial Prompt to TestGenerator...")
        self.log_message("Waiting for response...")

        results = TestGenerator.generate_tests_pipeline(
            initial_prompt,
            n_samples=int(self.config_window.n_samples),
            max_iter=int(self.config_window.max_iters)
        )
        response = results[0]["test"]
        self.log_message("Test Generation completed.")
        self.chat_frame.send_message(response, tag="API")

    def open_cov_report(self):
        # TODO: setup line coloring based on coverage report saved in DB
        source_code_window = tk.Toplevel()
        source_code_window.title("Coverage Report")
        source_code_window.geometry("800x600")
        text_widget = tk.Text(source_code_window, spacing3=6)
        text_widget.pack(fill="both", expand=True)
        # Chane font to monospace
        monospace_font = font.Font(family="Courier", size=12)
        text_widget.configure(font=monospace_font)
        obj_type = self.workst_tree.item(self.workst_tree.focus())["values"][0]
        obj_source = self._retrieve_source(obj_type)
        module_source = TestGenerator._adapter.retrieve_module_source()
        module_source_lstripped = '\n'.join([line.lstrip() for line in module_source.split('\n')])
        obj_source_lstripped = '\n'.join([line.lstrip() for line in obj_source.split('\n')])
        start = self._find_lines(module_source_lstripped, obj_source_lstripped)
        lines = obj_source.strip().split("\n")
        for i, line in enumerate(lines, start=start):
            line_numbered = "{:3d} ".format(i) + line
            text_widget.insert("end", line_numbered + "\n")
        text_widget.configure(state=tk.DISABLED)
        text_widget.tag_add("red", "1.0", "1.0 lineend")
        text_widget.tag_config("red", foreground="red")


    def _retrieve_source(self, obj_type: str):
        if obj_type == "function":
            func_name = self.workst_tree.item(self.workst_tree.focus())["text"]
            source_code = TestGenerator._adapter.retrieve_func_source(func_name)
        elif obj_type == "class":
            class_name = self.workst_tree.item(self.workst_tree.focus())["text"]
            source_code = TestGenerator._adapter.retrieve_class_source(class_name)
        elif obj_type == "class method":
            class_name = self.workst_tree.item(self.workst_tree.parent(self.workst_tree.focus()))["text"]
            method_name = self.workst_tree.item(self.workst_tree.focus())["text"]
            source_code = TestGenerator._adapter.retrieve_classmethod_source(class_name, method_name)
        else:
            messagebox.showinfo("Info", "No source code available.")
        return source_code

    def _find_lines(self, module_source: str, obj_source: str) -> int:
        """Finds the start line of the object in the module source code"""
        lines = module_source.split('\n')
        target_lines = obj_source.split('\n')
        for index, _ in enumerate(lines):
            if all(line in lines[index + i] for i, line in enumerate(target_lines)):
                start_line = index + 1
        return start_line
    
class ConfigWindow:
    def __init__(self, parent: tk.Tk):
        self.parent = parent
        self.n_samples: int = 1
        self.max_iters: int = 5
    
    def build_window(self, x_geom, y_geom):
        self.config_window = tk.Toplevel(self.parent)
        self.config_window.geometry(f"+{x_geom}+{y_geom}")
        self.config_window.resizable(False, False)
        self.config_window.title("Configuration")
        tk.Label(
            self.config_window,
            text="n_samples:"
        ).grid(row=0, column=0, padx=5, pady=5)
        self.ntests_entry = ttk.Entry(self.config_window)
        self.ntests_entry.grid(row=0, column=1, padx=5, pady=5)
        self.ntests_entry.insert(0, self.n_samples)
        tk.Label(
            self.config_window,
            text="max_iters:"
        ).grid(row=1, column=0, padx=5, pady=5)
        self.maxiter_entry = ttk.Entry(self.config_window)
        self.maxiter_entry.grid(row=1, column=1, padx=5, pady=5)
        self.maxiter_entry.insert(0, self.max_iters)

        ttk.Button(
            self.config_window,
            text="Ok",
            command=self.save_settings
        ).grid(row=2, column=0, padx=5, sticky="w")
        ttk.Button(
            self.config_window,
            text="Cancel",
            command=self.config_window.destroy
        ).grid(row=2, column=1, pady=5, padx=5, sticky="w")
    
    def save_settings(self):
        n_samples = self.ntests_entry.get()
        max_iters = self.maxiter_entry.get()

        if n_samples.isdigit() and max_iters.isdigit():
            self.n_samples = n_samples
            self.max_iters = max_iters
        else:
            messagebox.showerror(title="Error", message="Please enter integer values")
            return
        self.config_window.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Auto Test Generator")
    root.eval(f"tk::PlaceWindow . center")
    app = ChatApp(root)
    app.run()
