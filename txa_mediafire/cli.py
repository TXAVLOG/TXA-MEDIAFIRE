#!/usr/bin/env python3

import base64
import hashlib
import importlib.resources
import json
import platform
import subprocess
import sys
from re import findall, search
from time import sleep
from datetime import datetime
from requests import get
from gazpacho import Soup
from argparse import ArgumentParser
from os import path, makedirs, remove, environ
from threading import BoundedSemaphore, Thread, Event, Lock

# --- Rich UI Imports ---
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    ProgressColumn,
    TaskID,
)
from rich.table import Table
from rich.live import Live
from rich.theme import Theme
from rich import box

# --- Configuration ---
APP_VERSION = "2.1.4"

# Default ignore lists
IGNORE_EXTENSIONS = {".pyc", ".pyo", ".pyd", ".DS_Store", "Thumbs.db"}
IGNORE_NAMES = {"__pycache__", "desktop.ini"}

custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "highlight": "magenta",
    "link": "blue underline",
})

console = Console(theme=custom_theme)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Accept-Encoding": "gzip",
}



# --- Localization & Config ---
def get_config_path():
    system = platform.system()
    if system == "Windows":
        base_path = environ.get("LOCALAPPDATA", path.expanduser("~\\AppData\\Local"))
        return path.join(base_path, "TXAMEDIAFIRE", "config.json")
    elif system == "Darwin":
        return path.expanduser("~/Library/Application Support/TXAMEDIAFIRE/config.json")
    else:
        return path.expanduser("~/.config/TXAMEDIAFIRE/config.json")

def load_config():
    config_path = get_config_path()
    if path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"language": "en"}
    return {"language": "en"}

def save_config(language):
    config_path = get_config_path()
    config_dir = path.dirname(config_path)
    try:
        makedirs(config_dir, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"language": language}, f)
        return True
    except Exception as e:
        console.print(f"[bold red]Error saving config:[/bold red] {e}")
        return False

def get_history_path():
    return path.join(path.dirname(get_config_path()), "history.txa")

def xor_cipher(data: str) -> str:
    key = "txamediafire"
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data))

def save_to_history(filename, size_str):
    history_path = get_history_path()
    try:
        data = []
        if path.exists(history_path):
            with open(history_path, "rb") as f:
                enc_data = f.read()
                try:
                    decrypted = xor_cipher(base64.b64decode(enc_data).decode("utf-8"))
                    data = json.loads(decrypted)
                except: data = []
        
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file": filename,
            "size": size_str
        }
        data.append(entry)
        
        # Keep only last 100 entries for performance
        data = data[-100:]
        
        json_str = json.dumps(data)
        encrypted = base64.b64encode(xor_cipher(json_str).encode("utf-8"))
        with open(history_path, "wb") as f:
            f.write(encrypted)
    except: pass

def show_history():
    history_path = get_history_path()
    print_header()
    table = Table(title=f"[bold cyan]{T['history_title']}[/bold cyan]", box=box.ROUNDED, expand=True)
    table.add_column(T["history_header_date"], style="dim", width=20)
    table.add_column(T["history_header_file"], style="green")
    table.add_column(T["history_header_size"], justify="right", style="magenta", width=15)
    
    if not path.exists(history_path):
        console.print(f"[italic yellow]{T['history_empty']}[/italic yellow]")
        return

    try:
        with open(history_path, "rb") as f:
            enc_data = f.read()
            decrypted = xor_cipher(base64.b64decode(enc_data).decode("utf-8"))
            data = json.loads(decrypted)
            
            for item in reversed(data): # Show latest first
                table.add_row(item["date"], item["file"], item["size"])
                
        console.print(table)
    except Exception as e:
        console.print(f"[error]Error reading history:[/error] {e}")

# Load global config
CONFIG = load_config()
LANG = CONFIG.get("language", "en")

