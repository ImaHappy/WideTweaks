"""The WideTweaks window, two columns like Flawless Widescreen: the supported games on the left (with a dot
for their state), the selected game on the right with its on/off switches. On patches the game for your resolution
(backup kept), off puts the original back. Opened by `widetweaks` with no arguments, which is also what
double-clicking WideTweaks.exe does.

Only code and the fix files come with WideTweaks: the game list is refreshed from the fix files on GitHub (so new
games arrive without a new WideTweaks), and pictures (Steam art, before/after shots) are downloaded when shown."""
import hashlib, io, json, os, pathlib, platform, re, subprocess, sys, threading, time, tkinter as tk, urllib.parse, urllib.request, webbrowser
import tkinter.font as tkfont
import widetweaks
try:                                    # optional: shows the game's Steam artwork (Tk alone can't show JPEG)
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    try:
        FONT = ImageFont.load_default(12)
    except TypeError:                   # Pillow < 10.1
        FONT = ImageFont.load_default()
except ImportError:
    Image = None

WIN = platform.system() == 'Windows'
UI = 'Segoe UI' if WIN else 'Noto Sans'
MONO = 'Consolas' if WIN else 'JetBrains Mono'
C = {'bg': '#0c0e11', 'card': '#14181d', 'pick': '#1b2128', 'line': '#232a31', 'text': '#e6edf3', 'muted': '#8b98a5',
     'faint': '#56636f', 'accent': '#4fc3d9', 'ok': '#6fcf97', 'warn': '#ffc23d', 'bad': '#e5484d', 'off': '#2b333b',
     'kofi': '#ff5e5b'}
REPO = f'https://github.com/{widetweaks.REPO}'
RELEASES = f'{REPO}/releases/latest'
API = f'https://api.github.com/repos/{widetweaks.REPO}'
RAW = f'https://raw.githubusercontent.com/{widetweaks.REPO}/main/'
FROZEN = getattr(sys, 'frozen', False)  # WideTweaks.exe (PyInstaller), not the Python files
CHECKOUT = (widetweaks.HERE / '.git').exists()   # a git checkout: its own fixes/ are the ones being worked on
SITE = 'https://imahappy.dev/widetweaks'
KOFI = 'https://ko-fi.com/imahappy'
SCALE = 1.25                            # the whole window 25% larger than Tk's default size
WIDTH = round(760 * SCALE)              # narrowest window (px); height follows the content
LIST_MAX = round(320 * SCALE)           # widest game list (px); longer names are cut short
ICON = round(18 * SCALE)                # list icon size (px)
STATES = {'missing': ('NOT INSTALLED', 'faint'), 'off': ('INSTALLED · ORIGINAL', 'muted'), 'on': ('PATCHED', 'ok'),
          'unsupported': ('UNSUPPORTED GAME VERSION', 'warn')}


class Switch(tk.Canvas):
    """A pill on/off switch. command(new_state) decides; the switch only shows what it's told (set())."""
    W, H = round(46 * SCALE), round(26 * SCALE)

    def __init__(self, parent, command, bg):
        super().__init__(parent, width=self.W, height=self.H, bg=bg, highlightthickness=0, cursor='hand2')
        self.command, self.on, self.enabled = command, False, True
        self.bind('<Button-1>', lambda e: self.enabled and self.command(not self.on))
        self.draw()

    def set(self, on, enabled=True):
        self.on, self.enabled = on, enabled
        self.configure(cursor='hand2' if enabled else 'arrow')
        self.draw()

    def draw(self):
        self.delete('all')
        r, fill = self.H // 2, (C['accent'] if self.on else C['off']) if self.enabled else C['line']
        self.create_oval(0, 0, self.H, self.H, fill=fill, outline=fill)
        self.create_oval(self.W - self.H, 0, self.W, self.H, fill=fill, outline=fill)
        self.create_rectangle(r, 0, self.W - r, self.H, fill=fill, outline=fill)
        x = self.W - r if self.on else r
        self.create_oval(x - r + 4, 4, x + r - 4, self.H - 4, fill=C['text'] if self.enabled else C['faint'], outline='')


class Tip:
    """A small popup with `text` beside a widget while the mouse is on it, drawn inside the window (a separate popup
    window is placed at random by some Linux window managers)."""
    def __init__(self, widget, text):
        self.widget, self.text, self.popup = widget, text, None
        widget.bind('<Enter>', lambda e: self.show())
        widget.bind('<Leave>', lambda e: self.hide())
        widget.bind('<Destroy>', lambda e: self.hide(), add='+')

    def show(self):
        if self.popup:
            return
        w = self.widget; root = w.winfo_toplevel()
        self.popup = p = tk.Frame(root, bg=C['accent'])
        tk.Label(p, text=self.text, font=(UI, 9), fg=C['text'], bg=C['bg'], justify='left', padx=10, pady=7,
                 wraplength=round(280 * SCALE)).pack(padx=1, pady=1)
        p.update_idletasks()
        # Below the widget (above it if there's no room), never over it: covering it would end the hover and flicker.
        x = w.winfo_rootx() - root.winfo_rootx() - 12
        x = max(8, min(x, root.winfo_width() - p.winfo_reqwidth() - 8))
        y = w.winfo_rooty() - root.winfo_rooty() + w.winfo_height() + 4
        if y + p.winfo_reqheight() > root.winfo_height() - 8:
            y = w.winfo_rooty() - root.winfo_rooty() - p.winfo_reqheight() - 4
        p.place(x=x, y=y); p.lift()

    def hide(self):
        if self.popup:
            self.popup.destroy(); self.popup = None


CACHE = pathlib.Path(os.environ.get('LOCALAPPDATA', '~/.cache')).expanduser() / ('WideTweaks' if WIN else 'widetweaks')


