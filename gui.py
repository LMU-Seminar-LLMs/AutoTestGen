import tkinter as tk
from tkinter import filedialog
import os
from typing import Union
from dotenv import load_dotenv
import fnmatch
import sys, subprocess
from pathlib import Path
from tkinter import ttk, messagebox, font, scrolledtext
import sqlite3
from AutoTestGen import TestGenerator, MODELS, ADAPTERS

class ChatApp:
    def __init__(self, root: tk.Tk):
        # root
        self.root = root
        self.root.title("Auto Test Generator")
        self.root.eval(f"tk::PlaceWindow . center")
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        
        # Set ttk theme
        style = ttk.Style()
        style.theme_use("clam")

        # Main Technical variables
        self.repo_dir: str=None
        self.language: str=None
        self.conn: sqlite3.Connection=None
        
        # Intro Frame
        self.intro_frame = IntroFrame(self.root, width=500, height=500)
        # App Frame
        self.app_frame = AppFrame(self.root, width=1028, height=500)
        self.load_intro()
    
    def load_intro(self) -> None:
        self._center_window(self.root, 500, 500)
        self.intro_frame.tkraise()
        self.intro_frame.pack(fill="both", expand=True)
        self.intro_frame.pack_propagate(False)
        self.intro_frame.load_widgets()
        # Connection between IntroFrame and AppFrame
        ttk.Button(
            self.intro_frame,
            text="Open Repository",
            cursor="hand1",
            command=self.open_repo
        ).pack(pady=15)
    
    def load_app(self) -> None:
        sys.path[0] = self.repo_dir
        self._center_window(self.root, 1028, 500)
        self._clear_widgets(self.intro_frame)
        self.app_frame.configure_app(self.repo_dir, self.language, self.conn)
        self.app_frame.tkraise()
        self.app_frame.pack(fill="both", expand=True)
        self.app_frame.pack_propagate(False)
        # Go Back to Intro Frame Button
        tk.Button(
            self.app_frame,
            text="\u2190",
            command=self.reload_intro,
            width=2,
            height=1
        ).pack(side="left", pady=1, anchor="nw")
        self.app_frame.load_widgets()
        
    def reload_intro(self) -> None:
        self._clear_widgets(self.app_frame)
        self.load_intro()

    def open_repo(self) -> None:
        directory = filedialog.askdirectory()
        if directory:
            # Check size of repo
            tree = Path(directory).glob('**/*')
            if sum(f.stat().st_size for f in tree if f.is_file()) / 1e6 > 20:
                message = (
                    "Selected repository is larger than 20MB.",
                    "It might take time to mount it in the container.",
                    "Are you sure you chose the right directory?"
                )
                resp = messagebox.askyesno("Warning", message)
                if not resp: return
            self.repo_dir = directory
            self.language = self.intro_frame.choice_var.get()
            print("Repo dir:", self.repo_dir)
            # Connecting to container
            print("Starting container...")
            # Prepare database
            try:
                self.prepare_db()
            except:
                messagebox.showerror(
                    "Error",
                    "Error occured while preparing database"
                )
                raise
            TestGenerator.connect_to_container(
                self.repo_dir,
                image="autotestgen:latest",
                cont_name="autotestgen"
            )
            self.load_app()

    def prepare_db(self) -> None:
        """Prepare database if it does not exist yet for storing test and associating coverage data"""
        db_path = os.path.join(self.repo_dir, "autotestgen.db")
        if not os.path.isfile(db_path):
            self.conn = sqlite3.connect(db_path)
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE tests (
                    id INTEGER PRIMARY KEY,
                    module_name TEXT,
                    class_name TEXT,
                    obj_name TEXT,
                    message_history TEXT,
                    test_code TEXT,
                    coverage_report TEXT
                )
            ''')
            self.conn.commit()
            
    def _clear_widgets(self, frame: tk.Frame) -> None:
        """Clear all widgets of a frame"""
        for widget in frame.winfo_children():
            widget.destroy()
        frame.pack_forget()

    def _center_window(self, window: tk.Tk, width: int, height: int) -> None:
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2        
        window.geometry(f"{width}x{height}+{x}+{y}") 

    def run(self) -> None:
        self.root.mainloop()
    
    def quit(self) -> None:
        print("Closing app...")
        if TestGenerator._container:
            TestGenerator._container.reload()
            if TestGenerator._container.status == "running":
                try:
                    TestGenerator._container.stop()
                except:
                    messagebox.showerror(
                        "Error",
                        "Error occured while stopping container"
                    )
                    raise
        if self.conn:
            self.conn.close()
        self.root.destroy()


class IntroFrame(ttk.Frame):
    def __init__(self, root: tk.Tk, *args, **kwargs):
        super().__init__(root, *args, **kwargs)
        # For language selection
        self.choice_var = tk.StringVar()
        
    def load_widgets(self):
        self.choice_frame = ttk.LabelFrame(self, text="Select a Language")
        self.choice_frame.pack(padx=20, pady=10, fill="both", expand=True)
        for choice in ADAPTERS.keys():
            ttk.Radiobutton(
                self.choice_frame,
                text=choice,
                variable=self.choice_var,
                value=choice
            ).pack(anchor="w", padx=10, pady=5)


class AppFrame(ttk.Frame):
    def __init__(self, root: tk.Tk, *args, **kwargs):
        super().__init__(root, *args, **kwargs)
        
        self.repo_dir: Union[str, None]=None
        self.language: Union[str, None]=None
        self.suffix: Union[str, None]=None
        self.conn: Union[sqlite3.Connection, None]=None

        self.chat_frame: Union[ChatFrame, None]=None
        self.utils_frame: Union[UtilsFrame, None]=None
        
        
    def load_widgets(self) -> None:
        MenuBar(self.master, self.repo_dir)
        self.chat_frame = ChatFrame(self)
        self.chat_frame.pack(
            fill="both",
            side="left",
            padx=10,
            pady=5,
            expand=True
        )
        self.utils_frame = UtilsFrame(self)
        self.utils_frame.pack(
            fill="both",
            side="right",
            padx=10,
            pady=5,
            expand=True
        )
        
        
    def configure_app(
            self,
            repo_dir: str,
            language: str,
            conn: sqlite3.Connection
        ) -> None:
        self.repo_dir = repo_dir
        self.suffix = ADAPTERS[language].suffix
        self.language = language
        self.conn = conn
    
    def populate_db(
            self,
            mod_name: str,
            class_name: str,
            obj_name: str,
            history: str,
            code: str,
            coverage: str
        ) -> None:
        
        insert_query = """
            INSERT INTO tests
            (mod_name, class_name, obj_name, history, code, coverage)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        self.conn.execute(
            insert_query,
            (mod_name, class_name, obj_name, history, code, coverage)
        )
        self.conn.commit()


class MenuBar(tk.Menu):
    def __init__(self, master: tk.Tk, repo_dir: str, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.repo_dir = repo_dir
        self.file_menu = tk.Menu(self, tearoff=0)
        self.add_cascade(label="Authentication", menu=self.file_menu)
        self.file_menu.add_command(
            label="Authenticate",
            command=self.build_auth_window
        )
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Logout", command=self.logout)
        master.config(menu=self)

    def build_auth_window(self, event=None) -> None:
        if TestGenerator._api_key:
            message = (
                "You are already authenticated.",
                "For re-authentication please logout first."
            )
            messagebox.showinfo("Status", message)
            return
        AuthentificationWindow(self.repo_dir)
    
    def logout(self, event=None) -> None:
        TestGenerator._api_key = None
        TestGenerator._org_key = None
        messagebox.showinfo(title="Status", message="Logged-out successfully")

class AuthentificationWindow(tk.Toplevel):
    def __init__(self, repo_dir, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.repo_dir = repo_dir
        self.title("Authentication")
        self.resizable(False, False)
       
        # Add API Key Entry
        tk.Label(self, text="API Key").grid(row=0, column=0, padx=5, pady=5)
        self.api_entry = ttk.Entry(self, show="*")
        self.api_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # Add Organization Entry
        tk.Label(
            self,
            text="Organization [Optional]"
        ).grid(row=1, column=0, padx=5, pady=5)
        self.org_entry = ttk.Entry(self, show="*")
        self.org_entry.grid(row=1, column=1, padx=5, pady=5)

        # Login Buttons
        ttk.Button(
            self,
            text="Load .env",
            command=self.env_auth
        ).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Button(
            self,
            text="Authenticate",
            command= lambda event=None: self.gui_auth(
                self.api_entry.get(),
                self.org_entry.get()
            )
        ).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        tk.Button(
            self,
            text="?",
            command=self.env_help,
            width=2,
            height=1
        ).grid(row=2, column=2, padx=5, sticky="e")

    def gui_auth(self, api_key: str, org: str):
        if api_key == "":
            messagebox.showerror("Error", "Please enter an API Key")
            return
        TestGenerator.authenticate(api_key, org)
        self.destroy()
        messagebox.showinfo("Status", "Authentication completed successfully")

    def env_auth(self, event=None):
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
                self.destroy()
                messagebox.showinfo(title="Status", message="Authentication completed using .env file")

    def logout(self, event=None):
        TestGenerator._api_key = None
        TestGenerator._org_key = None
        messagebox.showinfo(title="Status", message="Logged-out successfully")

    def env_help(self, event=None):
        text = """For .env authentication
            place .env file in your selected directory.
            It should contain at least the 'OPENAI_API_KEY' variable.
            If you aditionally want to specify organization key, 
            add the 'OPENAI_ORG' variable.
        """
        messagebox.showinfo(".env authentication", text)
    
class ChatFrame(ttk.Frame):
    def __init__(self, master: AppFrame, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        # Model Variable
        self.model_var = tk.StringVar()
        self.configure(borderwidth=4, relief="groove")
        
        self.chat_history = ChatHistory(self, state=tk.DISABLED, bg="#B6CEB7")
        self.chat_history.pack(fill="both", expand=True)

        self.chat_entry = ttk.Entry(self)
        self.chat_entry.bind("<Return>", lambda event=None: self.send_message(self.chat_entry.get()), tag="User")
        self.chat_entry.pack(fill="both", side="left", expand=True)
        ttk.Button(self, text="\u232B", command=self.clear_chat, width=4).pack(fill="both", side="right")

        ttk.Button(
            self,
            text="Send", command=lambda event=None: self.send_message(self.chat_entry.get(), tag="User")
        ).pack(fill="both", side="right")

        
        self.model_box = ttk.Combobox(self, textvariable=self.model_var, values=MODELS, state="readonly", width=5)
        self.model_box.pack(fill="both", side="right", expand=True)
        self.model_box.bind("<<ComboboxSelected>>", lambda event=None: self.select_model())

    def send_message(self, message: str, tag: str):
        """Send message to API and display response in chat history"""
        if TestGenerator._api_key is None:
            messagebox.showwarning("Warning", "Please authenticate first!")
            return
        if TestGenerator._model is None:
            messagebox.showwarning("Warning", "Please select a model first!")
            return
        messages = self.collect_history()
        messages.append({"role": "user", "content": message})
        # TODO
        # response = TestGenerator.generate_tests_pipeline(messages)
        pass
    
    def display_message(self, message: str, tag: str="API"):
        """Displays message in chat history"""
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.insert(tk.END, f"{tag}:\n{message}\n", tag)
        self.chat_history.config(state=tk.DISABLED)
        self.chat_entry.delete(0, tk.END)

    def collect_history(self) -> list[dict]:
        user_rg = self.chat_history.tag_ranges("User")
        api_rg = self.chat_history.tag_ranges("API")
        if len(user_rg) != len(api_rg):
            messagebox.showerror("Error","Unexpected chat behavior occured.\nPlease clear chat and try again.")
            return
        messages = []
        if user_rg:
            for st_user, end_user, st_api, end_api in zip(user_rg[::2], user_rg[1::2], api_rg[::2], api_rg[1::2]):
                user_message = self.chat_history.get(st_user, end_user).split("\n")[1]
                api_message = self.chat_history.get(st_api, end_api).split("\n")[1]
                messages.append({"role": "user", "content": user_message})
                messages.append({"role": "assistant", "content": api_message})
        return messages
    
    def clear_chat(self, event=None):
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.delete("1.0", tk.END)
        self.chat_history.config(state=tk.DISABLED)
    
    def select_model(self):
        TestGenerator.set_model(self.model_var.get())


class UtilsFrame(ttk.Frame):
    def __init__(self, master: AppFrame, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.configure(borderwidth=2, relief="groove")
        self.app_frame = master
        
        # Pipeline parameters
        self.temp: float = 0.1
        self.max_iter: int = 5

        # Repo FileTree + Right-click menu
        self.file_tree = FileTree(self, self.app_frame.repo_dir, self.app_frame.suffix, show="tree", columns=["Value"])
        self.file_tree.pack(fill="both", side="top", expand=True)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Open", command=lambda event=None: self.open_selected_item())
        menu.add_command(label="Select for Testing", command=lambda event=None: self.select_for_testing())
        self.file_tree.bind("<Button-2>", lambda event: menu.post(event.x_root, event.y_root))
        
        # WorkstationTree + Right-click menu
        self.workst_tree = WorkStationTree(self, columns = ("Type", "Cov"))
        self.workst_tree.pack(fill="both", expand=True, pady=5)
        menu_wst = tk.Menu(self, tearoff=0)
        menu_wst.add_command(label="See Tests", command=self.show_tests)
        menu_wst.add_command(label="Open Coverage", command=self.open_cov_report)
        self.workst_tree.bind("<Button-2>", lambda event: menu_wst.post(event.x_root, event.y_root))

        # Workstation Tools
        config_button = tk.Button(self, text="\u2699", width=3, height=2)
        config_button.bind("<Button-1>", lambda event: ConfigWindow(self, event.x_root, event.y_root))
        config_button.pack(side="left", pady=3, anchor="sw")
        ttk.Button(self, text="Generate Tests", command=self.gen_tests).pack(side="left", padx=5, pady=5, anchor="sw")
        self.log_console = scrolledtext.ScrolledText(self, wrap=tk.WORD, font=("Courier", 13), width=40, heigh=10)
        self.log_console.insert(tk.END, "Log console:\n")
        self.log_console.config(state=tk.DISABLED, font=("Courier", 10))
        self.log_console.pack(fill="both", expand=True)

    def gen_tests(self, event=None):
        # TODO
        pass



    def log_message(self, message: str) -> None:
        """Logs message in log console"""
        self.log_console.config(state=tk.NORMAL)
        self.log_console.insert(tk.END, message + "\n")
        self.log_console.config(state=tk.DISABLED)
        self.log_console.see(tk.END)
    
    def open_selected_item(self):
        selected_item = self.file_tree.focus()
        if selected_item:
            item_path = self.file_tree.item(selected_item)["tags"][0]
            file = os.path.join(self.app_frame.repo_dir, item_path)
            if os.path.isfile(file):
                self.open_file(file)

    def open_file(self, file_path):
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
        except Exception:
            messagebox.showerror("Error", "Error occured while opening file")
            raise

    def select_for_testing(self):
        self.workst_tree.delete(*self.workst_tree.get_children())
        selected_item = self.file_tree.focus()
        file_path = self.file_tree.item(selected_item)["tags"][0]
        if not file_path.endswith(self.app_frame.suffix):
            messagebox.showerror("Error", f"Please select a {self.app_frame.suffix} file.")
            return
        print(f"Selected File: {file_path}")
        TestGenerator.configure_adapter(self.app_frame.language, module=file_path)
        container_check = TestGenerator._adapter.check_requirements_in_container(TestGenerator._container)
        if container_check:
            messagebox.showerror("Error", container_check)
            return
        func_names = TestGenerator._adapter.retrieve_func_defs()
        class_names = TestGenerator._adapter.retrieve_class_defs()
        if func_names + class_names == []:
            messagebox.showinfo("Info", "No Function- or Class Definiton found in the selected file.")
            return
        # TODO: Fix coverage percentage
        for func_name in func_names:
            _ = self.workst_tree.insert("", "end", text=func_name, values=("function", "0%"))
        for class_name in class_names:
            item_id = self.workst_tree.insert("", "end", text=class_name, values=("class", "0%"))
            methods = TestGenerator._adapter.retrieve_class_methods(class_name)
            for method in methods:
                self.workst_tree.insert(item_id, "end", text=method, values=("class method", "0%"))
        
    def show_tests(self):
        # TODO: Implement fetch tests from db
        pass

    def open_cov_report(self):
        source_code_window = tk.Toplevel()
        source_code_window.title("Coverage Report")
        source_code_window.geometry("800x600")
        text_frame = CustomText(source_code_window, spacing3=6)
        text_frame.configure(font=font.Font(family="Courier", size=12))
        text_frame.pack(fill="both", expand=True)

        #
        obj_type = self.workst_tree.item(self.workst_tree.focus())["values"][0]
        obj_source = self._retrieve_source(obj_type)
        obj_source_striped = "\n".join([line.strip() for line in obj_source.split("\n")])
        module_source: str = TestGenerator._adapter.retrieve_module_source()
        module_source_striped = "\n".join([line.strip() for line in module_source.split("\n")])

        start = self._find_lines(module_source_striped, obj_source_striped)
        lines = obj_source.strip().split("\n")
        # Numbering lines
        for i, line in enumerate(lines, start=start):
            line_numbered = "{:3d} ".format(i) + line
            text_frame.insert("end", line_numbered + "\n")
        text_frame.configure(state=tk.DISABLED)

        # TODO: Add coloring
        text_frame.tag_configure("missing", foreground="red")  
        text_frame.tag_add("missing", "1.0", "1.0 lineend")
        
    def _find_lines(self, module_source: str, obj_source: str) -> int:
        """Finds the start line of the object source_code in the module source code"""
        lines = module_source.split('\n')
        target_lines = obj_source.split('\n')
        for index, _ in enumerate(lines):
            if all(line in lines[index + i] for i, line in enumerate(target_lines)):
                start_line = index + 1
        return start_line
    
    def _retrieve_source(self, obj_type: str) -> str:
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


class WorkStationTree(ttk.Treeview):
    def __init__(self, master: UtilsFrame, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.heading("#0", text="Definition", anchor="w")
        self.heading("Type", text="Type", anchor="w")
        self.heading("Cov", text="Cov", anchor="w")
        self.column("Type", width=80)
        self.column("Cov", width=30)


class ConfigWindow(tk.Toplevel):
    def __init__(self, master: UtilsFrame, x_geom, y_geom, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.master: UtilsFrame
        self.geometry(f"+{x_geom}+{y_geom}")
        self.resizable(False, False)
        self.title("Configuration")
        
        tk.Label(self, text="temp:").grid(row=0, column=0, padx=5, pady=5)
        self.temp_entry = ttk.Entry(self)
        self.temp_entry.insert(0, master.temp)
        self.temp_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(self, text="max_iter:").grid(row=1, column=0, padx=5, pady=5)
        self.maxiter_entry = ttk.Entry(self)
        self.maxiter_entry.insert(0, master.max_iter)
        self.maxiter_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(self, text="Ok", command=self.save_settings).grid(row=2, column=0, padx=5, sticky="w")
        ttk.Button(self, text="Cancel", command=self.destroy).grid(row=2, column=1, pady=5, padx=5, sticky="w")

    def save_settings(self):
        temp = self.temp_entry.get()
        max_iter = self.maxiter_entry.get()

        if max_iter.isdigit():
            self.master.temp = float(temp)
            self.master.max_iter = int(max_iter)
        else:
            messagebox.showerror("Error", "Please enter integer value for max_iter")
            return
        self.destroy()


class CustomText(tk.Text):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind("<Button-1>", self.delayed_disable)
    
    def delayed_disable(self, event=None):
        self.config(state=tk.NORMAL)
        self.after(10, self.disable)
        
    def disable(self):
        self.config(state=tk.DISABLED)


class ChatHistory(CustomText):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tag_configure("User", foreground="black")
        self.tag_configure("API", foreground="blue")


class FileTree(ttk.Treeview):
    def __init__(self, master: UtilsFrame, repo_dir: str, suffix: str, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.repo_dir = repo_dir
        self.suffix = suffix
        self.column("#0", width=200)
        self.insert_directory(parent="", current_path=self.repo_dir)


    def insert_directory(self, parent: str, current_path: str):
        items = [
            fn 
            for fn in os.listdir(current_path)
            if (fn.endswith(self.suffix) or os.path.isdir(os.path.join(current_path, fn))) and not self.is_ignored(fn)
        ]
        for item in items:
            item_path = os.path.relpath(os.path.join(current_path, item), self.repo_dir)
            item_id = self.insert(parent, "end", text=item, tags=(item_path,), values=(item_path, ))
            if os.path.isdir(item_path): 
                self.insert_directory(item_id, item_path)
        
    def is_ignored(self, fn: str):
        """
            looks for .gitignore to ignore files in FileTree.
            Additionaly excludes: setup.py, files starting with "." and __pycache__.
        """
        if fn.startswith(".") or fn == "setup.py" or fn == "__pycache__": return True
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

    def open_file(self, file_path):
        try:
            if sys.platform.startswith('darwin'):
                subprocess.call(('open', file_path))
            elif sys.platform.startswith('win32'):
                subprocess.call(('start', file_path), shell=True)
            elif sys.platform.startswith('linux'):
                subprocess.call(('xdg-open', file_path))
            else:
                print("Unsupported platform: ", sys.platform)
        except Exception:
            messagebox.showerror("Error", "Error occured while opening file")
            raise


if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    app.run()