def load_translations():
    try:
        # Load defaults first (Source of Truth)
        default_content = importlib.resources.files("txa_mediafire").joinpath("translations.json").read_text(encoding="utf-8")
        translations = json.loads(default_content)

        config_path = get_config_path()
        config_dir = path.dirname(config_path)
        trans_path = path.join(config_dir, "translations.json")
        
        # Ensure config dir exists
        try:
            makedirs(config_dir, exist_ok=True)
        except: pass

        # Load user file if exists and merge
        if path.exists(trans_path):
            try:
                with open(trans_path, "r", encoding="utf-8") as f:
                    user_trans = json.load(f)
                    # Merge user overrides into defaults
                    for lang, keys in user_trans.items():
                        if lang in translations:
                            translations[lang].update(keys)
                        else:
                            translations[lang] = keys
            except Exception as e:
                pass # If user file is bad, just use defaults
        else:
            # If missing, write defaults
            try:
                with open(trans_path, "w", encoding="utf-8") as f:
                    f.write(default_content)
            except: pass

        return translations

    except Exception as e:
        console.print(f"[bold red]Critical Error loading translations:[/bold red] {e}")
        return {}

TRANSLATIONS = load_translations()
T = TRANSLATIONS.get(LANG, TRANSLATIONS.get("en", {}))

# --- Statistics Tracking ---
class DownloadStats:
    def __init__(self):
        self.total_files = 0
        self.total_size = 0
        self.downloaded_files = 0
        self.downloaded_bytes = 0
        self.skipped = 0
        self.failed = 0
        self.lock = Lock()

stats = DownloadStats()

class ClockColumn(ProgressColumn):
    """Renders the current time."""
    def render(self, task) -> Text:
        current_time = datetime.now().strftime("%H:%M:%S %d/%m/%y")
        return Text(current_time, style="bold cyan")

# --- Utility Functions ---
def format_size(size_bytes):
    if size_bytes == 0: return "0.00 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

def is_junk_file(filename: str) -> bool:
    if any(filename.endswith(ext) for ext in IGNORE_EXTENSIONS):
        return True
    if filename in IGNORE_NAMES:
        return True
    return False

def hash_file(filename: str) -> str:
    h = hashlib.sha256()
    try:
        with open(filename, "rb") as file:
            while True:
                chunk = file.read(65536)
                if not chunk:
                    break
                h.update(chunk)
    except Exception:
        return ""
    return h.hexdigest()

def normalize_file_or_folder_name(filename: str) -> str:
    return "".join(
        [char if (char.isalnum() or char in "-_. ") else "-" for char in filename]
    )

# --- Update Checker ---
def get_pypi_version(package_name):
    try:
        r = get(f"https://pypi.org/pypi/{package_name}/json", timeout=10)
        if r.status_code == 200:
            return r.json().get("info", {}).get("version")
    except:
        pass
    return None

def check_update(silent=False):
    """Checks for updates on PyPI."""
    if not silent:
        console.print(f"[dim]{T['checking_update']}[/dim]")
    
    latest_version = get_pypi_version("txa-m")
    
    # If package not found (yet), just return or handle gracefully
    if not latest_version:
        if not silent: console.print(f"[dim]Could not retrieve version from PyPI.[/dim]")
        return

    if latest_version != APP_VERSION:
        console.print(Panel(
            f"{T['update_available']}\n"
            f"[bold red]v{APP_VERSION}[/bold red] -> [bold green]v{latest_version}[/bold green]\n\n"
            f"[yellow]{T['update_notice']}[/yellow]\n"
            f"[dim]Alternative: pip install txa-m=={latest_version}[/dim]",
            title="[bold magenta]UPDATE[/bold magenta]",
            border_style="magenta",
            expand=False
        ))
    elif not silent:
        console.print(f"[bold green]{T['no_update']}[/bold green]")

