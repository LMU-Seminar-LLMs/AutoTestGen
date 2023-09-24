import tkinter as tk
from tkinter import filedialog
import os
from typing import Union
from dotenv import load_dotenv
import fnmatch
import sys, subprocess
from pathlib import Path
from tkinter import ttk, messagebox, font, scrolledtext
import sqlite3, json
from AutoTestGen import TestGenerator, MODELS, ADAPTERS, SUFFIXES

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
                    "Selected repository is larger than 20MB.\n"
                    "It might take time to mount it in the container.\n"
                    "Are you sure you chose the right directory?"
                )
                resp = messagebox.askyesno("Warning", message)
                if not resp: return
            self.repo_dir = directory
            self.language = self.intro_frame.choice_var.get()
            print("Repo dir:", self.repo_dir)
            print("Starting container...")
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
        """Prepare database if not avaliable yet in the repo directory"""
        db_path = os.path.join(self.repo_dir, "autotestgen.db")
        if not os.path.isfile(db_path):
            self.conn = sqlite3.connect(db_path)
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE tests (
                    id INTEGER PRIMARY KEY,
                    module TEXT,
                    class TEXT,
                    obj TEXT,
                    history TEXT,
                    test TEXT,
                    coverage_report TEXT
                )
            ''')
            self.conn.commit()
            cursor.close()
        else:
            self.conn = sqlite3.connect(db_path)
            print("Database already exists")
            
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
        # Refresh Button
        tk.Button(
            self,
            text="\u21BB",
            command=self.refresh,
            width=2,
            height=1
        ).pack(side="left", pady=1, anchor="nw")

        self.utils_frame = UtilsFrame(self)
        self.utils_frame.pack(
            fill="both",
            side="right",
            padx=10,
            pady=5,
            expand=True
        )
    
    def refresh(self) -> None:
        self.utils_frame.workst_tree.refresh()

    def configure_app(
            self,
            repo_dir: str,
            language: str,
            conn: sqlite3.Connection
        ) -> None:
        self.repo_dir = repo_dir
        self.suffix = SUFFIXES[language]
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
            (module, class, obj, history, test, coverage_report)
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

    def gui_auth(self, api_key: str, org: str) -> None:
        if api_key == "":
            messagebox.showerror("Error", "Please enter an API Key")
            return
        TestGenerator.authenticate(api_key, org)
        self.destroy()
        messagebox.showinfo("Status", "Authentication completed successfully")

    def env_auth(self, event=None) -> None:
        env_file = os.path.join(self.repo_dir, ".env")
        if os.path.isfile(env_file):
            _ = load_dotenv(env_file)
            variable_names = list(os.environ.keys())
            if not "OPENAI_API_KEY" in variable_names:
                messagebox.showerror("Error", "No 'OPENAI_API_KEY' in .env")
            else:
                api_key = os.getenv("OPENAI_API_KEY")
                org = os.getenv("OPENAI_ORG")
                TestGenerator.authenticate(api_key, org)
                self.destroy()
                messagebox.showinfo(
                    "Status",
                    "Authentication completed using .env file"
                )

    def logout(self, event=None) -> None:
        TestGenerator._api_key = None
        TestGenerator._org_key = None
        messagebox.showinfo(title="Status", message="Logged-out successfully")

    def env_help(self, event=None) -> None:
        text = (
            "For .env authentication\n"
            "place .env file in your selected directory.\n"
            "It should contain at least the 'OPENAI_API_KEY' variable.\n"
            "If you aditionally want to specify organization key,\n"
            "add the 'OPENAI_ORG' variable."
        )
        messagebox.showinfo(".env authentication", text)
    

class ChatFrame(ttk.Frame):
    def __init__(self, master: AppFrame, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        # Model Variable
        self.master: AppFrame
        self.model_var = tk.StringVar()
        self.configure(borderwidth=4, relief="groove")
        
        self.chat_history = CustomText(self, state=tk.DISABLED, bg="#B6CEB7")
        self.chat_history.tag_configure("User", foreground="black")
        self.chat_history.tag_configure("API", foreground="blue")
        self.chat_history.tag_configure("System", foreground="green")
        self.chat_history.pack(fill="both", expand=True)

        self.chat_entry = ttk.Entry(self)
        self.chat_entry.bind(
            "<Return>",
            func=lambda event=None: self.send_message(
                [{"role": "user", "content": self.chat_entry.get()}],
                tag="User"
            )
        )
        self.chat_entry.pack(fill="both", side="left", expand=True)
        # Clear Chat Button
        ttk.Button(
            self,
            text="\u232B",
            command=self.clear_chat,
            width=4
        ).pack(fill="both", side="right")
        # Send Message Button
        ttk.Button(
            self,
            text="Send",
            command=lambda event=None: self.send_message(
                [{"role": "user", "content": self.chat_entry.get()}],
                tag="User"
            )
        ).pack(fill="both", side="right")

        self.model_box = ttk.Combobox(
            self,
            textvariable=self.model_var,
            values=MODELS,
            state="readonly", 
            width=5
        )
        self.model_box.pack(fill="both", side="right", expand=True)
        self.model_box.bind(
            "<<ComboboxSelected>>",
            lambda event=None: self.select_model()
        )

    def send_message(self, message: list[dict], tag: str) -> None:
        """
            Send message to API and display response in chat history
            Message should be a list of dicts with keys: "role" and "content"
        """
        if TestGenerator._api_key is None:
            messagebox.showwarning("Warning", "Please authenticate first!")
            return
        if TestGenerator._model is None:
            messagebox.showwarning("Warning", "Please select a model first!")
            return
        messages = self.collect_history()
        if len(message) > 1:
            self.display_message(message[0]["content"], "System")
            self.display_message(message[1]["content"], tag)
        else:
            if self.master.chat_frame.chat_history.get("1.0", "end-1c") == "":
                messagebox.showwarning(
                    "Warning",
                    "Please start the chat with Generate Tests button first!"
                )
            self.display_message(message[1]["content"], tag)

        messages.extend(message)
        item = self.master.utils_frame.workst_tree.focus()
        obj_name = self.master.utils_frame.workst_tree.item(item)["text"]
        obj_type = self.master.utils_frame.workst_tree.item(item)["values"][0]
        if obj_type == "class method":
            import_name = self.master.utils_frame.workst_tree.item(
                self.master.utils_frame.workst_tree.parent(item)
            )["text"]
        else:
            import_name = obj_name
            
        result = TestGenerator.generate_tests_pipeline(
            messages,
            obj_name=import_name,
            temp=self.master.utils_frame.temp,
            n_samples=self.master.utils_frame.n_samples,
            max_iter=self.master.utils_frame.max_iter
        )

        if result["report"]["compile_error"]:
            messagebox.showinfo(
                "Info",
                message= (
                    "Pipeline resulted test still contains compiling error\n"
                    "You can continue communicating with API to fix it or\n"
                    "alternatively you can try to manually fix it."
                )
            )
            messagebox.showerror(
                "Compile Error",
                result["report"]["compile_error"]
            )

        elif result["report"]["errors"]:
            messagebox.showinfo(
                "Info",
                message=(
                    "Generated tests contain errors\n"
                    "You can continue communicating with API to fix it or\n"
                    "alternatively you can try to manually fix it."
                )
            )
            messagebox.showerror(
                "Test Error",
                result["report"]["errors"]
            )
        
        else:
            # Add test to database
            if obj_type.startswith("class"):
                class_name = self.master.utils_frame.workst_tree.item(
                    self.master.utils_frame.workst_tree.parent(item)
                )["text"]
            else:
                class_name = None

            self.master.populate_db(
                mod_name=TestGenerator._adapter.mod_name,
                class_name=class_name,
                obj_name=obj_name,
                history=json.dumps(result["messages"]),
                code=result["test"],
                coverage=json.dumps(result["report"])
            )

            start, end, _ = self.master.utils_frame._find_lines(
                obj_name,
                obj_type,
                class_name
            )
            ex_lns = [
                i
                for i in result["report"]["executed_lines"] 
                if i >= start and i <= end
            ]
            miss_lns = [
                i
                for i in result["report"]["missing_lines"]
                if i >= start and i <= end
            ]
            if ex_lns == 0:
                cov = 0
            else:
                cov = len(ex_lns) / (len(ex_lns) + len(miss_lns))
            cov_report = {
                "n_tests": result["report"]["tests_ran_n"],
                "failed": len(result["report"]["failures"]),
                "coverage": int(cov) * 100
            }
            messagebox.showinfo(
                "Tests Generated",
                message=(
                    "Tests generated successfully and added to the database\n"
                    "You can see them by right-clicking on the corresponding "
                    "object in the Table on the right.\n" + str(cov_report)
                )
            )
        self.display_message(result["test"], "API")
        
    
    def display_message(self, message: str, tag: str):
        """Displays message in chat history"""
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.insert(tk.END, f"{tag}:\n{message}\n", tag)
        self.chat_history.config(state=tk.DISABLED)
        self.chat_entry.delete(0, tk.END)

    def collect_history(self) -> list[dict]:
        user_rg = self.chat_history.tag_ranges("User")
        api_rg = self.chat_history.tag_ranges("API")
        sys_rg = self.chat_history.tag_ranges("System")
        messages = []
        if len(user_rg) != len(api_rg):
            err_msg = (
                "Unexpected chat behavior occured.\n"
                "Please clear chat and try again."
            )
            messagebox.showerror("Error", err_msg)
            return
        if sys_rg:
            sys_msg = self.chat_history.get(
                sys_rg[0],
                sys_rg[1]
            ).split("\n")[1]
            messages.append({"role": "system", "content": sys_msg})

        if user_rg:
            for st_user, end_user, st_api, end_api in (
                zip(user_rg[::2], user_rg[1::2], api_rg[::2], api_rg[1::2])
            ):
                user_message = self.chat_history.get(
                    st_user,
                    end_user
                ).split("\n")[1]
                api_message = self.chat_history.get(
                    st_api,
                    end_api
                ).split("\n")[1]
                messages.extend(
                    [
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": api_message}
                    ]
                )
        return messages
    
    def clear_chat(self, event=None) -> None:
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.delete("1.0", tk.END)
        self.chat_history.config(state=tk.DISABLED)
    
    def select_model(self):
        TestGenerator.set_model(self.model_var.get())

class CustomText(tk.Text):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind("<Button-1>", self.delayed_disable)
    
    def delayed_disable(self, event=None) -> None:
        self.config(state=tk.NORMAL)
        self.after(10, self.disable)
        
    def disable(self) -> None:
        self.config(state=tk.DISABLED)


class UtilsFrame(ttk.Frame):
    def __init__(self, master: AppFrame, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.configure(borderwidth=2, relief="groove")
        self.master: AppFrame
        # Pipeline default parameters
        self.temp: float = 0.1
        self.n_samples: int = 1
        self.max_iter: int = 5
        self.current_mod: Union[str, None] = None

        # Repo FileTree + right-click menu
        self.file_tree = FileTree(
            self, self.master.repo_dir,
            self.master.suffix,
            show="tree",
            columns=["Value"]
        )
        self.file_tree.pack(fill="both", side="top", expand=True)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Open",
            command=lambda event=None: self.open_selected_item()
        )
        menu.add_command(
            label="Select for Testing",
            command=lambda event=None: self.select_for_testing()
        )
        self.file_tree.bind(
            "<Button-2>",
            lambda event: menu.post(event.x_root, event.y_root)
        )
        
        # WorkstationTree + Right-click menu
        self.workst_tree = WorkStationTree(self)
        self.workst_tree.pack(fill="both", expand=True, pady=5)
        menu_wst = tk.Menu(self, tearoff=0)
        menu_wst.add_command(
            label="See Tests",
            command=self.show_tests
        )
        menu_wst.add_command(
            label="Open Coverage",
            command=self.open_cov_report
        )
        self.workst_tree.bind(
            "<Button-2>",
            lambda event: menu_wst.post(event.x_root, event.y_root)
        )

        # Workstation Tools
        config_button = tk.Button(self, text="\u2699", width=3, height=2)
        config_button.pack(side="left", pady=3, anchor="sw")
        config_button.bind(
            "<Button-1>",
            lambda event: ConfigWindow(self, event.x_root, event.y_root)
        )
        # Generate Tests Button
        ttk.Button(
            self,
            text="Generate Tests",
            command=self.gen_tests
        ).pack(side="left", padx=5, pady=5, anchor="sw")
        # Log Console
        self.log_console = scrolledtext.ScrolledText(
            self,
            wrap=tk.WORD,
            font=("Courier", 13),
            width=40,
            heigh=10
        )
        self.log_console.insert(tk.END, "Log console:\n")
        self.log_console.config(state=tk.DISABLED, font=("Courier", 10))
        self.log_console.pack(fill="both", expand=True)

    def fetch_data(self, obj: str, cls: bool) -> list:
        """Fetches data from database for tests and coverage"""
        if cls:
            query = """
                SELECT DISTINCT class, MAX(id) AS id, coverage_report
                FROM tests WHERE class=? GROUP BY class
            """
        else:
            query = "SELECT * FROM tests WHERE obj=? ORDER BY id DESC"

        data = self.master.conn.execute(
            query,
            (obj, )
        ).fetchall()
        return data
    
    def get_func_cov(self, func_name: str) -> tuple[set, set]:
        """Returns sets of executed and missing lines for a function"""
        
        resp = self.fetch_data(func_name, cls=False)
        if resp:
            # Ckck if method
            print(f"DB entry: {resp[0][2]}")
            if resp[0][2]:
                st, end, _ = self._find_lines(
                    func_name,
                    "class method",
                    resp[0][2]
                )
            else:
                st, end, _ = self._find_lines(func_name, "function")
            data = json.loads(resp[0][-1])
            exe_lns = [ln for ln in data["executed_lines"] if st <= ln <= end]
            miss_lns = [ln for ln in data["missing_lines"] if st <= ln <= end]
            return set(exe_lns), set(miss_lns)
        else:
            return set(), set()
    
    def get_class_cov(self, class_name: str) -> tuple[set, set]:
        """Returns set of executed and missing lines for a class"""
        resp = self.fetch_data(class_name, cls=True)
        if resp:
            st, end, _ = self._find_lines(class_name, "class")
            data = [json.loads(it[-1]) for it in resp]
            exec_lines = [method["executed_lines"] for method in data]
            miss_lines = [method["missing_lines"] for method in data]
            exec_lines_flat = {
                it
                for subl in exec_lines
                for it in subl
                if st <= it <= end
            }
            miss_lines_flat = {
                it
                for subl in miss_lines
                for it in subl
                if st <= it <= end
            }
            return exec_lines_flat, miss_lines_flat
        else:
            return set(), set()
        
    def gen_tests(self, event=None) -> None:
        item = self.workst_tree.focus()
        obj_type = self.workst_tree.item(item)["values"][0]
        if obj_type == "function":
            obj = self.workst_tree.item(item)["text"]
            method_name = None
        elif obj_type == "class method":
            obj = self.workst_tree.item(self.workst_tree.parent(item))["text"]
            method_name = self.workst_tree.item(item)["text"]
        
        initial_prompt = TestGenerator.get_prompt(obj, method_name)
        self.master.chat_frame.send_message(initial_prompt, tag="User")

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
            file = os.path.join(self.master.repo_dir, item_path)
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

    def select_for_testing(self) -> None:
        self.workst_tree.delete(*self.workst_tree.get_children())
        selected_item = self.file_tree.focus()
        if not selected_item:
            selected_item = self.current_mod
        file_path: str = self.file_tree.item(selected_item)["tags"][0]
        if not file_path.endswith(self.master.suffix):
            messagebox.showerror(
                "Error",
                f"Please select a {self.master.suffix} file."
            )
            return
        print(f"Selected File: {file_path}")

        _ = TestGenerator.configure_adapter(
            self.master.language,
            module=file_path
        )

        container_check = TestGenerator._adapter.check_reqs_in_container(
            TestGenerator._container
        )
        if container_check:
            messagebox.showerror("Error", container_check)
            return
        
        func_names = TestGenerator._adapter.retrieve_func_defs()
        class_names = TestGenerator._adapter.retrieve_class_defs()
        if func_names + class_names == []:
            messagebox.showinfo(
                "Info",
                "No Function- or Class Definiton found in the selected file."
            )
            return
        
        for func_name in func_names:
            ex, miss = self.get_func_cov(func_name)
            if len(ex) == 0:
                cov = "0%"
            else:
                cov = f"{int((len(ex)/(len(ex)+len(miss)))*100)}%"
    
            self.workst_tree.insert(
                parent="",
                index="end",
                text=func_name,
                values=("function", cov)
            )

        for cls in class_names:
            ex_c, miss_c = self.get_class_cov(cls)
            if len(ex_c) == 0:
                cls_cov = "0%"
            else:
                cls_cov= f"{int((len(ex_c)/(len(ex_c)+len(miss_c)))*100)}%"
                
            item_id = self.workst_tree.insert(
                parent="",
                index="end",
                text=cls,
                values=("class", cls_cov)
            )
            methods = TestGenerator._adapter.retrieve_class_methods(cls)
            for method in methods:
                ex_m, miss_m = self.get_func_cov(method)
                if len(ex_m) == 0:
                    cov = "0%"
                else:
                    cov = f"{int((len(ex_m)/(len(ex_m)+len(miss_m)))*100)}%"
                self.workst_tree.insert(
                    item_id,
                    "end",
                    text=method,
                    values=("class method", cov)
                )
            self.current_mod = selected_item
        

    def open_cov_report(self):
        cov_report = CovWindow()
        item = self.workst_tree.focus()
        obj = self.workst_tree.item(item)["text"]
        obj_typ = self.workst_tree.item(item)["values"][0]
        if obj_typ == "class method":
            cls = self.workst_tree.item(self.workst_tree.parent(item))["text"]
        else:
            cls = None
        start, _, lines = self._find_lines(obj, obj_typ, cls)

        # Numbering and coloring lines
        if obj_typ == "class":
            lns_ex, _ = self.get_class_cov(obj)
        else:
            lns_ex, _ = self.get_func_cov(obj)

        for i, line in enumerate(lines, start=start):
            ln_n = "{:3d} ".format(i) + line
            if i in lns_ex:
                cov_report.text_frame.insert("end", ln_n + "\n", "executed")
            else:
                cov_report.text_frame.insert("end", ln_n + "\n")
        cov_report.text_frame.configure(state=tk.DISABLED)

        
    def _find_lines(
            self, obj: str,
            obj_type: str,
            cls: Union[str, None]=None
        ) -> tuple[int, int, list[str]]:
        """Finds start  and end lines of obj definition in module source"""

        module_source: str = TestGenerator._adapter.retrieve_module_source()
        obj_source = self._retrieve_source(obj, obj_type, cls)

        obj_src_strp = "\n".join(
            [line.strip() for line in obj_source.split("\n")]
        )
        mod_src_strp = "\n".join(
            [line.strip() for line in module_source.split("\n")]
        )
        target_lines = obj_src_strp.split('\n')
        lines = mod_src_strp.split('\n')
        for index, _ in enumerate(lines):
            if all(line
                   in lines[index + i] 
                   for i, line in enumerate(target_lines)
                ):
                start_line = index + 1
        end_line = start_line + len(target_lines) - 1
        return start_line, end_line, obj_source.split("\n")
    
    def _retrieve_source(
            self,
            obj: str,
            obj_type: str,
            cls: Union[str, None]=None
        ) -> str:
        if obj_type == "function":
            source_code = TestGenerator._adapter.retrieve_func_source(obj)
        elif obj_type == "class":
            source_code = TestGenerator._adapter.retrieve_class_source(obj)
        elif obj_type == "class method":
            source_code = TestGenerator._adapter.retrieve_classmethod_source(
                class_name=cls,
                method_name=obj
            )
        else:
            messagebox.showinfo("Info", "No source code available.")
        return source_code

    def show_tests(self):
        item = self.workst_tree.focus()
        obj = self.workst_tree.item(item)["text"]
        obj_typ = self.workst_tree.item(item)["values"][0]
        TestsWindow(self, obj, obj_typ)
        

class TestsWindow(tk.Toplevel):
    def __init__(
            self,
            master: UtilsFrame,
            obj_name: str,
            obj_type: str,
            *args,
            **kwargs
        ):
        super().__init__(master, *args, **kwargs)
        self.master: UtilsFrame
        self.title("Tests")
        self.geometry("800x600")
        self.tree  = ttk.Treeview(
            self,
            columns=("Name", "Total", "Failed", "Coverage")
        )
        self.obj_name = obj_name
        self.obj_type = obj_type

        self.tree.heading("#0", text="Number", anchor="w")
        self.tree.heading("Name", text="Name", anchor="w")
        self.tree.heading("Total", text="Total", anchor="w")
        self.tree.heading("Failed", text="Failed", anchor="w")
        self.tree.heading("Coverage", text="Coverage", anchor="w")
        self.tree.column("Name", width=100)
        self.tree.column("#0", width=10)
        self.tree.pack(fill="both", expand=True)
        _ = self.populate_tree(obj_name, obj_type)

        self.tree.bind("<Double-Button-1>", self.open_test)
        
    def populate_tree(self, obj: str, obj_type: str) -> None:
        if obj_type == "class":
            data = self.master.master.conn.execute(
                "SELECT obj, test, coverage_report FROM tests WHERE class=?",
                (obj, )
            ).fetchall()
        else:
            data = self.master.master.conn.execute(
                "SELECT obj, test, coverage_report FROM tests WHERE obj=?",
                (obj, )
            ).fetchall()
        
        for i, (obj, test, cov_report) in enumerate(data, start=1):
            lns_ex, lns_miss = self.master.get_func_cov(obj)
            if len(lns_ex) == 0:
                cov = "0%"
            else:
                cov = f"{int((len(lns_ex)/(len(lns_ex)+len(lns_miss)))*100)}%"
            cov_report = json.loads(cov_report)
            self.tree.insert(
                parent="",
                index="end",
                text=i,
                values=(
                    obj,
                    cov_report["tests_ran_n"],
                    len(cov_report["failures"]),
                    cov
                ),
                tags=(test, )
            )

    def open_test(self, event=None) -> None:
        test = self.tree.item(self.tree.focus())["tags"][0]
        test_window = CustomText(self, spacing3=6)
        test_window.configure(font=font.Font(family="Courier", size=12))
        test_window.config(state=tk.NORMAL)
        test_window.insert(tk.END, test)
        test_window.config(state=tk.DISABLED)
        test_window.pack(fill="both", expand=True)


class WorkStationTree(ttk.Treeview):
    def __init__(self, master: UtilsFrame, *args, **kwargs):
        self.master: UtilsFrame
        super().__init__(master, columns=("Type", "Cov"), *args, **kwargs)
        self.heading("#0", text="Definition", anchor="w")
        self.heading("Type", text="Type", anchor="w")
        self.heading("Cov", text="Cov", anchor="w")
        self.column("Type", width=80)
        self.column("Cov", width=30)
    
    def refresh(self) -> None:
        self.master.select_for_testing()

class CovWindow(tk.Toplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Coverage Report")
        self.geometry("800x600")
        self.text_frame = CustomText(self, spacing3=6)
        self.text_frame.configure(font=font.Font(family="Courier", size=12))
        self.text_frame.tag_configure("executed", foreground="green")
        self.text_frame.pack(fill="both", expand=True)
        
class ConfigWindow(tk.Toplevel):
    def __init__(self, master: UtilsFrame, x_geom, y_geom, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.master: UtilsFrame
        self.geometry(f"+{x_geom}+{y_geom}")
        self.resizable(False, False)
        self.title("Configuration")
        
        tk.Label(self, text="temp").grid(row=0, column=0, padx=5, pady=5)
        self.temp_entry = ttk.Entry(self)
        self.temp_entry.insert(0, master.temp)
        self.temp_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(self, text="n_samples").grid(row=1, column=0, padx=5, pady=5)
        self.n_samples_entry = ttk.Entry(self)
        self.n_samples_entry.insert(0, master.n_samples)
        self.n_samples_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(self, text="max_iter").grid(row=2, column=0, padx=5, pady=5)
        self.maxiter_entry = ttk.Entry(self)
        self.maxiter_entry.insert(0, master.max_iter)
        self.maxiter_entry.grid(row=2, column=1, padx=5, pady=5)

        ttk.Button(
            self,
            text="Ok",
            command=self.save_settings
        ).grid(row=3, column=0, padx=5, sticky="w")
        ttk.Button(
            self,
            text="Cancel",
            command=self.destroy
        ).grid(row=3, column=1, pady=5, padx=5, sticky="w")

    def save_settings(self):
        temp = self.temp_entry.get()
        max_iter = self.maxiter_entry.get()
        n_samples = self.n_samples_entry.get()

        if max_iter.isdigit() and n_samples.isdigit():
            self.master.temp = float(temp)
            self.master.max_iter = int(max_iter)
            self.master.n_samples = int(n_samples)
        else:
            messagebox.showerror(
                "Error",
                "Please enter integer value for max_iter"
            )
            return
        self.destroy()


class FileTree(ttk.Treeview):
    def __init__(
            self,
            master: UtilsFrame,
            repo_dir: str,
            suffix: str,
            *args,
            **kwargs
        ):
        super().__init__(master, *args, **kwargs)
        self.repo_dir = repo_dir
        self.suffix = suffix
        self.column("#0", width=200)
        self.insert_directory(parent="", current_path=self.repo_dir)

    def refresh(self):
        self.delete(*self.get_children())
        self.insert_directory(parent="", current_path=self.repo_dir)

    def insert_directory(self, parent: str, current_path: str) -> None:
        items = [
            fn 
            for fn in os.listdir(current_path)
            if (
                fn.endswith(self.suffix)
                    or os.path.isdir(os.path.join(current_path, fn))
                )
                and not self.is_ignored(fn)
        ]
        for item in items:
            item_path = os.path.relpath(
                path=os.path.join(current_path, item),
                start=self.repo_dir
            )
            item_id = self.insert(
                parent,
                "end",
                text=item,
                tags=(item_path, ),
                values=(item_path, )
            )
            if os.path.isdir(item_path): 
                self.insert_directory(item_id, item_path)
        
    def is_ignored(self, fn: str):
        """
            looks for .gitignore to ignore files in FileTree.
            Also excludes: setup.py, files starting with "." and __pycache__.
        """
        if fn.startswith(".") or fn == "setup.py" or fn == "__pycache__":
            return True
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
