import tkinter as tk
from tkinter import ttk, messagebox, font, filedialog, scrolledtext
import os, sys, subprocess, fnmatch
from typing import Union
from dotenv import load_dotenv
from pathlib import Path
import sqlite3, json, logging
from . import ContainerManager, config, utils, generate_tests
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
        cont_manager: Handles container tasks. (ContainerManager).
        logger: logger for the app (logging.Logger).
    
    Methods:
        run: starts the app.
        load_intro: loads intro frame and its widgets.
        load_app: loads app frame and its widgets.
        reload_intro: clears app frame and reloads intro frame.
        open_repo: Transition from intro frame to app frame.
        prepare_db: prepares database if not yet avaliable in the repo.
        disconnect: disconnects from the db and stops the container.
        quit: quits the app.
        _clear_widgets: clears all deceased widgets of a frame.
        _center_window: centers window on the screen.
    """

    def __init__(self, root: tk.Tk) -> None:
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

        # Logger
        self.logger = logging.getLogger("AutoTestGen")
        self.logger.setLevel(logging.INFO)

        # Intro Frame
        self.intro_frame = IntroFrame(
            self.root,
            self.logger,
            width=500,
            height=500
        )

        # App Frame
        self.app_frame = AppFrame(
            self.root,
            self.logger,
            width=1028,
            height=500
        )
        self.load_intro()
    
    def load_intro(self) -> None:
        """Loads intro frame and its widgets."""
        self._center_window(self.root, 500, 500)
        self.intro_frame.tkraise()
        self.intro_frame.pack(fill="both", expand=True)
        self.intro_frame.load_widgets()
        # Connection between IntroFrame and AppFrame
        ttk.Button(
            self.intro_frame,
            text="Open Repository",
            cursor="hand1",
            command=self.open_repo
        ).pack(pady=5, expand=True)
    
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
        """Clears app frame and reloads intro frame."""
        self.disconnect()
        self._clear_widgets(self.app_frame)
        self.intro_frame.pack_propagate(False)
        self.load_intro()

    def open_repo(self) -> None:
        """
        - Sets important attributes (repo_dir, language).
        - Starts the container (ContainerManager).
        - Connects to the database (sqlite3.Connection).
        - Loads the app frame.
        """
        language = self.intro_frame.lang_entry.get()
        if language == "" or language is None:
                messagebox.showerror("Error", "Please select a language")
                self.logger.error("Language not selected")
                return
        
        image_name = self.intro_frame.image_entry.get()
        if image_name == "":
            messagebox.showerror("Error", "Please enter a Docker Image name")
            self.logger.error("Docker Image not specified")
            return
        
        directory = filedialog.askdirectory()
        if directory:
            self.logger.info("Checking size of the repository...")            
            tree = Path(directory).glob('**/*')
            if sum(f.stat().st_size for f in tree if f.is_file()) / 1e6 > 20:
                message = (
                    "Selected repository is larger than 20MB.\n"
                    "It might take time to mount it in the container.\n"
                    "Are you sure you selected  the right directory?"
                )
                resp = messagebox.askyesno("Warning", message)
                if not resp: return
        else:
            return
            
        self.repo_dir = directory
        self.language = language
        self.logger.info(f"Selected language: {self.language}")
        self.logger.info(f"Selected repo: {self.repo_dir}")
        
        self.logger.info("Connecting to database...")
        try:
            self.prepare_db()
        except Exception as e:
            self.logger.error(
                f"Error occured while connecting to database: {e}"
            )
            raise
        
        self.logger.info("Starting container...")
        try:
            self.cont_manager = ContainerManager(
                image_name=image_name,
                repo_dir=self.repo_dir
        )
        except Exception as e:
            self.logger.error(
                f"Error occured while initializing ContainerManager: {e}"
            )
            raise
        self.load_app()

    def prepare_db(self) -> None:
        """
        Prepares database if not yet avaliable in the selected repo.
        Otherwise connects to existing one. (autotestgen.db)
        """
        db_path = os.path.join(self.repo_dir, "autotestgen.db")
        if not os.path.isfile(db_path):
            try:
                self.conn = sqlite3.connect(db_path)
            except Exception as e:
                self.logger.error(
                    f"Error occured while connecting to database: {e}"
                )
                raise
            cursor = self.conn.cursor()
            try:
                cursor.execute(
                    """
                        CREATE TABLE tests (
                            id INTEGER PRIMARY KEY,
                            module TEXT,
                            class TEXT,
                            obj TEXT,
                            history TEXT,
                            test TEXT,
                            coverage_report TEXT
                        )
                    """
                )
                cursor.execute(
                    """
                        CREATE TABLE token_usage (
                            model TEXT,
                            input_tokens INTEGER,
                            output_tokens INTEGER
                        )
                    """
                )
                query = "INSERT INTO token_usage VALUES (?, ?, ?)"
                for model in MODELS:
                    cursor.execute(query, (model, 0, 0))
                self.conn.commit()

            except Exception as e:
                self.logger.error(
                    f"Error occured while creating Tables in database: {e}"
                )
                os.remove(db_path)
                raise
            finally:
                cursor.close()
        else:
            try:
                self.conn = sqlite3.connect(db_path)
            except Exception as e:
                self.logger.error(
                    f"Error occured while connecting to database: {e}"
                )
                raise
            self.logger.info("Database Connected")
            
    def _clear_widgets(self, frame: tk.Frame) -> None:
        """
        Helper function to clear all deceased widgets of a frame.

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
    
    def disconnect(self) -> None:
        """Disconnect from the db and stop the container."""
        if self.conn:
            self.logger.info("Disconnecting from db ...")
            self.conn.close()
        if self.cont_manager:
            self.logger.info("Stopping container ...")
            self.cont_manager.close_container()
    
    def quit(self) -> None:
        """Quit the app."""
        if messagebox.askyesno("Quit", "Do you want to quit?"):
            if self.app_frame.winfo_children():
                self.disconnect()
            self.root.destroy()


