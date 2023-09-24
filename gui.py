import tkinter as tk
from tkinter import ttk, messagebox, font, filedialog
import os, sys, subprocess, fnmatch
from typing import Union
from dotenv import load_dotenv
from pathlib import Path
import sqlite3, json
from AutoTestGen import ContainerManager, config, utils, generate_tests
from AutoTestGen import MODELS, ADAPTERS, SUFFIXES

class ChatApp:
    """
    Main class for starting the app.

    Attributes:
        root: root of the app (tk.Tk).
        intro_frame: intro frame (IntroFrame).
        app_frame: app frame (AppFrame).
        repo_dir: path to the selected repository (str).
        language: selected language (str).
        conn: connection to the database (sqlite3.Connection).
        cont_manager: instance of ContainerManager. For handling
            container related tasks.
    """

    def __init__(self, root: tk.Tk) -> None:
        # root
        self.root = root
        self.root.title("Auto Test Generator")
        self.root.eval(f"tk::PlaceWindow . center")
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        
        # Set ttk theme
        style = ttk.Style()
        style.theme_use("clam")

        # Main Technical variables
        self.repo_dir: str
        self.language: str
        self.conn: Union[sqlite3.Connection, None] = None 
        self.cont_manager: Union[ContainerManager, None] = None

        # Intro Frame
        self.intro_frame = IntroFrame(self.root, width=500, height=500)
        # App Frame
        self.app_frame = AppFrame(self.root, width=1028, height=500)
        self.load_intro()
    
    def load_intro(self) -> None:
        """Loads intro frame and its widgets."""
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
        """
        Loads app frame. Used when opening repository from intro frame.
        """
        sys.path[0] = self.repo_dir
        self._center_window(self.root, 1028, 500)
        self._clear_widgets(self.intro_frame)
        self.app_frame.configure_app(
            self.repo_dir,
            self.language,
            self.conn,
            self.cont_manager
        )
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
        """Reloads intro frame. Used when going back to intro frame"""
        self._clear_widgets(self.app_frame)
        self.load_intro()

    def open_repo(self) -> None:
        """
        Important function: starts the container, prepares the database
            and sets important atts like repo_dir, language, conn.
        """
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
            if self.language == "" or self.language is None:
                messagebox.showerror(
                    "Error",
                    "Please select a language"
                )
                return
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
            # Initialize ContainerManager
            if self.intro_frame.image_entry.get() == "":
                messagebox.showerror(
                    "Error",
                    "Please fill in the Docker image Name:Tag field"
                )
            try:
                self.cont_manager = ContainerManager(
                    image_name=self.intro_frame.image_entry.get(),
                    repo_dir=self.repo_dir
            )
            except:
                messagebox.showerror(
                    "Error",
                    (
                        "Error occured while initializing ContainerManager. "
                        "Please check the logs for more information"
                    )
                )
                raise
            self.load_app()

    def prepare_db(self) -> None:
        """
        Prepare database if not avaliable yet in the repo directory,
            otherwise connect to existing one.
        """
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
        """
        Helper function to clear all deceased widgets given a frame.

        Args:
            frame: frame to clear (tk.Frame).
        """
        for widget in frame.winfo_children():
            widget.destroy()
        frame.pack_forget()

    def _center_window(self, window: tk.Tk, width: int, height: int) -> None:
        """
        Helper function to center window on the screen.

        Args:
            window: root of the app (tk.Tk).
            width: width of the window.
            height: height of the window.
        """
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2        
        window.geometry(f"{width}x{height}+{x}+{y}") 

    def run(self) -> None:
        """Start the app."""
        self.root.mainloop()
    
    def quit(self) -> None:
        """
        Quit the app.

        Important: 
            stops the container and closes the db connection.
        
        """
        print("Closing app...")
        if self.cont_manager:
            print("Stopping container...")
            self.cont_manager.close_container()
        if self.conn:
            print("Closing database connection...")
            self.conn.close()
        self.root.destroy()