def download(url, max_age=None, offline=False):
    """The URL's bytes, kept on disk so the next start needs no network; refetched when older than max_age seconds
    (if the network fails, the old copy is used). offline: only the copy on disk, however old (OSError if none)."""
    path = CACHE / hashlib.sha1(url.encode()).hexdigest()
    if path.is_file() and (offline or max_age is None or time.time() - path.stat().st_mtime < max_age):
        return path.read_bytes()
    if offline:
        raise OSError(f'not downloaded yet: {url}')
    try:
        data = urllib.request.urlopen(url, timeout=10).read()
    except OSError:
        if path.is_file():
            return path.read_bytes()
        raise
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.{threading.get_ident()}.tmp')     # own name per thread: two downloads of one URL can't mix
    tmp.write_bytes(data); os.replace(tmp, path)
    return data


def link(parent, text, url, color, font, bg):
    """A clickable label opening url (or url(), for a link that changes)."""
    label = tk.Label(parent, text=text, font=font, fg=color, bg=bg, cursor='hand2')
    label.bind('<Button-1>', lambda e: webbrowser.open(url() if callable(url) else url))
    return label


def install_exe(data):
    """The new WideTweaks.exe in place of the running one (Windows lets a running .exe be renamed, not overwritten);
    the old one is left as .old and deleted at the next start."""
    exe = pathlib.Path(sys.executable)
    new, old = exe.with_name(exe.name + '.new'), exe.with_name(exe.name + '.old')
    new.write_bytes(data)
    old.unlink(missing_ok=True)
    os.replace(exe, old)
    try:
        os.replace(new, exe)
    except OSError:
        os.replace(old, exe); new.unlink(missing_ok=True)
        raise


ZIP_FILES = re.compile(r'(widetweaks(_app)?\.py|icon\.png|widetweaks\.desktop|README\.md|LICENSE|fixes/[\w.-]+\.json)')


def install_zip(data):
    """The Linux zip's files over this folder's: only WideTweaks' own names (anything else in the zip is ignored), each
    written aside first, then all swapped in."""
    import zipfile
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        files = {n: z.read(n) for n in z.namelist() if ZIP_FILES.fullmatch(n)}
    if 'widetweaks.py' not in files:
        raise ValueError('not a WideTweaks zip')
    for n, content in files.items():
        (widetweaks.HERE / (n + '.new')).parent.mkdir(exist_ok=True)
        (widetweaks.HERE / (n + '.new')).write_bytes(content)
    for n in files:
        os.replace(widetweaks.HERE / (n + '.new'), widetweaks.HERE / n)


def listing(folder, offline=False):
    """{file name: download URL} of a folder of the repo's main branch on GitHub (asked at most hourly). The URLs carry
    the file's hash, so a file is downloaded again only when it changed."""
    items = json.loads(download(f'{API}/contents/{folder}?ref=main', max_age=3600, offline=offline))
    return {i['name']: f"{RAW}{folder}/{i['name']}?{i['sha']}" for i in items if i['type'] == 'file'}


def load_fixes(offline=False):
    """{id: fix}: each game's fix file from GitHub, else the copy that came with WideTweaks (no network, GitHub down).
    A GitHub fix that needs a newer WideTweaks gives way to the bundled copy, if there is one; if not, it's kept and
    its game shows "Update WideTweaks". A git checkout uses only its own fixes/ (the ones being worked on)."""
    out = widetweaks.fixes()
    if CHECKOUT:
        return out
    try:
        files = listing('fixes', offline)
    except (OSError, ValueError, KeyError, TypeError):
        files = {}
    for name, url in files.items():
        gid = name.removesuffix('.json')
        if name.endswith('.json'):
            try:
                fix = json.loads(download(url, offline=offline))
            except (OSError, ValueError):
                continue
            if widetweaks.supported(fix) or gid not in out or not widetweaks.supported(out[gid]):
                out[gid] = fix
    return dict(sorted(out.items()))