def perform_update():
    """Updates the tool via pip."""
    try:
        latest = get_pypi_version("txa-m")
        if not latest:
            console.print("[bold red]Could not find 'txa-m' on PyPI.[/bold red]")
            return

        if latest == APP_VERSION:
             console.print(f"[bold green]{T['no_update']}[/bold green]")
             return
             
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "txa-m"]
        
        with console.status(f"[bold info]{T['updating']} {latest}...[/bold info]", spinner="dots") as status:
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                encoding='utf-8', 
                errors='replace'
            )
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    line = line.strip()
                    if not line: continue
                    
                    # Filter output for cleaner log
                    if "Requirement already satisfied" in line:
                         status.update(f"[dim]{line}[/dim]")
                    elif "Failed to remove contents" in line or "You can safely remove it manually" in line:
                         # Hide harmless Windows folder locking warnings
                         continue
                    elif "txa-m" in line.lower() or "successfully" in line.lower():
                         console.print(f"  [green]>> {line}[/green]")
                    else:
                         status.update(f"[dim]{line}[/dim]")
        
        if process.returncode == 0:
            console.print(f"[bold success]{T['update_success']}[/bold success]")
            sys.exit(0)
        else:
            console.print(f"[bold red]Update failed with code {process.returncode}[/bold red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]An error occurred:[/bold red] {e}")
        sys.exit(1)

# --- Custom Parser ---
class RichArgumentParser(ArgumentParser):
    def error(self, message):
        print_header()
        
        # Translate common argparse messages
        if "unrecognized arguments" in message:
            message = message.replace("unrecognized arguments", T.get('err_unrecognized_args', "Unrecognized arguments"))
        elif "the following arguments are required" in message:
            message = message.replace("the following arguments are required", T.get('err_missed_args', "Missing required arguments"))
        
        console.print(Panel(
            f"{message}\n\n[dim]Run with --help for usage.[/dim]",
            title="[bold red]ARGUMENT ERROR[/bold red]",
            style="red"
        ))
        sys.exit(1)

# --- API Endpoints ---
def get_files_or_folders_api_endpoint(filefolder: str, folder_key: str, chunk: int = 1, info: bool = False) -> str:
    return (
        f"https://www.mediafire.com/api/1.4/folder"
        f"/{'get_info' if info else 'get_content'}.php?r=utga&content_type={filefolder}"
        f"&filter=all&order_by=name&order_direction=asc&chunk={chunk}"
        f"&version=1.5&folder_key={folder_key}&response_format=json"
    )

def get_info_endpoint(file_key: str) -> str:
    return f"https://www.mediafire.com/api/file/get_info.php?quick_key={file_key}&response_format=json"

# --- Custom UI Helper ---
def print_header():
    console.clear()
    
    # Detect Platform
    sys_name = platform.system()
    is_termux = "com.termux" in environ.get("PREFIX", "")
    
    p_win = "[/dim][bold green underline]Windows[/bold green underline][dim]" if sys_name == "Windows" else "Windows"
    p_lin = "[/dim][bold green underline]Linux[/bold green underline][dim]" if sys_name == "Linux" and not is_termux else "Linux"
    p_mac = "[/dim][bold green underline]macOS[/bold green underline][dim]" if sys_name == "Darwin" else "macOS"
    p_and = "[/dim][bold green underline]Android (Termux)[/bold green underline][dim]" if is_termux else "Android (Termux)"
    
    platform_str = f"{p_win} • {p_lin} • {p_mac} • {p_and}"
    current_time = datetime.now().strftime("%H:%M:%S %d/%m/%Y")

    banner_text = (
        f"[bold cyan]TXA MediaFire Bulk Downloader v{APP_VERSION}[/bold cyan]\n"
        f"[dim]{T['banner_desc']}[/dim]\n"
        f"[dim]Platform: {platform_str}[/dim]\n"
        f"[dim]Time: {current_time}[/dim]\n"
        f"[italic]{T['copyright_notice']}[/italic]\n"
        f"[bold red]{T['quote_warning']}[/bold red]"
    )
    console.print(Panel(
        banner_text,
        box=box.ROUNDED,
        border_style="cyan",
        expand=False
    ))