class IntroFrame(ttk.Frame):
    """Intro Frame and its widgets."""
    def __init__(self, root: tk.Tk, *args, **kwargs) -> None:
        super().__init__(root, *args, **kwargs)
        # For language and Image selection
        self.choice_var = tk.StringVar()
        self.image_entry: ttk.Entry
    
    def load_widgets(self) -> None:
        """Loads widgets for intro frame"""
        choice_frame = ttk.LabelFrame(self, text="Select a Language")
        choice_frame.pack(padx=20, pady=10, fill="both", expand=True)
        for choice in ADAPTERS.keys():
            ttk.Radiobutton(
                choice_frame,
                text=choice,
                variable=self.choice_var,
                value=choice
            ).pack(anchor="w", padx=10, pady=5)

        # Image Entry
        label = ttk.Label(self, text="Docker image Name:Tag")
        label.pack(padx=20, pady=10, anchor="center")
        self.image_entry = ttk.Entry(self)
        self.image_entry.pack(padx=20, anchor="center")


class AppFrame(ttk.Frame):
    """
    App frame class. Contains all the widgets for the app itself.

    Attributes:
        chat_frame: chat frame (ChatFrame) for chat history and entry.
        utils_frame: utils frame (UtilsFrame) for file trees and tools.
    """
    def __init__(self, root: tk.Tk, *args, **kwargs) -> None:
        super().__init__(root, *args, **kwargs)
        
        self.repo_dir: str
        self.language: str
        self.suffix: str
        self.conn: sqlite3.Connection
        self.cont_manager: ContainerManager

        self.chat_frame: ChatFrame
        self.utils_frame: UtilsFrame
        
    def load_widgets(self) -> None:
        """Loads widgets for app frame"""
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
        """Refreshes workstation to update tests and coverage data"""
        self.utils_frame.workst_tree.refresh()

    def configure_app(
            self,
            repo_dir: str,
            language: str,
            conn: sqlite3.Connection,
            cont_manager: ContainerManager
        ) -> None:
        """
        Configures app frame with important attributes.
        
        Args:
            repo_dir: path to the selected repository (str).
            language: selected language (str).
            conn: connection to the database (sqlite3.Connection).
        """
        self.repo_dir = repo_dir
        self.suffix = SUFFIXES[language]
        self.language = language
        self.conn = conn
        self.cont_manager = cont_manager
    
    def populate_db(
            self,
            mod_name: str,
            class_name: str,
            obj_name: str,
            history: str,
            code: str,
            coverage: str
        ) -> None:
        """
        Populates database with generated tests and coverage report.

        Args:
            mod_name: name of the module (str).
            class_name: name of the class (str).
            obj_name: name of the object (str).
            history: chat history (str).
            code: code of generated test (str).
            coverage: coverage report in json string format.
        """
        
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
    """
    Top menu bar for the app.
    
    Tabs:
        Authentication: [Authenticate, Logout]
    
    """
    def __init__(
            self,
            master: tk.Tk,
            repo_dir: str,
            *args,
            **kwargs
        ) -> None:
        super().__init__(master, *args, **kwargs)
        self.repo_dir = repo_dir
        self.file_menu = tk.Menu(self, tearoff=0)
        self.add_cascade(label="Authentication", menu=self.file_menu)
        self.file_menu.add_command(
            label="Authenticate",
            command=self.build_auth_window
        )
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label="Logout",
            command=self.logout
        )
        master.config(menu=self)

    def build_auth_window(self, event=None) -> None:
        """
        Builds authentication window. Checks if already authenticated.
        
        Note:
            Initializes instance of class AuthentificationWindow.
        """
        if config.API_KEY:
            messagebox.showinfo(
                "Status",
                (
                    "You are already authenticated.\n"
                    "For re-authentication please logout first."
                )
            )
            return
        AuthentificationWindow(self.repo_dir)
    
    def logout(self, event=None) -> None:
        """Logs out from OpenAI API"""
        config.API_KEY = None
        config.ORG_KEY = None
        messagebox.showinfo("Status", "Logged-out successfully")