class IntroFrame(ttk.Frame):
    """
    Intro Frame and its widgets.
    
    Attributes:
        lang_entry: Selected Language variable (tk.StringVar).
        image_entry: Entered Docker Image variable (tk.StringVar).
        logger: Logger inherited from ChatApp.
    Methods:
        load_widgets: load intro frame widgets.
    """
    def __init__(self, root: tk.Tk, logger: logging.Logger, *args, **kwargs):
        super().__init__(root, *args, **kwargs)
        self.master: tk.Tk
        # For language and Image selection
        self.lang_entry = tk.StringVar()
        self.image_entry = tk.StringVar()
        # Logger
        self.logger = logger

    def load_widgets(self) -> None:
        """Loads widgets for intro frame"""
        self.master.resizable(False, False)
        self.configure(borderwidth=4, relief="groove")

        choice_frame = ttk.LabelFrame(self, text="Select a Language")
        choice_frame.pack(padx=20, pady=10, fill="x", expand=True)
        for choice in ADAPTERS.keys():
            ttk.Radiobutton(
                choice_frame,
                text=choice,
                variable=self.lang_entry,
                value=choice
            ).pack(anchor="w", padx=10, pady=5)
        
        image_frame = ttk.LabelFrame(
            self,
            text="Enter Docker Image 'Name:Tag'"
        )
        image_frame.pack(padx=10, pady=5, expand=True)
        self.image_entry = ttk.Entry(
            image_frame,
            textvariable=self.image_entry
        )
        self.image_entry.pack(anchor="w", padx=10, pady=5)
        
        log_console = LogConsole(self, height=10)
        log_console.pack(padx=10, side="bottom", expand=True)
        self.logger.handlers.clear()
        self.logger.addHandler(CustomHandler(log_console))