# --- Custom Help ---
def show_help():
    print_header()
    
    usage_table = Table(box=None, padding=(0, 2), show_header=False)
    usage_table.add_column("Command", style="bold green")
    usage_table.add_column("Description", style="white")
    
    usage_table.add_row("txa-m", "Run the tool (alias)")
    
    console.print("\n[bold underline]USAGE:[/bold underline]")
    console.print("  txa-m [bold yellow]\"<URL>\"[/bold yellow] [bold magenta][OPTIONS][/bold magenta]")
    
    console.print("\n[bold underline]OPTIONS:[/bold underline]")
    
    opts_table = Table(box=None, padding=(0, 2), show_header=False)
    opts_table.add_column("Option", style="bold yellow", width=30)
    opts_table.add_column("Description", style="white")
    
    opts_table.add_row('"-h", "--help"', "Show this help message")
    opts_table.add_row('"-o", "--output"', 'Output directory [dim](supports env vars)[/dim]')
    opts_table.add_row('"-t", "--threads"', "Number of threads [dim](default: 10)[/dim]")
    opts_table.add_row('"-ie", "--ignore-extensions"', "Ignore specific extensions [dim](e.g. .mp4,.mkv)[/dim]")
    opts_table.add_row('"-in", "--ignore-names"', "Ignore specific filenames")
    opts_table.add_row('"--sl", "--set-lang"', "Set language [dim](en/vi)[/dim]")
    opts_table.add_row('"-hi", "--history"', "Show download history [dim](encrypted)[/dim]")
    opts_table.add_row('"-u", "--update"', "Check and auto-update tool via pip")
    opts_table.add_row('"-v", "--version"', "Show version info")
    
    console.print(opts_table)
    
    console.print("\n[bold underline]EXAMPLES:[/bold underline]")
    console.print('  [dim]# Download a folder to Desktop[/dim]')
    console.print('  txa-m [green]"https://mediafire.com/..."[/green] -o [yellow]"%USERPROFILE%/Desktop"[/yellow]')
    console.print('\n  [dim]# Download with 20 threads, ignoring .mp4 files[/dim]')
    console.print('  txa-m [green]"https://mediafire.com/..."[/green] -t 20 -ie .mp4')
    console.print('\n  [dim]# Check for updates[/dim]')
    console.print('  txa-m --u')
    
    console.print("\n[dim]Note: Always wrap URLs and Paths in double quotes to avoid terminal errors.[/dim]")