class AuthentificationWindow(tk.Toplevel):
    """
    Authentication window for OpenAI API
    
    Methods:
        gui_auth: authenticates using GUI entries.
        env_auth: authenticates using .env file.
        env_help: shows help message for .env authentication.
    """
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
            text=".env authentication",
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
        """Authenticates using GUI entries"""
        if api_key == "":
            messagebox.showerror("Error", "Please enter an API Key")
            return
        utils.set_api_keys(api_key, org)
        self.destroy()
        messagebox.showinfo("Status", "Authentication completed successfully")

    def env_auth(self, event=None) -> None:
        """Authentication using .env file if avaliabe"""
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.isfile(env_file):
            _ = load_dotenv(env_file)
            variable_names = list(os.environ.keys())
            if not "OPENAI_API_KEY" in variable_names:
                messagebox.showerror("Error", "No 'OPENAI_API_KEY' in .env")
            else:
                api_key = os.getenv("OPENAI_API_KEY")
                org = os.getenv("OPENAI_ORG")
                utils.set_api_keys(api_key, org)
                self.destroy()
                messagebox.showinfo(
                    "Status",
                    "Authentication completed using .env file"
                )
        else:
            messagebox.showerror(
                "Error",
                f"No .env file found in {self.repo_dir}"
            )

    def env_help(self, event=None) -> None:
        """Shows help message for .env authentication"""
        text = (
            "For .env authentication\n"
            "place .env file in the same directory as gui.py.\n"
            "It should contain at least the 'OPENAI_API_KEY' variable.\n"
            "If you aditionally want to specify organization key,\n"
            "add the 'OPENAI_ORG' variable."
        )
        messagebox.showinfo(".env authentication", text)
    
class ChatFrame(ttk.Frame):
    """
    Chat part of the app. Contains chat history and entry.
    
    Attributes:
        self.model_var: model variable to select model for API.
        self.chat_history: chat box.
        self.chat_entry: chat entry.
    """
    def __init__(self, master: AppFrame, *args, **kwargs) -> None:
        super().__init__(master, *args, **kwargs)
        # Model Variable
        self.master: AppFrame
        self.model_var = tk.StringVar()
        self.chat_state: list[dict[str, str]] = []
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
            Send message to API and display response in chat history.

            Args:
                message: list of dicts with keys: "role" and "content".
                tag: tag name for formatting messages in chat history.

            Important:
                It enforces the user to start the chat with Generate
                Tests button, which sends initial prompt engineered
                message, after which the user has possibility to
                communicate with the API directly through chat entry.
                Through the chat existence (before cleaning it),
                all the previous messages are send together
                with the new prompt.
            
            Raises:
                Exception: if there is a problem running the pipeline.
        """
        if config.API_KEY is None:
            messagebox.showwarning("Warning", "Please authenticate first!")
            return
        if config.MODEL is None:
            messagebox.showwarning("Warning", "Please select a model first!")
            return
        
        if len(message) > 1:
            if self.chat_state == []:
                self.chat_state.extend(message[:2])
                self.display_message(message[0]["content"], "System")
                self.display_message(message[1]["content"], tag)
            else:
                self.chat_state.append(message[1])
                self.display_message(message[1]["content"], tag)  
        else:
            if self.chat_state == []:
                messagebox.showwarning(
                    "Warning",
                    "Please start the chat with Generate Tests button first!"
                )
                return
            else:
                self.chat_state.append(message[0])
                self.display_message(message[0]["content"], tag)

        item = self.master.utils_frame.workst_tree.focus()
        obj_name = self.master.utils_frame.workst_tree.item(item)["text"]
        obj_type = self.master.utils_frame.workst_tree.item(item)["values"][0]
        print("Object name: ", obj_name)
        print("Object type: ", obj_type)
        print("Chat state: ", self.chat_state)
        if obj_type == "class method":
            class_name = self.master.utils_frame.workst_tree.item(
                self.master.utils_frame.workst_tree.parent(item)
            )["text"]
            import_name = class_name
        elif obj_type == "function":
            class_name = None
            import_name = obj_name
        else:
            messagebox.showerror(
                "Error",
                "Please select a class method or function for testing"
            )
            return
        
        try:
            result = generate_tests(
                self.chat_state,
                self.master.cont_manager,
                obj_name=import_name,
                temp=self.master.utils_frame.temp,
                n_samples=self.master.utils_frame.n_samples,
                max_iter=self.master.utils_frame.max_iter
            )
            self.chat_state.append(
                {"role": "assistant", "content": result["test"]}
            )
            self.display_message(result["test"], "API")
        except:
            messagebox.showerror(
                "Error",
                (
                    "Exception occured while running the pipeline. It "
                    "might be an API related error or an error in the "
                    "pipiline code itself. Please check the logs.\n"
                )
            )
            raise

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
            self.master.populate_db(
                mod_name=os.path.basename(config.ADAPTER.module),
                class_name=class_name,
                obj_name=obj_name,
                history=json.dumps(result["messages"]),
                code=result["test"],
                coverage=json.dumps(result["report"])
            )
            # Compute coverage
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
        
    def display_message(self, message: str, tag: str) -> None:
        """
        Displays message in chat history
        
        Args:
            message: message to display (str).
            tag: tag name for formatting message (str).
        """
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.insert(tk.END, f"{tag}:\n{message}\n", tag)
        self.chat_history.config(state=tk.DISABLED)
        self.chat_entry.delete(0, tk.END)
    
    def clear_chat(self, event=None) -> None:
        """Clears chat history"""""
        self.chat_state.clear()
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.delete("1.0", tk.END)
        self.chat_history.config(state=tk.DISABLED)

    
    def select_model(self) -> None:
        """Sets model endpoint for API"""
        utils.set_model(self.model_var.get())

class CustomText(tk.Text):
    """
    CustomText to allow users to select and copy text but not edit it.
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.bind("<Button-1>", self.delayed_disable)
    
    def delayed_disable(self, event=None) -> None:
        self.config(state=tk.NORMAL)
        self.after(10, self.disable)
        
    def disable(self) -> None:
        self.config(state=tk.DISABLED)


