"""The WideTweaks window, two columns like Flawless Widescreen: the supported games on the left (with a dot
for their state), the selected game on the right with its on/off switch. On patches the game for your resolution
(backup kept), off puts the original back. Opened by `widetweaks` with no arguments, which is also what
double-clicking WideTweaks.exe does."""
import hashlib, json, os, pathlib, platform, threading, time, tkinter as tk, urllib.parse, urllib.request, webbrowser
import widetweaks
try:                                    # optional: shows the game's Steam artwork (Tk alone can't show JPEG)
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    import io
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
REPO = 'https://github.com/ImaHappy/WideTweaks'
SITE = 'https://imahappy.dev/widetweaks'
KOFI = 'https://ko-fi.com/imahappy'
SCALE = 1.25                            # the whole window 25% larger than Tk's default size
WIDTH = round(760 * SCALE)              # narrowest window (px); height follows the content
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


CACHE = pathlib.Path(os.environ.get('LOCALAPPDATA', '~/.cache')).expanduser() / ('WideTweaks' if WIN else 'widetweaks')


def download(url, max_age=None):
    """The URL's bytes, kept on disk so the next start needs no network; refetched when older than max_age seconds
    (if the network fails, the old copy is used)."""
    path = CACHE / hashlib.sha1(url.encode()).hexdigest()
    if path.is_file() and (max_age is None or time.time() - path.stat().st_mtime < max_age):
        return path.read_bytes()
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
    label = tk.Label(parent, text=text, font=font, fg=color, bg=bg, cursor='hand2')
    label.bind('<Button-1>', lambda e: webbrowser.open(url))
    return label