# --- Main Logic ---
def main():
    global IGNORE_EXTENSIONS, IGNORE_NAMES, T, LANG
    
    parser = RichArgumentParser(add_help=False)
    
    # Make mediafire_url optional so we can run just --set-lang or --help
    parser.add_argument("mediafire_url", nargs="?", help='The URL of the file or folder (MUST be wrapped in quotes)')
    parser.add_argument("-o", "--output", help='Output folder (supports env vars, MUST be wrapped in quotes)', default=".")
    parser.add_argument("-t", "--threads", help="Number of threads", type=int, default=10)
    parser.add_argument("-ie", "--ignore-extensions", help="Comma-separated list of extensions to ignore (e.g. .mp4,.mkv)", default=None)
    parser.add_argument("-in", "--ignore-names", help="Comma-separated list of filenames to ignore", default=None)
    parser.add_argument("-v", "--version", action="version", version=f"TXA MediaFire Bulk Downloader v{APP_VERSION} (c) TXA", help="Show version and copyright info")
    parser.add_argument("--sl", "--set-lang", choices=["en", "vi"], help="Set application language (en/vi)", dest="set_lang")
    parser.add_argument("-hi", "--history", action="store_true", help="Show encrypted download history")
    parser.add_argument("-u", "--update", action="store_true", help="Check and auto-update tool via pip")
    parser.add_argument("-h", "--help", action="store_true", help="Show this help message")
    
    args = parser.parse_args()

    # Handle Help
    if args.help:
        show_help()
        sys.exit(0)

    # Handle History
    if args.history:
        show_history()
        sys.exit(0)

    # Handle Language Setting
    if args.set_lang:
        if save_config(args.set_lang):
            # Reload msg to show in new language immediately
            T = TRANSLATIONS.get(args.set_lang, TRANSLATIONS["en"])
            cfg_path = get_config_path()
            console.print(Panel(
                f"[bold success]{T['lang_set']}[/bold success]\n[dim]Config: {cfg_path}[/dim]", 
                border_style="green", 
                expand=False
            ))
            sys.exit(0)
    
    # Handle Update
    if args.update:
        perform_update()
        sys.exit(0)

    # Requirement: If no URL provided and no other action taken, show help
    if not args.mediafire_url:
        show_help()
        check_update(silent=True) # Check quickly on empty run
        sys.exit(0)

    # Update ignore lists
    if args.ignore_extensions:
        exts = [e.strip() for e in args.ignore_extensions.split(",")]
        IGNORE_EXTENSIONS = set(exts)
    
    if args.ignore_names:
        names = [n.strip() for n in args.ignore_names.split(",")]
        IGNORE_NAMES = set(names)

    # Validate URL FIRST before showing banner
    folder_or_file = findall(r"mediafire\.com/(folder|file|file_premium)\/([a-zA-Z0-9]+)", args.mediafire_url)
    if not folder_or_file:
        # Improved error handling logic
        print_header()
        input_val = args.mediafire_url.lower()
        
        if not input_val.startswith("http") and not input_val.startswith("mediafire"):
             msg = f"{T['invalid_cmd']}\n[yellow]Input: {args.mediafire_url}[/yellow]"
        else:
             msg = f"{T['invalid_link']}\n[dim]{args.mediafire_url}[/dim]"
        
        console.print(Panel(msg, title="[bold red]ERROR[/bold red]", style="red"))
        sys.exit(1)

    t_type, key = folder_or_file[0]

    # Process Output Directory
    output_dir = path.expandvars(args.output)
    output_dir = path.expanduser(output_dir)
    output_dir = path.abspath(output_dir)

    # Ensure output directory exists before showing banner to confirm we can write
    try:
        makedirs(output_dir, exist_ok=True)
    except Exception as e:
        console.print(f"[bold error]Error:[/bold error] {T['error_create_dir']} '{output_dir}'.\nReason: {e}", style="error")
        sys.exit(1)

    # Show Banner (Aesthetics Improved)
    print_header()
    
    console.print(f"[dim]{T['output_dir']}: [link=file://{output_dir}]{output_dir}[/link][/dim]\n")

    # --- Discovery Phase ---
    all_tasks = []
    with console.status(f"[bold info]{T['scanning']}", spinner="dots"):
        if t_type in {"file", "file_premium"}:
            try:
                response = get(get_info_endpoint(key), timeout=30)
                file_info = response.json().get("response", {}).get("file_info")
                if file_info and not is_junk_file(file_info["filename"]):
                    all_tasks.append((file_info, output_dir))
            except Exception as e:
                console.print(f"[bold error]{T['error_fetch_file']}:[/bold error] {e}")
        else:
            all_tasks = discover_all_files(key, output_dir)
    
    if not all_tasks:
        console.print(f"[bold warning]Warning:[/bold warning] {T['warning_no_files']}", style="warning")
        check_update(silent=True) # Check update even if no files
        return

    stats.total_files = len(all_tasks)
    stats.total_size = sum(int(t[0].get("size", 0)) for t in all_tasks)

    console.print(f"[bold success]{T['success_found']}:[/bold success] [highlight]{stats.total_files}[/highlight] {T['files_total_size']} [highlight]{format_size(stats.total_size)}[/highlight].\n")

    # --- Download Phase ---
    event = Event()
    limiter = BoundedSemaphore(args.threads)
    
    # Progress for Bytes (Total + Individual)
    p_bytes = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.0f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
        console=console,
        expand=True
    )

    # Progress for File Counts
    p_count = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.0f}%",
        "•",
        TextColumn("[bold blue]{task.completed}/{task.total}[/bold blue] " + T["files_count"].split()[0]),
        console=console,
        expand=True
    )

    ui_group = Group(
        Panel(p_count, title=f"[bold cyan]{T['files_count']}", border_style="cyan"),
        Panel(p_bytes, title=f"[bold magenta]{T['total_progress']}", border_style="magenta")
    )

    with Live(ui_group, console=console, refresh_per_second=10):
        overall_task = p_bytes.add_task(f"[bold]{T['total_progress']}", total=stats.total_size)
        file_count_task = p_count.add_task(f"[bold]{T['files_count']}", total=stats.total_files)

        def update_overall():
            p_bytes.update(overall_task, completed=stats.downloaded_bytes)
            p_count.update(file_count_task, completed=stats.downloaded_files, 
                          description=f"[bold]{T['files_count']} ({stats.downloaded_files}/{stats.total_files})")

        threads = []
        for file_info, destination in all_tasks:
            threads.append(Thread(target=download_file_worker, args=(file_info, destination, event, limiter, p_bytes, update_overall)))

        for t in threads:
            t.start()

        try:
            while any(t.is_alive() for t in threads):
                sleep(0.1)
        except KeyboardInterrupt:
            console.print(f"\n[bold warning]{T['stopping']}[/bold warning]")
            event.set()
            for t in threads:
                t.join()
            console.print(f"[bold error]{T['interrupted']}[/bold error]")
            print_summary()
            exit(0)
    
    # Auto-check update after successful run
    print_summary()
    check_update()