class UtilsFrame(ttk.Frame):
    """
    Utils frame for the app. Contains file trees and tools.

    Attributes:
        file_tree: file tree for the repository.
        workst_tree: file tree for the overview of objects inside
            selected module and avaliable tests.
    """
    def __init__(self, master: AppFrame, *args, **kwargs) -> None:
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

    def fetch_data(
            self,
            obj_name: str,
            obj_type: str,
            class_name: Union[str, None]=None
        ) -> list[tuple]:
        """
        Fetches data from database for tests and coverage
        
        Args:
            obj_name: name of the object. 
            obj_type: type of the object.
                One of ["function", "class", "class method"].
            class_name: if obj_type is class method.
        
        Returns:
            list of tuples with data from database.
        """
        
        if obj_type == "class method":
            query = """
                SELECT * FROM tests
                    WHERE obj=? AND class=?
                    ORDER BY id DESC
            """
            data = self.master.conn.execute(
                query,
                (obj_name, class_name)
            ).fetchall()
            return data
        
        elif obj_type == "function":
            query = "SELECT * FROM tests WHERE obj=? ORDER BY id DESC"
        elif obj_type == "class":
            query = "SELECT * FROM tests WHERE class=? ORDER BY id DESC"
        else:
            raise ValueError("Unknown object type")
        data = self.master.conn.execute(query, (obj_name, )).fetchall()
        return data
    
    def get_cov(
            self,
            obj_name: str,
            obj_type: str,
            class_name: Union[str, None]=None
        ) -> tuple[set, set]:
        """
        Returns sets of executed, missing lines for the object,
            searches the database.

        Args:
            obj_name: name of the object.
            obj_type: type of the object.
                One of ["function", "class", "class method"].
            class_name: if obj_type is class method.

        Returns:
            tuple of sets of executed and missing lines.
        """
        
        resp = self.fetch_data(obj_name, obj_type, class_name)
        if resp:
            st, end, _ = self._find_lines(obj_name, obj_type, class_name)
            data = [json.loads(it[-1]) for it in resp]
            exec_lines = [method["executed_lines"] for method in data]
            miss_lines = [method["missing_lines"] for method in data]
            
            exec_lines_flt = {
                it
                for subl in exec_lines
                for it in subl
                if st <= it <= end
            }
            miss_lines_flt = {
                it
                for subl in miss_lines
                for it in subl
                if st <= it <= end
            }
            return exec_lines_flt, miss_lines_flt.difference(exec_lines_flt)
        else:
            return set(), set()

    def gen_tests(self, event=None) -> None:
        """Generates tests for selected object"""
        item = self.workst_tree.focus()
        obj_type = self.workst_tree.item(item)["values"][0]
        
        if obj_type == "function":
            obj = self.workst_tree.item(item)["text"]
            method_name = None
        elif obj_type == "class method":
            obj = self.workst_tree.item(self.workst_tree.parent(item))["text"]
            method_name = self.workst_tree.item(item)["text"]
        else:
            messagebox.showerror(
                "Error",
                "Please select a class method or function for testing"
            )
            return
        
        initial_prompt = config.ADAPTER.prepare_prompt(
            obj,
            method_name
        )
        self.master.chat_frame.send_message(initial_prompt, tag="User")

    def open_selected_item(self) -> None:
        """Opens selected item in default editor"""
        selected_item = self.file_tree.focus()
        if selected_item:
            item_path = self.file_tree.item(selected_item)["tags"][0]
            file = os.path.join(self.master.repo_dir, item_path)
            if os.path.isfile(file):
                self.file_tree.open_file(file)

    def select_for_testing(self) -> None:
        """
        Selects module for testing, sets adapter and displys objects
            in the selected module.
        """
        self.workst_tree.delete(*self.workst_tree.get_children())
        selected_item = self.file_tree.focus()
        if not selected_item:
            if self.current_mod:
                selected_item = self.current_mod
            else: return
        file_path: str = self.file_tree.item(selected_item)["tags"][0]
        if not file_path.endswith(self.master.suffix):
            messagebox.showerror(
                "Error",
                f"Please select a {self.master.suffix} file."
            )
            return

        _ = utils.set_adapter(self.master.language, module_dir=file_path)
        
        container_check = config.ADAPTER.check_reqs_in_container(
            self.master.cont_manager.container
        )
        if container_check:
            messagebox.showerror("Error", container_check)
            return
        
        func_names = config.ADAPTER.retrieve_func_defs()
        class_names = config.ADAPTER.retrieve_class_defs()
        if func_names + class_names == []:
            messagebox.showinfo(
                "Info",
                "No Function- or Class Definiton found in the selected file."
            )
            return
        
        for func_name in func_names:
            ex, miss = self.get_cov(func_name, "function")
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
            ex_c, miss_c = self.get_cov(cls, "class")
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
            methods = config.ADAPTER.retrieve_class_methods(cls)
            for method in methods:
                ex_m, miss_m = self.get_cov(method, "class method", cls)
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
        
    def open_cov_report(self) -> None:
        """Opens coverage report for selected object"""
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
        lns_ex, _ = self.get_cov(obj, obj_typ, cls)

        for i, line in enumerate(lines, start=start):
            ln_n = "{:3d} ".format(i) + line
            if i in lns_ex:
                cov_report.text_frame.insert("end", ln_n + "\n", "executed")
            else:
                cov_report.text_frame.insert("end", ln_n + "\n")
        cov_report.text_frame.configure(state=tk.DISABLED)

    def _find_lines(
            self,
            obj: str,
            obj_type: str,
            cls: Union[str, None]=None
        ) -> tuple[int, int, list[str]]:
        """
        Finds start, end lines of obj definition in module source code.

        Args:
            obj: name of the object.
            obj_type: type of the object.
                One of ["function", "class", "class method"].
            cls: class name if obj_type is class method.

        Returns:
            tuple of position where source_code starts, 
                position where it ends and source code line by line
                in a list.
        """

        module_source: str = config.ADAPTER.retrieve_module_source()
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
        """Helper function to retrieve source code for the object"""
        if obj_type == "function":
            source_code = config.ADAPTER.retrieve_func_source(obj)
        elif obj_type == "class":
            source_code = config.ADAPTER.retrieve_class_source(obj)
        elif obj_type == "class method":
            source_code = config.ADAPTER.retrieve_classmethod_source(
                class_name=cls,
                method_name=obj
            )
        else:
            messagebox.showinfo("Info", "No source code available.")
        return source_code

    def show_tests(self) -> None:
        """Shows tests for selected object in a new window"""
        item = self.workst_tree.focus()
        obj = self.workst_tree.item(item)["text"]
        obj_typ = self.workst_tree.item(item)["values"][0]
        if obj_typ == "class method":
            cls = self.workst_tree.item(self.workst_tree.parent(item))["text"]
        else:
            cls = None
        TestsWindow(self, obj, obj_typ, cls)
        