class App:
    def __init__(self, root):
        self.root = root
        root.title('WideTweaks')
        root.tk.call('tk', 'scaling', root.tk.call('tk', 'scaling') * SCALE)   # fonts and point sizes
        root.configure(bg=C['bg'])

        # Header: name, tagline, links; then your resolution (the switches patch for whatever is here).
        head = tk.Frame(root, bg=C['bg']); head.pack(fill='x', padx=24, pady=(8, 0))
        tk.Label(head, text='WideTweaks', font=(UI, 20, 'bold'), fg=C['text'], bg=C['bg']).pack(side='left')
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
        self.list = tk.Frame(left, bg=C['card']); self.list.pack(fill='both', expand=True)
        self.blank = tk.PhotoImage(width=ICON, height=ICON)     # keeps names aligned before (or without) icons
        self.detail = tk.Frame(body, bg=C['card'], highlightthickness=1, highlightbackground=C['line'])
        self.detail.pack(side='left', fill='both', expand=True, padx=(10, 0))

        # shortcut: a plain column of rows, no scrolling; make it scrollable once there are ~15+ games.
        self.games = []
        for gid, fix in widetweaks.fixes().items():
            g = {'gid': gid, 'fix': fix, 'game': widetweaks.find_game(fix)}
            g['row'] = tk.Frame(self.list, bg=C['card'], cursor='hand2'); g['row'].pack(fill='x')
            g['icon'] = tk.Label(g['row'], image=self.blank, bg=C['card']); g['icon'].pack(side='left', padx=(12, 8), pady=6)
            g['name'] = tk.Label(g['row'], text=fix['name'], font=(UI, 10), bg=C['card'], anchor='w')
            g['name'].pack(side='left', fill='x', expand=True)
            g['dot'] = tk.Label(g['row'], text='●', font=(UI, 8), bg=C['card']); g['dot'].pack(side='right', padx=12)
            for w in (g['row'], g['icon'], g['dot'], g['name']):
                w.bind('<Button-1>', lambda e, g=g: self.select(g))
            self.games.append(g)

        foot = tk.Frame(root, bg=C['bg']); foot.pack(side='bottom', fill='x', padx=24, pady=(12, 16), before=body)   # kept when the window is short
        tk.Label(foot, text='by ImaHappy', font=(UI, 9), fg=C['faint'], bg=C['bg']).pack(side='left')
        link(foot, 'GitHub', REPO, C['muted'], (UI, 9), C['bg']).pack(side='right')
        link(foot, '♥ Support me on Ko-fi', KOFI, C['kofi'], (UI, 9), C['bg']).pack(side='right', padx=(0, 14))

        self.none = tk.Label(self.list, text='No match', font=(UI, 10), fg=C['faint'], bg=C['card'])
        self.selected = None
        self.build_detail()
        root.after(0, lambda: threading.Thread(target=self.fetch_icons, daemon=True).start())   # once Tk runs: threads call root.after
        # Reading the games' files takes a moment (about 2 s for Dave): in the background, then pick the first game.
        root.after(0, lambda: threading.Thread(target=self.load_states, daemon=True).start())
        if self.games:          # shown at once (switches "checking"), so the window has its size from the start
            root.after(0, lambda: self.select(self.games[0]))

    def load_states(self):
        for g in self.games:
            g['states'] = widetweaks.states(g['fix'], g['game'])
        self.root.after(0, self.show_states)

    def show_states(self):
        for g in self.games:
            self.refresh(g, recheck=False)
        if self.selected and self.selected['state'] == 'missing':     # the first game isn't installed: an installed one
            self.select(next((g for g in self.games if g['state'] != 'missing'), self.selected))

    def build_detail(self):
        d = self.detail
        self.art = tk.Label(d, bg=C['bg'], height=0)            # the game's Steam header image, when loaded
        self.art.pack(fill='x')
        bar = tk.Frame(d, bg=C['card']); bar.pack(fill='x', padx=20, pady=(16, 2))
        self.title = tk.Label(bar, font=(UI, 16, 'bold'), fg=C['text'], bg=C['card'], anchor='w')
        self.title.pack(side='left', fill='x', expand=True)
        # "Play": starts the game through Steam, right of the title under the picture (installed games only).
        self.play = tk.Label(bar, text='▶  Play', font=(UI, 10, 'bold'), fg=C['bg'], bg=C['accent'], padx=14, pady=4,
                             cursor='hand2')
        self.play.bind('<Button-1>', lambda e: webbrowser.open(f"steam://rungameid/{self.selected['fix']['steam_appid']}"))
        self.summary = tk.Label(d, font=(UI, 10), fg=C['muted'], bg=C['card'], anchor='w', justify='left', wraplength=round(420 * SCALE))
        self.summary.pack(fill='x', padx=20)
        # The switch with its label and state beside it, on a slightly raised strip.
        # One switch strip per toggle of the game (built when it's picked); "Compare" sits on the first.
        self.rows = tk.Frame(d, bg=C['card']); self.rows.pack(fill='x', padx=20, pady=(18, 0))
        self.switches, self.compare_buttons, self.comparing = {}, {}, None
        self.detail.bind('<Configure>', lambda e: self.fit_art())
        self.art.bind('<Motion>', lambda e: self.comparing and self.draw_compare(e.y))
        # Details (how the fix works, where the game is), folded away until clicked.
        self.more = tk.Label(d, text='Details ▸', font=(UI, 9), fg=C['faint'], bg=C['card'], anchor='w', cursor='hand2')
        self.more.pack(fill='x', padx=20, pady=(12, 16))
        self.more.bind('<Button-1>', lambda e: self.show_details(not self.details_open))
        self.details = tk.Label(d, font=(UI, 9), fg=C['muted'], bg=C['card'], anchor='w', justify='left', wraplength=round(420 * SCALE))
        self.details_open = False

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
        """fixes/previews/<id>-<switch>-before.jpg and -after.jpg per switch (the first switch may drop "<switch>-");
        a switch with both gets a Compare button."""
        if 'previews' not in g:
            g['previews'] = {}
            for i, name in enumerate(widetweaks.toggles(g['fix'])):
                for stem in [f"{g['gid']}-{name.lower().replace(' ', '-')}"] + ([g['gid']] if i == 0 else []):
                    paths = [widetweaks.FIXES / 'previews' / f'{stem}-{n}.jpg' for n in ('before', 'after')]
                    if Image and all(p.is_file() for p in paths):
                        g['previews'][name] = [Image.open(p).convert('RGB') for p in paths]
                        break
        self.compare(None)

    def build_rows(self, g):
        """A strip per switch: the switch, its name and state; clicking anywhere on the strip flips it."""
        for w in self.rows.winfo_children():
            w.destroy()
        self.switches, self.compare_buttons = {}, {}
        for i, name in enumerate(widetweaks.toggles(g['fix'])):
            row = tk.Frame(self.rows, bg=C['pick'], highlightthickness=1, highlightbackground=C['line'])
            row.pack(fill='x', pady=(6 if i else 0, 0))
            switch = Switch(row, lambda on, n=name: self.toggle(self.selected, n, on), C['pick'])
            switch.pack(side='left', padx=(14, 12), pady=10)
            text = tk.Frame(row, bg=C['pick']); text.pack(side='left', fill='x', expand=True)
            label = tk.Label(text, text=name, font=(UI, 11, 'bold'), fg=C['text'], bg=C['pick'], anchor='w'); label.pack(fill='x')
            state = tk.Label(text, font=(MONO, 8), bg=C['pick'], anchor='w', justify='left', wraplength=round(380 * SCALE)); state.pack(fill='x')
            for w in (row, text, label, state):
                w.configure(cursor='hand2'); w.bind('<Button-1>', lambda e, s=switch: s.event_generate('<Button-1>'))
            self.switches[name] = (switch, state)
            if name in g.get('previews', {}):   # "Compare": the picture on top becomes original (above) vs fixed (below)
                button = tk.Label(row, text='◐  Compare', font=(UI, 9), fg=C['accent'], bg=C['card'], cursor='hand2',
                                  padx=10, pady=3, highlightthickness=1, highlightbackground=C['line'])
                button.bind('<Button-1>', lambda e, n=name: self.compare(None if self.comparing == n else n))
                button.pack(side='right', padx=(0, 12))
                self.compare_buttons[name] = button

    def compare(self, name):
        """Show the comparison of switch `name` in the picture area (None: the game's picture again)."""
        self.comparing = name if self.selected and name in self.selected.get('previews', {}) else None
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
        before, after = self.selected['previews'][self.comparing]
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
        for g in self.games:
            try:
                a = self.assets(g)
                data = download(f"https://cdn.fastly.steamstatic.com/steamcommunity/public/images/apps/{g['fix']['steam_appid']}/{a['community_icon']}.jpg")
            except Exception:
                continue
            self.root.after(0, lambda g=g, data=data: self.set_icon(g, data))

    def set_icon(self, g, data):
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
            self.root.after_idle(self.fit_window)
            return
        if g.get('art_width') != w:
            im = g['art_raw']
            g['art'], g['art_width'] = ImageTk.PhotoImage(im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)), w
        if self.comparing:
            self.draw_compare(None)
        else:
            self.art.configure(image=g['art'])
        self.root.after_idle(self.fit_window)

    def fit_window(self):
        """The window never shorter than what it shows: picture, every switch, Details (grows if it must). Width stays
        free above WIDTH: the picture follows the width, so the width can't follow the picture."""
        self.root.update_idletasks()                # let the layout settle first, or the height is stale
        h = self.root.winfo_reqheight()
        if self.root.minsize() != (WIDTH, h) or self.root.winfo_height() < h:
            self.root.minsize(WIDTH, h)
            if self.root.winfo_height() < h:
                self.root.geometry(f'{self.root.winfo_width()}x{h}')

    def show_details(self, open_):
        self.details_open = open_
        self.more.configure(text='Details ▾' if open_ else 'Details ▸')
        self.root.after_idle(self.fit_window)
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
        self.details.configure(text=f"{f.get('notes', '')}\n\n{where}".strip())
        self.show_art(g)
        self.load_previews(g)
        self.build_rows(g)
        self.refresh(g, recheck=False)
        self.root.after_idle(self.fit_window)

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
            self.root.after_idle(self.fit_window)

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
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    run()