def print_summary():
    table = Table(title=T["summary_title"], box=box.ROUNDED, header_style="bold highlight", show_header=False)
    table.add_column("Property", style="dim")
    table.add_column("Value", justify="right")
    
    table.add_row(T["total_found"], str(stats.total_files))
    table.add_row(T["downloaded"], f"[success]{stats.downloaded_files}[/success]")
    table.add_row(T["skipped"], f"[warning]{stats.skipped}[/warning]")
    table.add_row(T["failed"], f"[error]{stats.failed}[/error]")
    table.add_row(T["total_size"], format_size(stats.total_size))
    table.add_row(T["downloaded_size"], format_size(stats.downloaded_bytes))

    console.print("\n")
    console.print(Panel(table, border_style="highlight", title=f"[bold]{T['done_title']}[/bold]", subtitle=f"{T['powered_by']} v{APP_VERSION}"))

def discover_all_files(folder_key, base_path):
    """Recursively discover all files in a folder."""
    try:
        r = get(get_files_or_folders_api_endpoint("folder", folder_key, info=True), timeout=30)
        r_json = r.json()
        if "folder_info" not in r_json.get("response", {}):
            return []
        
        # Determine current folder name relative to base_path
        current_folder_name = normalize_file_or_folder_name(r_json["response"]["folder_info"]["name"])
        current_path = path.join(base_path, current_folder_name)
    except Exception as e:
        console.print(f"[error]Error accessing folder {folder_key}:[/error] {e}")
        return []

    tasks = []

    # Get files in current folder
    chunk = 1
    more = True
    while more:
        try:
            res = get(get_files_or_folders_api_endpoint("files", folder_key, chunk=chunk), timeout=30).json()
            folder_content = res.get("response", {}).get("folder_content", {})
            for f in folder_content.get("files", []):
                if not is_junk_file(f["filename"]):
                    tasks.append((f, current_path))
                else:
                    with stats.lock:
                        stats.skipped += 1
            more = folder_content.get("more_chunks") == "yes"
            chunk += 1
        except Exception as e:
            console.print(f"[error]Error fetching files chunk {chunk}:[/error] {e}")
            break

    # Get subfolders
    chunk = 1
    more = True
    while more:
        try:
            res = get(get_files_or_folders_api_endpoint("folders", folder_key, chunk=chunk), timeout=30).json()
            folder_content = res.get("response", {}).get("folder_content", {})
            for sub in folder_content.get("folders", []):
                tasks.extend(discover_all_files(sub["folderkey"], current_path))
            more = folder_content.get("more_chunks") == "yes"
            chunk += 1
        except Exception as e:
            console.print(f"[error]Error fetching subfolders chunk {chunk}:[/error] {e}")
            break

    return tasks