class AppFrame(ttk.Frame):
    """
    App frame class. Contains all the widgets for the app itself.

    Attributes:
        chat_frame: chat frame (ChatFrame) for chat history and entry.
        utils_frame: utils frame (UtilsFrame) for file trees and tools.
        logger: logger inherited from ChatApp.
    
    Methods:
        load_widgets: loads app frame widgets.
        configure_app: configures app frame with important attributes.
        refresh: refresh app frame to update tests and coverage data.
    """
    def __init__(self, root: tk.Tk, logger: logging.Logger, *args, **kwargs):
        super().__init__(root, *args, **kwargs)
        self.master: tk.Tk
        self.repo_dir: str
        self.language: str
        self.suffix: str
        self.conn: sqlite3.Connection
        self.cont_manager: ContainerManager

        self.chat_frame: ChatFrame
        self.utils_frame: UtilsFrame
        self.logger = logger

    def load_widgets(self) -> None:
        """Loads widgets for app frame"""
        self.master.resizable(True, True)
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
            cont_manager: Handling container tasks (ContainerManager).
        """
        self.repo_dir = repo_dir
        self.suffix = SUFFIXES[language]
        self.language = language
        self.conn = conn
        self.cont_manager = cont_manager

    def refresh(self) -> None:
        """Refreshes workstation to update tests and coverage data"""
        self.utils_frame.workst_tree.refresh()

class MenuBar(tk.Menu):
    """
    Menu bar for the app.
    Tabs:
        - Authentication: [Authenticate, Logout]
    
    methods:
        build_auth_window: builds (AuthentificationWindow)
        logout: logs out from OpenAI API.
    """
    def __init__(self,master: tk.Tk, repo_dir: str, *args, **kwargs) -> None:
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
        """Builds authentication window"""
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
    Authentication window for OpenAI API.
    
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
                f"No .env file found in {os.path.dirname(__file__)}"
            )

    def env_help(self, event=None) -> None:
        """Shows help message for .env authentication"""
        text = (
            "For .env authentication place .env file in the"
            f"{os.path.dirname(__file__)} directory. It should contain: "
            "at least the 'OPENAI_API_KEY' variable. If you aditionally "
            "want to specify organization key, add the 'OPENAI_ORG' variable."
        )
        messagebox.showinfo(".env authentication", text)


class ChatFrame(ttk.Frame):
    """
    Chat part of the app. Contains:
        - Chat history (CustomText).
        - Chat entry (ttk.Entry).
        - Send message button (ttk.Button).
        - Clear chat button (ttk.Button).
        - Select model combobox (ttk.Combobox).
        - Token count label (ttk.Label).
    
    Attributes:
        self.model_var: model variable to select model for API.
        self.chat_history: chat box.
        self.chat_entry: chat entry.
    
    Methods:
        send_message: sends message to API and displays response.
        display_message: displays message in chat history.
        clear_chat: clears chat history.
        populate_db: populates database with generated tests.
    """
    def __init__(self, master: AppFrame, *args, **kwargs) -> None:
        super().__init__(master, *args, **kwargs)
        # Model Variable
        self.master: AppFrame
        self._chat_state: list[dict[str, str]] = []
        self.model_var = tk.StringVar(value="gpt-3.5-turbo")
        self.configure(borderwidth=4, relief="groove")
        self.chat_history = CustomText(self, state=tk.DISABLED, bg="#B6CEB7")
        self.chat_history.tag_configure("User", foreground="black")
        self.chat_history.tag_configure("API", foreground="blue")
        self.chat_history.tag_configure("System", foreground="green")
        self.chat_history.pack(fill="both", expand=True)
        self.token_count = ttk.Label(
            self,
            text="Token Count: 0",
            foreground="red"
        )
        self.token_count.pack(anchor="ne")

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
    
    @property
    def chat_state(self) -> list[dict[str, str]]:
        """Returns chat state"""
        return self._chat_state

    def update_state(self, message: dict[str, str]) -> None:
        """Updates chat state and counts tokens"""
        if len(message) == 1:
            self._chat_state.append(message[0])
        else:
            self._chat_state.extend(message)
        self.update_token_count(utils.count_tokens(self._chat_state))
                                
    def update_token_count(self, count: int) -> None:
        """Updates token count"""
        self.token_count.config(text=f"Token Count: {count}")

    def send_message(self, message: list[dict], tag: str) -> None:
        """
        Send message to API and display response in chat history.

        Args:
            message: list of dicts with keys: "role" and "content".
            tag: tag name for formatting messages in chat history.

        Important:
            It enforces the user to start the chat with Generate Tests
            button, which runs pipeline and sends initial prompt
            engineered message, after which the user has possibility to
            communicate with the API directly through chat entry.
            Through the chat existence (before cleaning it),
            all the previous messages are send together
            with the new prompt.
        
        Raises:
            Exception: if there is a problem running the pipeline.
        """
        
        item = self.master.utils_frame.workst_tree.focus()
        if not item: 
            messagebox.showwarning(
                "Warning",
                "Please select an object to test first!"
            )
            return
        if config.API_KEY is None:
            messagebox.showwarning("Warning", "Please authenticate first!")
            return
        if config.MODEL is None:
            messagebox.showwarning("Warning", "Please select a model first!")
            return

        obj_name = self.master.utils_frame.workst_tree.item(item)["text"]
        obj_type = self.master.utils_frame.workst_tree.item(item)["values"][0]
        self.master.logger.info(
            f"Object name: {obj_name}, Object type: {obj_type}"
        )
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

        if len(message) > 1:
            if not self.chat_state:
                self.display_message(message[0]["content"], "System")
                self.display_message(message[1]["content"], tag)
                self.update_state(message[:2])
            else:
                # Omit system message
                self.display_message(message[1]["content"], tag)
                self.update_state(message[1:2])
                message = message[1:2]
        else:
            if not self.chat_state:
                messagebox.showwarning(
                    "Warning",
                    "Please start the chat with Generate Tests button first!"
                )
                return
            else:
                self.display_message(message[0]["content"], tag)
                self.update_state(message[0:1])
        
        try:
            result = generate_tests(
                self.chat_state,
                self.master.cont_manager,
                obj_name=import_name,
                temp=self.master.utils_frame.temp,
                n_samples=self.master.utils_frame.n_samples,
                max_iter=self.master.utils_frame.max_iter,
                logger=self.master.logger
            )
            self.update_state(
                [{"role": "assistant", "content": result["test"]}]
            )
            self.display_message(result["test"], "API")
            
            # Save token count to database
            try:
                in_tokens = utils.count_tokens(message)
                out_tok = utils.count_tokens(
                    [{"role": "assistant", "content": result["test"]}]
                )
                _, in_total, out_total = self.master.conn.execute(
                    "SELECT * FROM token_usage WHERE model=?",
                    (config.MODEL,)
                ).fetchone()
                self.master.conn.execute(
                    """
                        UPDATE token_usage
                        SET input_tokens=?,
                            output_tokens=?
                        WHERE model=?;
                    """,
                    (in_total + in_tokens, out_total + out_tok, config.MODEL)
                )
                self.master.conn.commit()

            except Exception as e:
                self.master.logger.warning(
                    f"Updating token usage in databse failed: {e}"
                )
        
        except Exception as e:
            self.master.logger.error(
                f"Error occured while running the pipeline: {e}"
            )
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
            self.master.logger.warning(
                f"compiling error: {result['report']['compile_error']}"
            )

        elif result["report"]["errors"]:
            messagebox.showinfo(
                "Info",
                (
                    "Generated tests contain errors\n"
                    "You can continue communicating with API to fix it or\n"
                    "alternatively you can try to manually fix it."
                )
            )
            messagebox.showerror(
                "Test Error",
                result["report"]["errors"]
            )
            self.master.logger.warning(
                f"test error: {result['report']['errors']}"
            )
        
        else:
            try:
                self.populate_db(
                    mod_name=os.path.basename(config.ADAPTER.module),
                    class_name=class_name,
                    obj_name=obj_name,
                    history=json.dumps(result["messages"]),
                    code=result["test"],
                    coverage=json.dumps(result["report"])
                )
                self.master.logger.info(
                    "Tests successfully added to the database"
                )
            except Exception as e:
                self.master.logger.warning(
                    f"Error occured while populating database: {e}"
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
                (
                    "Tests generated successfully and added to the database\n"
                    "You can see them by right-clicking on the corresponding "
                    "object in the Table on the right.\n" + str(cov_report)
                )
            )
            self.master.refresh()
        
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
        self.update_token_count(0)
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.delete("1.0", tk.END)
        self.chat_history.config(state=tk.DISABLED)

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
        self.master.conn.execute(
            insert_query,
            (mod_name, class_name, obj_name, history, code, coverage)
        )
        self.master.conn.commit()
    
    def select_model(self) -> None:
        """Sets model endpoint for API"""
        utils.set_model(self.model_var.get())


class UtilsFrame(ttk.Frame):
    """
    Utils frame for the app. Contains:
        - File tree (FileTree).
        - Workstation tree (WorkStationTree).
        - Tests tree (TestsTree).
        - Log console (LogConsole).
        - Config button (tk.Button).
        - Generate tests button (ttk.Button).
        - Load test state button (ttk.Button).
        - See usage button (ttk.Button).
    
    Important Methods:
        select_for_testing: selects object for testing.
        gen_tests: generates tests for selected object.
        

    """
    def __init__(self, master: AppFrame, *args, **kwargs) -> None:
        super().__init__(master, *args, **kwargs)
        self.configure(borderwidth=2, relief="groove")
        self.master: AppFrame
        # Pipeline default parameters
        self.temp: float = 0.1
        self.n_samples: int = 1
        self.max_iter: int = 3
        self.current_mod: Union[str, None] = None

        # Repo FileTree + right-click menu
        self.file_tree = FileTree(
            self, self.master.repo_dir,
            self.master.suffix,
            show="tree",
            columns=["Value"],
            height=4
        )
        self.file_tree.pack(fill="both", expand=True)
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(
            label="Open",
            command=lambda event=None: self.open_selected_item()
        )
        self.file_tree.bind("<Button-2>", lambda event: self.post_ft(event))
        self.file_tree.bind(
            "<Double-Button-1>",
            lambda event=None: self.select_for_testing()
        )
        
        # WorkstationTree + Right-click menu
        self.workst_tree = WorkStationTree(self, height=5)
        self.workst_tree.pack(fill="both", expand=True, pady=5)
        self.menu_wst = tk.Menu(self, tearoff=0)

        self.menu_wst.add_command(
            label="Open Coverage",
            command=self.open_cov_report
        )
        self.workst_tree.bind("<Double-Button-1>", self.show_tests)
        self.workst_tree.bind(
            "<Button-2>",
            lambda event: self.post_wst(event)
        )
        
        # TestsWinow
        self.tests_window = TestsTree(self, height=5)
        self.tests_window.pack(fill="both", expand=True)

        # Log-console
        log_console = LogConsole(self, height=5)
        log_console.pack(expand=True, fill="both")
        self.master.logger.handlers.clear()
        self.master.logger.addHandler(CustomHandler(log_console))
        
        # Workstation Tools
        config_button = tk.Button(self, text="\u2699", width=3, height=2)
        config_button.pack(side="left", pady=3, anchor="s")
        config_button.bind(
            "<Button-1>",
            lambda event: ConfigWindow(self, event.x_root, event.y_root)
        )

        # Generate Tests Button
        ttk.Button(
            self,
            text="Generate Tests",
            command=self.gen_tests
        ).pack(side="left", padx=5, pady=5, anchor="s")

        # Load Test State Button
        ttk.Button(
            self,
            text="Load Test State",
            command=self.load_test_state
        ).pack(side="left", padx=5, pady=5, anchor="s")

        # See Statistics
        usage_button = ttk.Button(self, text="See Usage",)
        usage_button.bind(
            "<Button-1>",
            lambda event: self.show_stats(event.x_root, event.y_root)
        )
        usage_button.pack(side="left", padx=5, pady=5, anchor="s")

    def post_ft(self, event: tk.Event) -> None:
        """Posts right-click menu for file tree"""
        item_iden = self.file_tree.identify_row(event.y)
        if item_iden:
            self.file_tree.focus(item_iden)
            self.file_tree.selection_set(item_iden)
            self.menu.post(event.x_root, event.y_root)

    def post_wst(self, event: tk.Event) -> None:
        """Posts right-click menu for workstation tree"""
        item_iden = self.workst_tree.identify_row(event.y)
        if item_iden:
            self.workst_tree.focus(item_iden)
            self.workst_tree.selection_set(item_iden)
            self.menu_wst.post(event.x_root, event.y_root)

    def show_stats(self, x, y) -> None:
        """Shows statistics window"""
        stats_window = Statistics(x, y, height=300, width=300)
        stats_window.populate_table(self.master.conn)

    def load_test_state(self, event=None) -> None:
        """Loads test state from the database"""
        if config.MODEL is None:
            messagebox.showwarning("Warning", "Please select a model first!")
            return
        
        item = self.tests_window.focus()
        if not item:
            return
        obj_type = self.tests_window.item(item)["tags"][2]
        if obj_type == "class":
            return

        prim_key = self.tests_window.item(item)["tags"][1]
        data = self.master.conn.execute(
            "SELECT history FROM tests WHERE id=?",
            (prim_key, )
        ).fetchall()
        if data:
            # If system message is present, avoid repeating it.
            messages = json.loads(data[0][0])
            if self.master.chat_frame.chat_state:
                messages = messages[1:]
            for message in messages:
                tag = message["role"].capitalize()
                if message["role"] == "assistant": tag = "API"
                self.master.chat_frame.display_message(
                    message["content"],
                    tag
                )
            self.master.chat_frame.update_state(json.loads(data[0][0]))
     
        else:
            messagebox.showerror("Error", "No test history found in the db")
    
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
            obj_type: One of ['function', 'class', 'class method'].
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
        accumulated over all avaliable tests. searches the database.

        Args:
            obj_name: name of the object.
            obj_type: One of ["function", "class", "class method"].
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
        if not item:
            messagebox.showwarning(
                "Warning",
                "Please select an object to test first!"
            )
            return
        
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
        try:
            initial_prompt = config.ADAPTER.prepare_prompt(
                obj,
                method_name
            )
        except Exception as e:
            self.master.logger.error(
                f"Error occured while preparing initial prompt: {e}"
            )
            raise
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
        Selects module for testing, prepares adapter and populates
        workstation tree with functions and class methods.
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
        """Opens coverage report for selected object in new window"""
        item = self.workst_tree.focus()
        if not item: return
        cov_report = CovWindow()
        obj = self.workst_tree.item(item)["text"]
        obj_typ = self.workst_tree.item(item)["values"][0]
        if obj_typ == "class method":
            cls = self.workst_tree.item(self.workst_tree.parent(item))["text"]
        else:
            cls = None
        start, _, lines = self._find_lines(obj, obj_typ, cls)

        # Numbering and coloring lines
        lns_ex, lns_miss = self.get_cov(obj, obj_typ, cls)

        for i, line in enumerate(lines, start=start):
            ln_n = "{:3d} ".format(i) + line
            if i in lns_ex:
                cov_report.text_frame.insert("end", ln_n + "\n", "executed")
            elif i in lns_miss:
                cov_report.text_frame.insert("end", ln_n + "\n", "missing")
            else:
                cov_report.text_frame.insert("end", ln_n + "\n", "irrelevant")
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
                break
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

    def show_tests(self, event=None) -> None:
        """Populates tests tree with tests for selected object"""
        item = self.workst_tree.focus()
        if not item: return
        self.tests_window.delete(*self.tests_window.get_children())
        obj = self.workst_tree.item(item)["text"]
        obj_typ = self.workst_tree.item(item)["values"][0]
        if obj_typ == "class method":
            cls = self.workst_tree.item(self.workst_tree.parent(item))["text"]
        else:
            cls = None
        self.tests_window.populate_tree(obj, obj_typ, cls)
        
class TestsTree(ttk.Treeview):
    """
    Representing tests in the database for selected object
    
    Methods:
        post_tt: posts right-click menu for tests tree.
        populate_tree: populates tests tree with data from database.
        save_test: saves selected test to a file.
        delete_test: deletes selected test from the database.
        open_cov_report: opens coverage report for selected test.
        see_failures: show failures for selected test in new window.
        open_test: opens selected test in new window.
    """
    def __init__(self, master: UtilsFrame, *args, **kwargs):
        self.master: UtilsFrame
        col_names = ("Name", "Total", "Failed", "Coverage")
        super().__init__(master, columns=col_names, *args, **kwargs)
        
        self.heading("#0", text="N", anchor="w")
        self.heading("Name", text="Name", anchor="w")
        self.heading("Total", text="Total", anchor="w")
        self.heading("Failed", text="Failed", anchor="w")
        self.heading("Coverage", text="Coverage", anchor="w")
        self.column("Name", width=100)
        self.column("#0", width=25)
        self.column("Total", width=50)
        self.column("Failed", width=50)
        self.column("Coverage", width=70)

        self.bind("<Double-Button-1>", self.open_test)
        # Right-click menu
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(
            label="Open Coverage",
            command=lambda event=None: self.open_cov_report()
        )
        self.menu.add_command(
            label="See Failures",
            command=lambda event=None: self.see_failures()
        )
        self.menu.add_separator()
        self.menu.add_command(
            label="Save Test",
            command=lambda event=None: self.save_test()
        )
        self.menu.add_command(
            label="Delete Test",
            command=lambda event=None: self.delete_test()
        )
        self.bind("<Button-2>", lambda event: self.post_tt(event))
        # Test Window
        self.test_window = CustomText(self.master, height=6, spacing3=6)
        self.test_window.configure(font=font.Font(family="Courier", size=12))

    def post_tt(self, event: tk.Event) -> None:
        """Posts right-click menu for tests tree"""
        item_iden = self.identify_row(event.y)
        if item_iden:
            self.focus(item_iden)
            self.selection_set(item_iden)
            self.menu.post(event.x_root, event.y_root)

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
            self.insert(
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
        test = self.item(self.focus())["tags"][0]
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
        primary_id = self.item(self.focus())["tags"][1]
        self.master.master.conn.execute(
            "DELETE FROM tests WHERE id=?",
            (primary_id, )
        )
        self.master.master.conn.commit()
        self.delete(self.focus())
    
    def open_cov_report(self):
        """Opens coverage report for selected test"""
        item = self.focus()
        if not item: return
        cov_window = CovWindow()
        cov_report = json.loads(self.item(item)["tags"][3])
        exec_lines = cov_report["executed_lines"]
        miss_lines = cov_report["missing_lines"]
        start, _, lines = self.master._find_lines(
            self.item(item)["values"][0],
            self.item(item)["tags"][2],
            self.item(item)["tags"][4]
        )
        for i, line in enumerate(lines, start=start):
            ln_n = "{:3d} ".format(i) + line
            if i in exec_lines:
                cov_window.text_frame.insert("end", ln_n + "\n", "executed")
            elif i in miss_lines:
                cov_window.text_frame.insert("end", ln_n + "\n", "missing")
            else:
                cov_window.text_frame.insert("end", ln_n + "\n", "irrelevant")
        cov_window.text_frame.configure(state=tk.DISABLED)
    
    def see_failures(self):
        """Displays failures in a new window"""
        item = self.focus()
        if not item: return
        failures = json.loads(self.item(item)["tags"][3])["failures"]
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
        """Displays selected test in new window"""
        item = self.focus()
        if item:
            obj = self.item(item)["values"][0]
            test = self.item(item)["tags"][0]
            test_id = self.item(self.focus())["tags"][1]
            TestWindow(
                self.master,
                obj,
                test_id,
                test,
                self.master.master.conn
            )
    
    def clear_tree(self, event=None) -> None:
        """Clears tests tree"""
        self.delete(*self.get_children())


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
        self.master.tests_window.clear_tree()

class TestWindow(tk.Toplevel):
    """
    Test Window for displaying tests in a new window
    
    Methods:
        save_changes: saves changes to tests to the database.
    """
    def __init__(
        self,
        master: UtilsFrame,
        obj: str,
        test_id: str,
        test: str,
        conn:sqlite3.Connection,
        *args,
        **kwargs
    ) -> None:
        super().__init__(master, *args, **kwargs)
        self.master: UtilsFrame
        self.title(obj)
        self.geometry("800x600")
        self.text_frame = tk.Text(self, spacing3=6)
        self.text_frame.configure(font=font.Font(family="Courier", size=12))
        self.text_frame.insert(tk.END, test)
        self.text_frame.pack(fill="both", expand=True)

        self.save_test = ttk.Button(
            self,
            text="Save Changes",
            command=lambda event=None:self.save_changes(test_id, conn)
        )
        self.save_test.pack(side="left", padx=5, pady=5)

    def save_changes(self, test_id: int, conn: sqlite3.Connection) -> None:
        """Saves changes to the database"""
        modified_test = self.text_frame.get("1.0", tk.END)
        conn.execute(
            "UPDATE tests SET test=? WHERE id=?",
            (modified_test, test_id)
        )
        # Modify also chat history
        chat_history = conn.execute(
            "SELECT history FROM tests WHERE id=?",
            (test_id, )
        ).fetchone()[0]
        chat_history = json.loads(chat_history)
        chat_history[-1]["content"] = modified_test
        conn.execute(
            "UPDATE tests SET history=? WHERE id=?",
            (json.dumps(chat_history), test_id)
        )
        conn.commit()
        self.destroy()
        self.master.show_tests()

class CovWindow(tk.Toplevel):
    """Coverage Window, for displaying coverage reports"""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.title("Coverage Report")
        self.geometry("800x600")
        self.text_frame = CustomText(self, spacing3=6)
        self.text_frame.configure(font=font.Font(family="Courier", size=12))
        self.text_frame.tag_configure("executed", foreground="green")
        self.text_frame.tag_configure("missing", foreground="red")
        self.text_frame.tag_configure("irrelevant", foreground="grey")
        self.text_frame.pack(fill="both", expand=True)
        
class ConfigWindow(tk.Toplevel):
    """
    Configuration Window for setting pipeline parameters
    
    Methods:
        save_settings: saves pipeline variables to master.
    """
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
            self,text="Ok", command=self.save_settings
        ).grid(row=3, column=0, padx=5, sticky="w")
        ttk.Button(
            self, text="Cancel", command=self.destroy
        ).grid(row=3, column=1, pady=5, padx=5, sticky="w")

    def save_settings(self) -> None:
        """Saves pipeline variables to master"""
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
        self.master: UtilsFrame
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
        looks for .gitignore to ignore files in FileTree. Also excludes
        ['setup.py', '__pycache__', files starting with '.']
        
        Args:
            fn: file name to check.
        
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
        """Opens file in default editor."""
        try:
            if sys.platform.startswith('darwin'):
                subprocess.call(('open', file_path))
            elif sys.platform.startswith('win32'):
                subprocess.call(('start', file_path), shell=True)
            elif sys.platform.startswith('linux'):
                subprocess.call(('xdg-open', file_path))
            else:
                print("Unsupported platform: ", sys.platform)
        except Exception as e:
            messagebox.showerror("Error", "Error occured while opening file")
            self.master.master.logger.error(f"{e}")
            raise

class CustomText(tk.Text):
    """Custom tk.Text: allows selecting and copying text."""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.bind("<Button-1>", self.delayed_disable)
    
    def delayed_disable(self, event=None) -> None:
        """Disables text widget after 10ms"""
        self.config(state=tk.NORMAL)
        self.after(10, self.disable)
        
    def disable(self) -> None:
        self.config(state=tk.DISABLED)

class Statistics(tk.Toplevel):
    """Class for Visualizing token usage statistics"""
    def __init__(self, x_geom, y_geom, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Statistics")
        self.geometry(f"+{x_geom}+{y_geom}")
        self.resizable(False, False)
        self.table = ttk.Treeview(self)
        self.table.pack(fill="both", expand=True)
        self.table["columns"] = ("Model", "Input Tokens", "Output Tokens")
        self.table.column("#0", width=0, stretch="no")
        self.table.column("Model", anchor="w", width=100)
        self.table.column("Input Tokens", anchor="w", width=100)
        self.table.column("Output Tokens", anchor="w", width=100)
        self.table.heading("#0", text="", anchor="w")
        self.table.heading("Model", text="Model", anchor="w")
        self.table.heading("Input Tokens", text="Input Tokens", anchor="w")
        self.table.heading("Output Tokens", text="Output Tokens", anchor="w")
    
    def populate_table(self, conn: sqlite3.Connection) -> None:
        """Populates table with token usage statistics."""
        self.table.delete(*self.table.get_children())
        data = conn.execute("SELECT * FROM token_usage").fetchall()
        for row in data:
            self.table.insert("", "end", text="", values=row)
        self.table.pack(fill="both", expand=True)

class LogConsole(scrolledtext.ScrolledText):
    """Log Console for the app"""
    def __init__(self, master, *args, **kwargs) -> None:
        super().__init__(
            master,
            font=("Courier", 12),
            wrap=tk.WORD,
            bg="#F0F0F0",
            *args,
            **kwargs
        )
        self.configure(state=tk.DISABLED)
        self.config(borderwidth=4, relief="groove")
        self.tag_configure("INFO", foreground="black")
        self.tag_configure("WARNING", foreground="orange")
        self.tag_configure("ERROR", foreground="red")
        self.tag_configure("DEBUG", foreground="blue")
        # Right-click menu
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(
            label="Clear",
            command=lambda event=None: self.clear_console()
        )
        self.bind(
            "<Button-2>",
            lambda event: self.menu.post(event.x_root, event.y_root)
        )

    def clear_console(self) -> None:
        """Clears console"""
        self.config(state=tk.NORMAL)
        self.delete("1.0", tk.END)
        self.config(state=tk.DISABLED)
  

class CustomHandler(logging.Handler):
    """Custom logging handler for redirecting logs to GUI"""
    def __init__(self, text: LogConsole, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.text: LogConsole = text
        self.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord) -> None:
        """Emits log record and displays it in the console"""
        self.text.config(state=tk.NORMAL)
        msg = self.format(record)
        self.text.insert(tk.END, msg + "\n", record.levelname)
        self.text.see(tk.END)
        self.text.update()
        self.text.config(state=tk.DISABLED)


def main() -> None:
    """Entry point for the app"""
    root = tk.Tk()
    app = ChatApp(root)
    app.run()

if __name__ == "__main__":
    main()