class TestsWindow(tk.Toplevel):
    """
    Window to show avaliable tests in the db for the selected object.

    Methods:
        populate_tree: populates tests tree with data from database.
        save_test: saves selected test to a file.
        delete_test: deletes selected test from the database.
        open_test: opens selected test in the current window.
        open_cov_report: opens coverage report for selected test.
        see_failures: shows failures for selected test.
    """
    def __init__(
            self,
            master: UtilsFrame,
            obj_name: str,
            obj_type: str,
            cls: Union[str, None]=None,
            *args,
            **kwargs
        ) -> None:
        super().__init__(master, *args, **kwargs)
        self.master: UtilsFrame
        self.title("Tests")
        self.geometry("800x600")
        self.tree  = ttk.Treeview(
            self,
            columns=("Name", "Total", "Failed", "Coverage")
        )
        self.tree.heading("#0", text="Number", anchor="w")
        self.tree.heading("Name", text="Name", anchor="w")
        self.tree.heading("Total", text="Total", anchor="w")
        self.tree.heading("Failed", text="Failed", anchor="w")
        self.tree.heading("Coverage", text="Coverage", anchor="w")
        self.tree.column("Name", width=100)
        self.tree.column("#0", width=10)
        self.tree.pack(fill="both", expand=True)
        _ = self.populate_tree(obj_name, obj_type, cls)

        self.tree.bind("<Double-Button-1>", self.open_test)
        # Right-click menu
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Open Coverage",
            command=lambda event=None: self.open_cov_report()
        )
        menu.add_command(
            label="See Failures",
            command=lambda event=None: self.see_failures()
        )
        menu.add_separator()
        menu.add_command(
            label="Save Test",
            command=lambda event=None: self.save_test()
        )
        menu.add_command(
            label="Delete Test",
            command=lambda event=None: self.delete_test()
        )


        self.tree.bind(
            "<Button-2>",
            lambda event: menu.post(event.x_root, event.y_root)
        )
        # Test Window
        self.test_window = CustomText(self, spacing3=6)
        self.test_window.configure(font=font.Font(family="Courier", size=12))
        
    def populate_tree(self, obj: str, obj_type: str, cls: str) -> None:
        """Populates tests tree with data from database"""
        data = self.master.fetch_data(obj, obj_type, cls)
        
        for i, (prim_id, _, cl_n, obj, _, test, cov_rp) in enumerate(data):
            if cl_n is None:
                obj_t = "function"
                lns_ex, lns_miss = self.master.get_cov(obj, obj_t)
            else:
                obj_t = "class method"
                lns_ex, lns_miss = self.master.get_cov(
                    obj,
                    obj_t,
                    cl_n
                )

            if len(lns_ex) == 0:
                cov = "0%"
            else:
                cov = f"{int((len(lns_ex)/(len(lns_ex)+len(lns_miss)))*100)}%"
        
            cov_report = json.loads(cov_rp)
            self.tree.insert(
                parent="",
                index="end",
                text=i+1,
                values=(
                    obj,
                    cov_report["tests_ran_n"],
                    len(cov_report["failures"]),
                    cov
                ),
                tags=(test, prim_id, obj_t, cov_rp, cl_n)
            )

    def save_test(self):
        """Saves selected test to a file"""
        test = self.tree.item(self.tree.focus())["tags"][0]
        file = filedialog.asksaveasfile(
            mode="w",
            defaultextension=".py",
            filetypes=[("Python Files", "*.py")]
        )
        if file:
            file.write(test)
            file.close()
    
    def delete_test(self):
        """Deletes selected test from the database"""
        primary_id = self.tree.item(self.tree.focus())["tags"][1]
        self.master.master.conn.execute(
            "DELETE FROM tests WHERE id=?",
            (primary_id, )
        )
        self.master.master.conn.commit()
        self.tree.delete(self.tree.focus())
    
    def open_cov_report(self):
        """Opens coverage report for selected test"""
        item = self.tree.focus()
        cov_window = CovWindow()
        cov_report = json.loads(self.tree.item(item)["tags"][3])
        exec_lines = cov_report["executed_lines"]
        start, _, lines = self.master._find_lines(
            self.tree.item(item)["values"][0],
            self.tree.item(item)["tags"][2],
            self.tree.item(item)["tags"][4]
        )
        for i, line in enumerate(lines, start=start):
            ln_n = "{:3d} ".format(i) + line
            if i in exec_lines:
                cov_window.text_frame.insert("end", ln_n + "\n", "executed")
            else:
                cov_window.text_frame.insert("end", ln_n + "\n")
        cov_window.text_frame.configure(state=tk.DISABLED)
    
    def see_failures(self):
        """Displays failures in a new window"""
        item = self.tree.focus()
        failures = json.loads(self.tree.item(item)["tags"][3])["failures"]
        fail_window = tk.Toplevel(self)
        fail_window.title("Failures")
        fail_window.geometry("800x600")
        text_wid = CustomText(fail_window, spacing3=6)
        text_wid.tag_configure("name", font=("Courier", 12, "bold"))
        text_wid.pack(fill="both", expand=True)
        if failures == []:
            text_wid.insert(tk.END, "All tests passed!")
        for (name, fail) in failures:
            text_wid.insert(tk.END, name + ":\n", "name")
            text_wid.insert(tk.END, fail + "\n")

    def open_test(self, event=None) -> None:
        """Displays selected test in the same window"""
        test = self.tree.item(self.tree.focus())["tags"][0]
        self.test_window.config(state=tk.NORMAL)
        self.test_window.delete("1.0", tk.END)
        self.test_window.insert(tk.END, test)
        self.test_window.config(state=tk.DISABLED)
        self.test_window.pack(fill="both", expand=True)