def download_file_worker(file, output_dir, event, limiter, progress, update_cb):
    """Download a single file."""
    # Create a task for this specific file download (visible now)
    
    filename = normalize_file_or_folder_name(file["filename"])
    file_path = path.join(output_dir, filename)
    file_size = int(file.get("size", 0))

    limiter.acquire()
    
    task_id: TaskID = None

    try:
        # We ensure dir exists in main loop, but recursive structures might need this
        makedirs(output_dir, exist_ok=True)

        if path.exists(file_path):
            existing_hash = hash_file(file_path)
            if existing_hash == file.get("hash", ""):
                console.log(f"[dim]{T['skip_exists']}: {filename}[/dim]")
                with stats.lock:
                    stats.skipped += 1
                    stats.downloaded_files += 1
                    stats.downloaded_bytes += file_size
                update_cb()
                return

        if event.is_set():
            return

        # Show task now that we know we might download it
        task_id = progress.add_task(f"[cyan]{filename}[/cyan]", total=file_size, visible=True)

        download_link = file["links"]["normal_download"]
        
        # Step 1: Get the real download button/link
        response = get(download_link, headers=HEADERS, timeout=60)
        if response.status_code != 200:
             progress.console.log(f"[error]{T['http_err']} {response.status_code} for {filename}[/error]")
             with stats.lock: stats.failed += 1
             if task_id is not None: progress.remove_task(task_id)
             return

        html = response.text
        soup = Soup(html)
        download_btn = soup.find("a", {"id": "downloadButton"})
        real_link = None
        
        if download_btn and download_btn.attrs.get("href"):
            real_link = download_btn.attrs["href"]
        
        if not real_link and download_btn and download_btn.attrs.get("data-scrambled-url"):
            try:
                real_link = base64.b64decode(download_btn.attrs["data-scrambled-url"]).decode("utf-8")
            except Exception: pass
        
        if not real_link:
            # Fallback Strategy: Regex
            match = search(r'href=[\"\'](https?://download[^\"\']+)[\"\']', html)
            if match:
                real_link = match.group(1)

        if not real_link:
            progress.console.log(f"[error]{T['fail_link']} {filename}[/error]")
            with stats.lock: stats.failed += 1
            if task_id is not None: progress.remove_task(task_id)
            return

        # Step 2: Download the actual file
        res = get(real_link, headers=HEADERS, stream=True, timeout=60)
        if res.status_code != 200:
             progress.console.log(f"[error]{T['http_err']} {res.status_code} for {filename}[/error]")
             with stats.lock: stats.failed += 1
             if task_id is not None: progress.remove_task(task_id)
             return

        downloaded_for_this_file = 0
        with open(file_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=65536):
                if event.is_set():
                    break
                if chunk:
                    f.write(chunk)
                    chunk_len = len(chunk)
                    downloaded_for_this_file += chunk_len
                    with stats.lock:
                        stats.downloaded_bytes += chunk_len
                    progress.update(task_id, advance=chunk_len)
                    update_cb()

        # Remove task when done to keep the list clean
        if task_id is not None: 
            progress.remove_task(task_id)

        if event.is_set():
            if path.exists(file_path): remove(file_path)
            return

        # Verify if we actually got data
        if downloaded_for_this_file > 0:
            with stats.lock:
                stats.downloaded_files += 1
                save_to_history(filename, format_size(file_size))
            update_cb()
        else:
            progress.console.log(f"[error]{T['err_download']} {filename}: 0 bytes received[/error]")
            with stats.lock: stats.failed += 1
            if path.exists(file_path): remove(file_path)

    except Exception as e:
        console.log(f"[error]{T['err_download']} {filename}:[/error] {e}")
        with stats.lock: stats.failed += 1
        if task_id is not None: progress.remove_task(task_id)
    finally:
        limiter.release()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print(f"\n[error]{T['interrupted']}[/error]")
        exit(0)