class App:
    def __init__(self, root):
        self.root = root
        root.title('WideTweaks')
        try:                                    # window / taskbar icon (the .exe's own icon comes from icon.ico)
            self.icon = tk.PhotoImage(file=str(widetweaks.HERE / 'icon.png')); root.iconphoto(True, self.icon)
        except tk.TclError:
            pass
        root.tk.call('tk', 'scaling', root.tk.call('tk', 'scaling') * SCALE)   # fonts and point sizes
        root.configure(bg=C['bg'])

        # Header: name, tagline, links; then your resolution (the switches patch for whatever is here).
        head = tk.Frame(root, bg=C['bg']); head.pack(fill='x', padx=24, pady=(8, 0))
        name = tk.Label(head, text='WideTweaks', font=(UI, 20, 'bold'), fg=C['text'], bg=C['bg'], cursor='hand2')
        name.pack(side='left'); name.bind('<Button-1>', lambda e: self.show_start())    # back to the start screen
        tk.Label(head, text=widetweaks.VERSION, font=(UI, 9), fg=C['faint'], bg=C['bg']).pack(side='left', anchor='s', padx=6, pady=(0, 6))
        link(head, 'imahappy.dev', SITE, C['accent'], (UI, 10), C['bg']).pack(side='right', anchor='s', pady=(0, 4))
        sub = tk.Frame(root, bg=C['bg']); sub.pack(fill='x', padx=24, pady=(0, 16))
        tk.Label(sub, text="Happy's Ultrawide Fixes", font=(UI, 11), fg=C['muted'], bg=C['bg']).pack(side='left')
        self.aspect = tk.Label(sub, font=(UI, 10), fg=C['muted'], bg=C['bg']); self.aspect.pack(side='right')
        detected = widetweaks.screen_resolution()
        self.res = tk.StringVar(value='%dx%d' % detected if detected else '')
        tk.Entry(sub, textvariable=self.res, font=(UI, 12), width=11, justify='center', bg=C['card'], fg=C['text'],
                 insertbackground=C['text'], relief='flat', highlightthickness=1, highlightbackground=C['line'],
                 highlightcolor=C['accent']).pack(side='right', padx=10, ipady=3)
        tk.Label(sub, text='RESOLUTION', font=(MONO, 9), fg=C['faint'], bg=C['bg']).pack(side='right')
        self.res.trace_add('write', lambda *a: self.show_aspect()); self.show_aspect()
        # "WideTweaks X is out": a strip under the header, shown when GitHub has a newer release (never updates by itself).
        self.banner = tk.Frame(root, bg=C['pick'], highlightthickness=1, highlightbackground=C['accent'])
        self.banner_text = tk.Label(self.banner, font=(UI, 10), fg=C['text'], bg=C['pick'], anchor='w')
        self.banner_text.pack(side='left', padx=12, pady=6)
        self.banner_button = tk.Label(self.banner, font=(UI, 10, 'bold'), fg=C['bg'], bg=C['accent'], padx=12, pady=2, cursor='hand2')
        self.banner_button.pack(side='right', padx=8)
        self.banner_button.bind('<Button-1>', lambda e: self.update_app())
        link(self.banner, "What's new", lambda: self.release['html_url'], C['accent'], (UI, 9), C['pick']).pack(side='right', padx=8)
        self.release = None

        # Two columns: games | the selected game.
        body = tk.Frame(root, bg=C['bg']); body.pack(fill='both', expand=True, padx=24)
        left = tk.Frame(body, bg=C['card'], highlightthickness=1, highlightbackground=C['line'], width=round(250 * SCALE))
        left.pack(side='left', fill='y'); left.pack_propagate(False)
        self.query = tk.StringVar()
        search = tk.Entry(left, textvariable=self.query, font=(UI, 10), bg=C['bg'], fg=C['text'], insertbackground=C['text'],
                          relief='flat', highlightthickness=1, highlightbackground=C['line'], highlightcolor=C['accent'])
        search.pack(fill='x', padx=10, pady=10, ipady=4)
        hint = tk.Label(search, text='Search games', font=(UI, 10), fg=C['faint'], bg=C['bg'])
        hint.bind('<Button-1>', lambda e: search.focus_set())
        def update_hint(*a):
            hint.place(x=4, rely=.5, anchor='w') if not self.query.get() else hint.place_forget()
        self.query.trace_add('write', lambda *a: (update_hint(), self.filter())); update_hint()
        self.left = left
        self.list = tk.Frame(left, bg=C['card']); self.list.pack(fill='both', expand=True)
        self.blank = tk.PhotoImage(width=ICON, height=ICON)     # keeps names aligned before (or without) icons
        self.detail = tk.Frame(body, bg=C['card'], highlightthickness=1, highlightbackground=C['line'])
        self.detail.pack(side='left', fill='both', expand=True, padx=(10, 0))

        foot = tk.Frame(root, bg=C['bg']); foot.pack(side='bottom', fill='x', padx=24, pady=(12, 16), before=body)   # kept when the window is short
        tk.Label(foot, text='by ImaHappy', font=(UI, 9), fg=C['faint'], bg=C['bg']).pack(side='left')
        link(foot, 'GitHub', REPO, C['muted'], (UI, 9), C['bg']).pack(side='right')
        link(foot, '♥ Support me on Ko-fi', KOFI, C['kofi'], (UI, 9), C['bg']).pack(side='right', padx=(0, 14))

        self.selected, self.games, self.previews, self.width, self.fitting, self.asked = None, [], {}, WIDTH, False, None
        self.build_start()
        self.build_detail()
        self.build_list(load_fixes(offline=True))       # at once from what's on disk; GitHub's list follows (below)
        self.show_start()
        if FROZEN:                                      # left over by the last update (see update_app)
            try: pathlib.Path(sys.executable + '.old').unlink(missing_ok=True)
            except OSError: pass
        # Once Tk runs (threads hand their results over with root.after): the list from GitHub, update check.
        root.after(0, lambda: threading.Thread(target=self.fetch_online, daemon=True).start())

    def build_list(self, fixes):
        """The game list, one row per fix; built again when GitHub's fixes differ from the ones shown."""
        selected = self.selected and self.selected['gid']
        for w in self.list.winfo_children():
            w.destroy()
        # shortcut: a plain column of rows, no scrolling; make it scrollable once there are ~15+ games.
        old = {g['gid']: g for g in self.games}
        self.games = []
        for gid, fix in fixes.items():
            g = {'gid': gid, 'fix': fix, 'game': widetweaks.find_game(fix)}
            if gid in old and old[gid]['fix'] == fix:   # unchanged: keep what was loaded (states, art, icon)
                g.update({k: v for k, v in old[gid].items() if k in ('states', 'state', 'assets', 'art_raw', 'icon_data', 'shots')})
            g['row'] = tk.Frame(self.list, bg=C['card'], cursor='hand2'); g['row'].pack(fill='x')
            g['icon'] = tk.Label(g['row'], image=self.blank, bg=C['card']); g['icon'].pack(side='left', padx=(12, 8), pady=6)
            g['dot'] = tk.Label(g['row'], text='●', font=(UI, 8), bg=C['card'], fg=C['card']); g['dot'].pack(side='right', padx=12)
            g['name'] = tk.Label(g['row'], text=fix['name'], font=(UI, 10), bg=C['card'], fg=C['muted'], anchor='w')   # after the dot:
            g['name'].pack(side='left', fill='x', expand=True)                                                     # a long name can't push it
            for w in (g['row'], g['icon'], g['dot'], g['name']):
                w.bind('<Button-1>', lambda e, g=g: self.select(g))
            if 'icon_data' in g:
                self.set_icon(g, g['icon_data'])
            self.games.append(g)
        self.none = tk.Label(self.list, text='No match', font=(UI, 10), fg=C['faint'], bg=C['card'])
        # The list as wide as its longest game name, up to LIST_MAX (longer names end in "…"); the window grows by the same.
        left, base = self.left, round(250 * SCALE)
        left.config(width=base)
        self.list.update_idletasks()
        need = self.list.winfo_reqwidth()
        width = max(base, min(need, LIST_MAX))
        self.width = WIDTH + width - base; left.config(width=width)
        room = width - (need - max((g['name'].winfo_reqwidth() for g in self.games), default=0))    # minus icon, dot and padding
        font = tkfont.Font(font=(UI, 10))
        for g in self.games:
            name = g['fix']['name']
            while font.measure(name) > room:
                name = name[:-2] + '…'
            g['name'].config(text=name)
        self.filter()
        for g in self.games:
            if 'states' in g:
                self.refresh(g, recheck=False)
        self.selected = next((g for g in self.games if g['gid'] == selected), None)
        self.select(self.selected) if self.selected else self.show_start()
        threading.Thread(target=self.load_states, daemon=True).start()   # reading the games' files takes a moment (2 s for Dave)
        threading.Thread(target=self.fetch_icons, daemon=True).start()

    def fetch_online(self):
        """In the background: the fix files and before/after shots on GitHub, then whether a newer WideTweaks is out."""
        fixes = load_fixes()
        try:
            previews = {} if CHECKOUT else listing('fixes/previews')
        except (OSError, ValueError, KeyError, TypeError):
            previews = {}
        def show():
            self.previews = previews
            if [(g['gid'], g['fix']) for g in self.games] != list(fixes.items()):
                self.build_list(fixes)
            elif self.selected:
                self.select(self.selected)          # Compare buttons for shots that are only on GitHub
            else:
                self.show_start()
        self.root.after(0, show)
        try:
            release = json.loads(urllib.request.urlopen(f'{API}/releases/latest', timeout=10).read())
            if widetweaks.version(release['tag_name']) > widetweaks.version(widetweaks.VERSION):
                self.root.after(0, lambda: self.show_release(release))
        except (OSError, ValueError, KeyError):
            pass

    def show_release(self, release):
        self.release = release
        tag = release['tag_name'].lstrip('v')
        self.banner_text.configure(text=f'WideTweaks {tag} is out (you have {widetweaks.VERSION}).', fg=C['text'])
        self.banner_button.configure(text='Update now' if CHECKOUT or not FROZEN or WIN else 'Download')
        self.banner.pack(fill='x', padx=24, pady=(0, 12), before=self.detail.master)
        if self.selected:
            self.build_rows(self.selected); self.refresh(self.selected, recheck=False)
        self.fit_later()

    def update_app(self):
        """The user asked for the new version; nothing changes before they click. WideTweaks.exe (Windows) and the Linux
        zip: download the release's file, check its SHA-256 against the one GitHub lists for it, put it in place and
        restart. A git checkout: git pull (fast-forward only) and restart."""
        if not self.release:
            return webbrowser.open(RELEASES)
        how = 'git' if CHECKOUT else 'exe' if WIN and FROZEN else 'zip' if not FROZEN else None
        name = {'exe': 'WideTweaks.exe', 'zip': 'WideTweaks_Linux.zip'}.get(how)
        asset = next((a for a in self.release.get('assets', []) if a['name'] == name), None)
        if not how or (name and not (asset and str(asset.get('digest', '')).startswith('sha256:'))):
            return webbrowser.open(self.release['html_url'])
        self.banner_text.configure(text='Updating WideTweaks…')
        self.banner_button.pack_forget()
        def work():
            try:
                if how == 'git':
                    out = subprocess.run(['git', '-C', str(widetweaks.HERE), 'pull', '--ff-only'], capture_output=True,
                                         text=True, timeout=120)
                    if out.returncode:
                        raise ValueError((out.stderr.strip() or 'git pull failed').splitlines()[-1])
                else:
                    data = urllib.request.urlopen(asset['browser_download_url'], timeout=120).read()
                    if hashlib.sha256(data).hexdigest() != asset['digest'].split(':', 1)[1].lower():
                        raise ValueError("the download doesn't match the release's SHA-256: not installed")
                    (install_exe if how == 'exe' else install_zip)(data)
                self.root.after(0, self.restart)
            except (OSError, ValueError, subprocess.SubprocessError) as e:
                self.root.after(0, lambda: (self.banner_text.configure(text=f'Update failed: {e}', fg=C['bad']),
                                            self.banner_button.configure(text='Download'),
                                            self.banner_button.pack(side='right', padx=8)))
                self.release = {**self.release, 'assets': []}      # next click: the release page
        threading.Thread(target=work, daemon=True).start()

    def restart(self):
        """Start the updated WideTweaks, then close this one."""
        if FROZEN:      # a fresh start for the new .exe (PyInstaller: don't reuse this process's unpacked files)
            subprocess.Popen([sys.executable], env={**os.environ, 'PYINSTALLER_RESET_ENVIRONMENT': '1'}, close_fds=True)
        else:
            subprocess.Popen([sys.executable, str(widetweaks.HERE / 'widetweaks.py')], start_new_session=True)
        self.root.destroy()

    def load_states(self):
        games = list(self.games)
        for g in games:
            g['states'] = (widetweaks.states(g['fix'], g['game']) if widetweaks.supported(g['fix'])
                           else {t: 'unsupported' for t in widetweaks.toggles(g['fix'])})
        self.root.after(0, lambda: self.show_states(games))

    def show_states(self, games):
        for g in games:
            if g in self.games:
                self.refresh(g, recheck=False)
        if not self.selected:
            self.show_start()

    def build_start(self):
        """The start screen in the right column, before a game is picked: what WideTweaks is, how many of its games are
        installed here, and where to begin."""
        s = self.start = tk.Frame(self.detail, bg=C['card'])
        inner = tk.Frame(s, bg=C['card']); inner.pack(expand=True, fill='both', padx=32, pady=32)
        try:
            self.logo = tk.PhotoImage(file=str(widetweaks.HERE / 'icon.png')).subsample(2)
            tk.Label(inner, image=self.logo, bg=C['card']).pack(anchor='w', pady=(0, 12))
        except tk.TclError:
            pass
        tk.Label(inner, text='Ultrawide fixes, one switch each', font=(UI, 16, 'bold'), fg=C['text'], bg=C['card'],
                 anchor='w').pack(fill='x')
        self.start_text = tk.Label(inner, font=(UI, 10), fg=C['muted'], bg=C['card'], anchor='w', justify='left',
                                   wraplength=round(420 * SCALE))
        self.start_text.pack(fill='x', pady=(8, 0))
        self.start_installed = tk.Frame(inner, bg=C['card']); self.start_installed.pack(fill='x', pady=(16, 0))
        tk.Label(inner, text='Every fix keeps the original files next to the game: switch it off and they are back.',
                 font=(UI, 9), fg=C['faint'], bg=C['card'], anchor='w', justify='left',
                 wraplength=round(420 * SCALE)).pack(fill='x', pady=(20, 0))

    def show_start(self):
        """The start screen (also what shows when none of the games is installed)."""
        self.selected = None
        for g in self.games:
            for w in (g['row'], g['icon'], g['dot'], g['name']):
                w.configure(bg=C['card'])
            g['name'].configure(fg=C['muted'])
        self.page.pack_forget(); self.compare(None)
        self.start.pack(fill='both', expand=True)
        installed = [g for g in self.games if g['game']]
        n = len(self.games)
        if installed:
            text = (f'{n} games supported, {len(installed)} installed on this PC. Pick one on the left (or below) to see '
                    'what its fix changes, then flip the switches you want.')
        else:
            text = (f"{n} games supported, none of them installed on this PC yet. Install one through Steam and it "
                    'shows up here, ready to patch. (A copy outside Steam: the command line takes --path.)')
        self.start_text.configure(text=text)
        for w in self.start_installed.winfo_children():
            w.destroy()
        for g in installed:
            row = tk.Label(self.start_installed, text=f"→  {g['fix']['name']}", font=(UI, 10), fg=C['accent'],
                           bg=C['card'], anchor='w', cursor='hand2')
            row.pack(fill='x', pady=1); row.bind('<Button-1>', lambda e, g=g: self.select(g))
        self.fit_later()

    def build_detail(self):
        d = self.page = tk.Frame(self.detail, bg=C['card'])
        self.art = tk.Label(d, bg=C['bg'], height=0)            # the game's Steam header image, when loaded
        self.art.pack(fill='x')
        bar = tk.Frame(d, bg=C['card']); bar.pack(fill='x', padx=20, pady=(16, 2))
        self.title = tk.Label(bar, font=(UI, 16, 'bold'), fg=C['text'], bg=C['card'], anchor='w', justify='left',
                              wraplength=round(330 * SCALE))     # a long name wraps beside "Play"
        self.title.pack(side='left', fill='x', expand=True)
        # "Play": starts the game through Steam, right of the title under the picture (installed games only).
        self.play = tk.Label(bar, text='▶  Play', font=(UI, 10, 'bold'), fg=C['bg'], bg=C['accent'], padx=14, pady=4,
                             cursor='hand2')
        self.play.bind('<Button-1>', lambda e: webbrowser.open(f"steam://rungameid/{self.selected['fix']['steam_appid']}"))
        self.summary = tk.Label(d, font=(UI, 10), fg=C['muted'], bg=C['card'], anchor='w', justify='left', wraplength=round(420 * SCALE))
        self.summary.pack(fill='x', padx=20)
        # A step to do in Steam first (e.g. switch to a beta branch), with a button copying its code; when the fix has one.
        self.setup = tk.Frame(d, bg=C['pick'], highlightthickness=1, highlightbackground=C['warn'])
        self.setup_text = tk.Label(self.setup, font=(UI, 9), fg=C['text'], bg=C['pick'], anchor='w', justify='left',
                                   wraplength=round(320 * SCALE))
        self.setup_text.pack(side='left', fill='x', expand=True, padx=(12, 8), pady=8)
        self.setup_copy = tk.Label(self.setup, font=(MONO, 9), fg=C['text'], bg=C['card'], padx=10, pady=4, cursor='hand2',
                                   highlightthickness=1, highlightbackground=C['line'])
        self.setup_copy.pack(side='right', padx=(0, 12))
        self.setup_copy.bind('<Button-1>', lambda e: self.copy_setup())
        # One strip per switch of the game (built when it's picked): switch, name, what it does, state, "Compare".
        self.rows = tk.Frame(d, bg=C['card']); self.rows.pack(fill='x', padx=20, pady=(18, 0))
        self.switches, self.compare_buttons, self.comparing = {}, {}, None
        self.detail.bind('<Configure>', lambda e: self.fit_art())
        self.art.bind('<Motion>', lambda e: self.comparing and self.draw_compare(e.y))
        # Details (tested with, where the game is, how the fix works), folded away until clicked.
        self.more = tk.Label(d, text='Details ▸', font=(UI, 9), fg=C['faint'], bg=C['card'], anchor='w', cursor='hand2')
        self.more.pack(fill='x', padx=20, pady=(12, 16))
        self.more.bind('<Button-1>', lambda e: self.show_details(not self.details_open))
        self.details = tk.Frame(d, bg=C['card'])
        self.details_text = tk.Label(self.details, font=(UI, 9), fg=C['muted'], bg=C['card'], anchor='w', justify='left',
                                     wraplength=round(420 * SCALE))
        self.details_text.pack(fill='x')
        link(self.details, 'How the fix works (GitHub) ↗', lambda: f"{REPO}/blob/main/docs/fixes/{self.selected['gid']}.md",
             C['accent'], (UI, 9), C['card']).pack(anchor='w', pady=(6, 0))
        self.details_open = False

    def copy_setup(self):
        """The setup step's code to the clipboard; the button says so for a moment."""
        self.root.clipboard_clear(); self.root.clipboard_append(self.selected['fix']['setup']['copy'])
        self.setup_copy.configure(text=f"{self.selected['fix']['setup']['copy']}   ✓ Copied", fg=C['ok'])
        self.root.after(1500, lambda: self.selected and 'setup' in self.selected['fix'] and
                        self.setup_copy.configure(text=f"{self.selected['fix']['setup']['copy']}   ⧉ Copy", fg=C['text']))

    def show_art(self, g):
        """The game's Steam header image across the top of the right column, fetched once in the background."""
        if not Image:
            return
        if 'art_raw' in g:
            return self.fit_art()
        self.art.configure(image='')
        def fetch():
            try:
                a = self.assets(g)
                data = download('https://shared.fastly.steamstatic.com/store_item_assets/' + a['asset_url_format'].replace('${FILENAME}', a['header']))
            except Exception:
                data = None
            self.root.after(0, lambda: self.set_art(g, data))
        threading.Thread(target=fetch, daemon=True).start()

    def load_previews(self, g):
        """Which switches have before/after shots, fixes/previews/<id>-<switch>-before.jpg and -after.jpg (the first
        switch may drop "<switch>-"): in the folder next to WideTweaks (a checkout), else on GitHub. A switch with both
        gets a Compare button; the shots themselves are downloaded when it's clicked."""
        g['previews'] = {}
        local = widetweaks.FIXES / 'previews'
        for i, name in enumerate(widetweaks.toggles(g['fix'])):
            for stem in [f"{g['gid']}-{name.lower().replace(' ', '-')}"] + ([g['gid']] if i == 0 else []):
                files = [f'{stem}-{n}.jpg' for n in ('before', 'after')]
                if Image and all((local / f).is_file() for f in files):
                    g['previews'][name] = [local / f for f in files]; break
                if Image and all(f in self.previews for f in files):
                    g['previews'][name] = [self.previews[f] for f in files]; break
        self.compare(None)

    def shots(self, g, name, then):
        """The before/after pictures of switch `name` (opened or downloaded in the background), then then()."""
        g.setdefault('shots', {})
        if name in g['shots']:
            return then()
        self.compare_buttons[name].configure(text='…  Loading')
        def fetch():
            try:
                g['shots'][name] = [Image.open(src if isinstance(src, pathlib.Path) else io.BytesIO(download(src))).convert('RGB')
                                    for src in g['previews'][name]]
                self.root.after(0, lambda: g is self.selected and then())
            except (OSError, ValueError):
                self.root.after(0, lambda: g is self.selected and name in self.compare_buttons and
                                self.compare_buttons[name].configure(text='✕  No connection'))
        threading.Thread(target=fetch, daemon=True).start()

    def build_rows(self, g):
        """A strip per switch: the switch, its name and state; clicking anywhere on the strip flips it."""
        for w in self.rows.winfo_children():
            w.destroy()
        self.switches, self.compare_buttons = {}, {}
        if not widetweaks.supported(g['fix']):     # a fix from GitHub that uses what this WideTweaks doesn't have yet
            row = tk.Frame(self.rows, bg=C['pick'], highlightthickness=1, highlightbackground=C['warn']); row.pack(fill='x')
            tk.Label(row, text=f"This fix needs WideTweaks {g['fix']['requires']} or newer (you have {widetweaks.VERSION}).",
                     font=(UI, 10), fg=C['text'], bg=C['pick'], anchor='w', justify='left',
                     wraplength=round(300 * SCALE)).pack(side='left', fill='x', expand=True, padx=14, pady=10)
            button = tk.Label(row, text='Update WideTweaks', font=(UI, 10, 'bold'), fg=C['bg'], bg=C['accent'], padx=12,
                              pady=3, cursor='hand2')
            button.pack(side='right', padx=12); button.bind('<Button-1>', lambda e: self.update_app())
            return
        for i, name in enumerate(widetweaks.toggles(g['fix'])):
            row = tk.Frame(self.rows, bg=C['pick'], highlightthickness=1, highlightbackground=C['line'])
            row.pack(fill='x', pady=(6 if i else 0, 0))
            switch = Switch(row, lambda on, n=name: self.toggle(self.selected, n, on), C['pick'])
            switch.pack(side='left', padx=(14, 12), pady=10)
            text = tk.Frame(row, bg=C['pick']); text.pack(side='left', fill='x', expand=True)
            top = tk.Frame(text, bg=C['pick']); top.pack(fill='x')
            label = tk.Label(top, text=name, font=(UI, 11, 'bold'), fg=C['text'], bg=C['pick'], anchor='w'); label.pack(side='left')
            about = widetweaks.switch_text(g['fix'], name)
            if about:                           # "ⓘ": what the switch changes, in plain words, shown while hovered
                info = tk.Label(top, text='ⓘ', font=(UI, 11), fg=C['faint'], bg=C['pick'], cursor='question_arrow')
                info.pack(side='left', padx=(6, 0)); Tip(info, about)
            state = tk.Label(text, font=(MONO, 8), bg=C['pick'], anchor='w', justify='left', wraplength=round(330 * SCALE)); state.pack(fill='x')
            for w in (row, text, top, label, state):
                w.configure(cursor='hand2'); w.bind('<Button-1>', lambda e, s=switch: s.event_generate('<Button-1>'))
            self.switches[name] = (switch, state)
            if name in g.get('previews', {}):   # "Compare": the picture on top becomes original (above) vs fixed (below)
                button = tk.Label(row, text='◐  Compare', font=(UI, 9), fg=C['accent'], bg=C['card'], cursor='hand2',
                                  padx=10, pady=3, highlightthickness=1, highlightbackground=C['line'])
                button.bind('<Button-1>', lambda e, n=name: self.compare(None) if self.comparing == n else
                            self.shots(self.selected, n, lambda: self.compare(n)))
                button.pack(side='right', padx=(0, 12))
                self.compare_buttons[name] = button

    def compare(self, name):
        """Show the comparison of switch `name` in the picture area (None: the game's picture again)."""
        self.comparing = name if self.selected and name in self.selected.get('shots', {}) else None
        for n, button in self.compare_buttons.items():
            button.configure(fg=C['bg'] if n == self.comparing else C['accent'], bg=C['accent'] if n == self.comparing else C['card'],
                             text='✕  Close' if n == self.comparing else '◐  Compare')
        self.art.configure(cursor='sb_v_double_arrow' if self.comparing else '')
        if self.comparing:
            self.draw_compare(None)
        else:
            self.art.configure(image='')
            self.fit_art()

    def draw_compare(self, y):
        """Original above y, fixed below it (so both sides' bars show at once), with a divider and labels."""
        before, after = self.selected['shots'][self.comparing]
        w = max(1, self.detail.winfo_width() - 2)
        if self.selected.get('compare_size') != (self.comparing, w):    # scaled to the column once, reused while moving
            self.selected['compare_size'] = (self.comparing, w)
            self.selected['compare'] = [im.resize((w, round(im.height * w / im.width)), Image.LANCZOS) for im in (before, after)]
        b, a = self.selected['compare']
        art = self.selected.get('art')
        top = (art.height() - a.height) // 2 if art and art.height() > a.height else 0   # padding, so nothing jumps
        y = a.height // 2 if y is None else max(0, min(a.height, y - top))
        out = a.copy(); out.paste(b.crop((0, 0, w, y)), (0, 0))
        d = ImageDraw.Draw(out)
        x = w // 2
        d.rectangle((0, y - 4, w, y + 3), fill=C['bg'])                  # dark edges, so the line shows on any picture
        d.rectangle((0, y - 2, w, y + 1), fill=C['accent'])
        d.ellipse((x - 17, y - 17, x + 17, y + 17), fill=C['bg'])
        d.ellipse((x - 15, y - 15, x + 15, y + 15), fill=C['accent'])
        d.polygon(((x, y - 10), (x - 7, y - 3), (x + 7, y - 3)), fill=C['bg'])
        d.polygon(((x, y + 10), (x - 7, y + 3), (x + 7, y + 3)), fill=C['bg'])
        # Small see-through labels riding on the line (original above, fixed below), so they cover little.
        tags = Image.new('RGBA', out.size); t = ImageDraw.Draw(tags)
        for text, y0 in (('ORIGINAL', y - 25), ('WIDETWEAKS', y + 6)):
            tw = t.textlength(text, font=FONT)
            t.rounded_rectangle((10, y0, 10 + tw + 12, y0 + 19), 4, fill=(12, 14, 17, 150))
            t.text((16, y0 + 10), text, font=FONT, fill=C['text'], anchor='lm')
        out = Image.alpha_composite(out.convert('RGBA'), tags).convert('RGB')
        if top:
            framed = Image.new('RGB', (w, art.height()), C['bg']); framed.paste(out, (0, top))
            out = framed
        self.compare_image = ImageTk.PhotoImage(out)
        self.art.configure(image=self.compare_image)

    def assets(self, g):
        """The game's Steam store image names (asked once per game, shared by the icon and the header)."""
        if 'assets' not in g:
            q = {'ids': [{'appid': g['fix']['steam_appid']}], 'context': {'language': 'english', 'country_code': 'US'},
                 'data_request': {'include_assets': True}}
            url = 'https://api.steampowered.com/IStoreBrowseService/GetItems/v1/?' + urllib.parse.urlencode({'input_json': json.dumps(q)})
            g['assets'] = json.loads(download(url, max_age=7 * 86400))['response']['store_items'][0]['assets']   # new art within a week
        return g['assets']

    def fetch_icons(self):
        """The small Steam icon (32 px) next to each game in the list, in the background."""
        if not Image:
            return
        for g in list(self.games):
            if 'icon_data' in g:
                continue
            try:
                a = self.assets(g)
                data = download(f"https://cdn.fastly.steamstatic.com/steamcommunity/public/images/apps/{g['fix']['steam_appid']}/{a['community_icon']}.jpg")
            except Exception:
                continue
            self.root.after(0, lambda g=g, data=data: self.set_icon(g, data))

    def set_icon(self, g, data):
        g['icon_data'] = data
        if g not in self.games:                     # the list was built again meanwhile
            return
        g['icon_image'] = ImageTk.PhotoImage(Image.open(io.BytesIO(data)).resize((ICON, ICON), Image.LANCZOS))
        g['icon'].configure(image=g['icon_image'])

    def filter(self):
        """Show only the games whose name contains the search text."""
        q = self.query.get().strip().lower()
        shown = 0
        for g in self.games:
            g['row'].pack_forget()
        for g in self.games:
            if q in g['fix']['name'].lower():
                g['row'].pack(fill='x'); shown += 1
        self.none.pack(pady=12) if not shown else self.none.pack_forget()

    def set_art(self, g, data):
        if data:                                    # a failed download is tried again next time the game is picked
            g['art_raw'] = Image.open(io.BytesIO(data)); g['art_raw'].load()
        if g is self.selected:
            self.fit_art()

    def fit_art(self):
        """The selected game's picture at the right column's current width (again whenever the window resizes)."""
        g, w = self.selected, self.detail.winfo_width() - 2
        if not g or 'art_raw' not in g or w < 50:   # not laid out yet: the <Configure> that follows draws it
            self.fit_later()
            return
        if g.get('art_width') != w:
            im = g['art_raw']
            g['art'], g['art_width'] = ImageTk.PhotoImage(im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)), w
        if self.comparing:
            self.draw_compare(None)
        else:
            self.art.configure(image=g['art'])
        self.fit_later()

    def fit_later(self):
        """fit_window shortly, once the layout has settled; asked many times in a row, it still runs once."""
        if not self.fitting:
            self.fitting = True
            self.root.after(30, self.fit_window)

    def fit_window(self):
        """The window never shorter than what it shows: picture, every switch, Details (grows if it must). Width stays
        free above WIDTH: the picture follows the width, so the width can't follow the picture. Each height is asked of
        the window manager once: one that keeps the window smaller (Hyprland with Wine does) must not start a loop."""
        self.fitting = False
        h = self.root.winfo_reqheight()
        if self.root.minsize() != (self.width, h):
            self.root.minsize(self.width, h)
        if self.root.winfo_height() < h and self.asked != h:
            self.asked = h
            self.root.geometry(f'{max(self.root.winfo_width(), self.width)}x{h}')

    def show_details(self, open_):
        self.details_open = open_
        self.more.configure(text='Details ▾' if open_ else 'Details ▸')
        self.fit_later()
        if open_:
            self.details.pack(fill='x', padx=20, pady=(0, 16), after=self.more)
        else:
            self.details.pack_forget()

    def resolution(self):
        return widetweaks.parse_resolution(self.res.get())

    def show_aspect(self):
        r = self.resolution()
        self.aspect.configure(text=f'{r[0] / r[1] * 9:.1f}:9 · {r[0] / r[1]:.2f}' if r else 'e.g. 3440x1440',
                              fg=C['muted'] if r else C['faint'])

    def select(self, g):
        self.selected = g
        self.start.pack_forget(); self.page.pack(fill='both', expand=True)
        self.play.pack(side='right') if g['game'] else self.play.pack_forget()
        for o in self.games:
            bg = C['pick'] if o is g else C['card']
            for w in (o['row'], o['icon'], o['dot'], o['name']):
                w.configure(bg=bg)
            o['name'].configure(fg=C['text'] if o is g else C['muted'])
        f = g['fix']
        self.title.configure(text=f['name'])
        self.summary.configure(text=f['summary'])
        where = str(g['game'] / f['exe']) if g['game'] else f"Steam app {f['steam_appid']}, not found in your Steam libraries"
        self.details_text.configure(text=f"Tested: {f['tested']}\nNeeds WideTweaks {f.get('requires', '0.1.0')} or newer\n{where}")
        if 'setup' in f:                            # a step in Steam first, e.g. a beta branch and its code
            self.setup_text.configure(text=f['setup']['text'])
            self.setup_copy.configure(text=f"{f['setup']['copy']}   ⧉ Copy", fg=C['text'])
            self.setup.pack(fill='x', padx=20, pady=(12, 0), before=self.rows)
        else:
            self.setup.pack_forget()
        self.show_art(g)
        self.load_previews(g)
        self.build_rows(g)
        self.refresh(g, recheck=False)
        self.fit_later()

    def refresh(self, g, message=None, color=None, which=None, recheck=True):
        """Show the game's switches; recheck reads its files again (at start and after a change, not on every click)."""
        if recheck:
            g['states'] = widetweaks.states(g['fix'], g['game'])
        if 'states' not in g:                       # the start-up check is still reading the files: it refreshes later
            for switch, label in self.switches.values() if g is self.selected else ():
                label.configure(text='CHECKING…', fg=C['faint']); switch.set(False, enabled=False)
            return
        states = g['states']
        g['state'] = widetweaks.overall(states)
        g['dot'].configure(fg=C[STATES[g['state']][1]])
        if g is self.selected:
            for name, (switch, label) in self.switches.items():
                text, tone = STATES[states[name]]
                own = message and which in (name, None)
                label.configure(text=message if own else text, fg=(color or C[tone]) if own else C[tone])
                switch.set(states[name] == 'on', enabled=states[name] in ('on', 'off'))
            self.fit_later()

    def toggle(self, g, name, on):
        """Flip one switch: the game's files are rebuilt from the originals with the switches now on."""
        r = self.resolution()
        if not r:
            return self.refresh(g, 'ENTER YOUR RESOLUTION FIRST, E.G. 3440X1440', C['warn'], name)
        now = {t for t, s in g['states'].items() if s == 'on'}
        try:
            widetweaks.setup(g['fix'], g['game'], *r, now | {name} if on else now - {name})
            self.refresh(g, f'PATCHED FOR {r[0]}×{r[1]}' if on else None, C['ok'], name)
        except (ValueError, OSError) as e:          # e.g. game running, unknown version
            self.refresh(g, str(e).upper()[:160], C['bad'], name)


def run():
    root = tk.Tk(className='WideTweaks')     # window class (Tk makes it "Widetweaks"): Linux taskbars find the icon by it, see widetweaks.desktop
    App(root)
    root.mainloop()


if __name__ == '__main__':
    run()