class WorkStationTree(ttk.Treeview):
    """WorkstationTree separed from UtilsFrame for clarity"""
    def __init__(self, master: UtilsFrame, *args, **kwargs):
        self.master: UtilsFrame
        super().__init__(master, columns=("Type", "Cov"), *args, **kwargs)
        self.heading("#0", text="Definition", anchor="w")
        self.heading("Type", text="Type", anchor="w")
        self.heading("Cov", text="Cov", anchor="w")
        self.column("Type", width=80)
        self.column("Cov", width=30)

    def refresh(self) -> None:
        """Refreshes tree"""
        self.master.select_for_testing()

class CovWindow(tk.Toplevel):
    """Coverage Window, for displaying coverage reports"""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.title("Coverage Report")
        self.geometry("800x600")
        self.text_frame = CustomText(self, spacing3=6)
        self.text_frame.configure(font=font.Font(family="Courier", size=12))
        self.text_frame.tag_configure("executed", foreground="green")
        self.text_frame.pack(fill="both", expand=True)
        
class ConfigWindow(tk.Toplevel):
    """Configuration Window for setting pipeline parameters"""
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

    def save_settings(self) -> None:
        """Saves pipeline settings to master"""
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
    """
    FileTree and its methods
    
    Methods:
        refresh: refreshes tree.
        insert_directory: resursivly inserts files into tree.
        is_ignored: checks if file is ignored by .gitignore.
        open_file: opens file in default editor.
    """
    def __init__(
            self,
            master: UtilsFrame,
            repo_dir: str,
            suffix: str,
            *args,
            **kwargs
        ) -> None:
        super().__init__(master, *args, **kwargs)
        self.repo_dir = repo_dir
        self.suffix = suffix
        self.column("#0", width=200)
        self.insert_directory(parent="", current_path=self.repo_dir)

    def refresh(self) -> None:
        """Refreshes tree"""
        self.delete(*self.get_children())
        self.insert_directory(parent="", current_path=self.repo_dir)

    def insert_directory(self, parent: str, current_path: str) -> None:
        """Recursivly inserts files into tree"""
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
        
    def is_ignored(self, fn: str) -> bool:
        """    
        looks for .gitignore to ignore files in FileTree.
        Also excludes:
            setup.py, files starting with "." and __pycache__.

        Args:
            fn: file name
        
        Returns:
            True if file is ignored, False otherwise.
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

    def open_file(self, file_path: str) -> None:
        """ Open file in default editor."""
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
