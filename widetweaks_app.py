"""The WideTweaks window, two columns like Flawless Widescreen: the supported games on the left (with a dot
for their state), the selected game on the right with its on/off switch. On patches the game for your resolution
(backup kept), off puts the original back. Opened by `widetweaks` with no arguments, which is also what
double-clicking widetweaks.exe does."""
import json, platform, threading, tkinter as tk, urllib.parse, urllib.request, webbrowser
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
ICON = 18                               # list icon size (px)
STATES = {'missing': ('NOT INSTALLED', 'faint'), 'off': ('INSTALLED · ORIGINAL', 'muted'), 'on': ('PATCHED', 'ok'),
          'unsupported': ('UNSUPPORTED GAME VERSION', 'warn')}


class Switch(tk.Canvas):
    """A pill on/off switch. command(new_state) decides; the switch only shows what it's told (set())."""
    W, H = 46, 26

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


def download(url):
    return urllib.request.urlopen(url, timeout=10).read()


def link(parent, text, url, color, font, bg):
    label = tk.Label(parent, text=text, font=font, fg=color, bg=bg, cursor='hand2')
    label.bind('<Button-1>', lambda e: webbrowser.open(url))
    return label


class App:
    def __init__(self, root):
        self.root = root
        root.title('WideTweaks')
        root.configure(bg=C['bg'])
        root.minsize(760, 420)

        # Header: name, tagline, links; then your resolution (the switches patch for whatever is here).
        head = tk.Frame(root, bg=C['bg']); head.pack(fill='x', padx=24, pady=(8, 0))
        tk.Label(head, text='WideTweaks', font=(UI, 20, 'bold'), fg=C['text'], bg=C['bg']).pack(side='left')
        link(head, 'imahappy.dev', SITE, C['accent'], (UI, 10), C['bg']).pack(side='right', anchor='s', pady=(0, 4))
        sub = tk.Frame(root, bg=C['bg']); sub.pack(fill='x', padx=24, pady=(0, 16))
        tk.Label(sub, text='Ultrawide Game Compatibility Toolkit', font=(UI, 11), fg=C['muted'], bg=C['bg']).pack(side='left')
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
        left = tk.Frame(body, bg=C['card'], highlightthickness=1, highlightbackground=C['line'], width=250)
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

        foot = tk.Frame(root, bg=C['bg']); foot.pack(fill='x', padx=24, pady=(12, 16))
        tk.Label(foot, text='by ImaHappy', font=(UI, 9), fg=C['faint'], bg=C['bg']).pack(side='left')
        link(foot, 'GitHub', REPO, C['muted'], (UI, 9), C['bg']).pack(side='right')
        link(foot, '♥ Support me on Ko-fi', KOFI, C['kofi'], (UI, 9), C['bg']).pack(side='right', padx=(0, 14))

        self.none = tk.Label(self.list, text='No match', font=(UI, 10), fg=C['faint'], bg=C['card'])
        self.selected = None
        self.build_detail()
        threading.Thread(target=self.fetch_icons, daemon=True).start()
        for g in self.games:
            self.refresh(g)
        if self.games:
            self.select(next((g for g in self.games if g['state'] != 'missing'), self.games[0]))

    def build_detail(self):
        d = self.detail
        self.art = tk.Label(d, bg=C['bg'], height=0)            # the game's Steam header image, when loaded
        self.art.pack(fill='x')
        self.title = tk.Label(d, font=(UI, 16, 'bold'), fg=C['text'], bg=C['card'], anchor='w')
        self.title.pack(fill='x', padx=20, pady=(16, 2))
        self.summary = tk.Label(d, font=(UI, 10), fg=C['muted'], bg=C['card'], anchor='w', justify='left', wraplength=420)
        self.summary.pack(fill='x', padx=20)
        # The switch with its label and state beside it, on a slightly raised strip.
        row = tk.Frame(d, bg=C['pick'], highlightthickness=1, highlightbackground=C['line']); row.pack(fill='x', padx=20, pady=(18, 0))
        self.switch = Switch(row, lambda on: self.toggle(self.selected, on), C['pick']); self.switch.pack(side='left', padx=(14, 12), pady=12)
        text = tk.Frame(row, bg=C['pick']); text.pack(side='left', fill='x', expand=True)
        self.toggle_label = tk.Label(text, font=(UI, 11, 'bold'), fg=C['text'], bg=C['pick'], anchor='w'); self.toggle_label.pack(fill='x')
        self.state = tk.Label(text, font=(MONO, 8), bg=C['pick'], anchor='w', justify='left', wraplength=380)
        self.state.pack(fill='x')
        # "Compare": swaps the picture on top for original vs fixed, split where the mouse is.
        self.compare_button = tk.Label(row, text='◐  Compare', font=(UI, 9), fg=C['accent'], bg=C['card'], cursor='hand2',
                                       padx=10, pady=3, highlightthickness=1, highlightbackground=C['line'])
        self.compare_button.bind('<Button-1>', lambda e: self.compare(not self.comparing))
        self.comparing = False
        self.art.bind('<Motion>', lambda e: self.comparing and self.draw_compare(e.x))
        for w in (row, text, self.toggle_label, self.state):    # the whole strip flips the switch
            w.configure(cursor='hand2'); w.bind('<Button-1>', lambda e: self.switch.event_generate('<Button-1>'))
        # Details (how the fix works, where the game is), folded away until clicked.
        self.more = tk.Label(d, text='Details ▸', font=(UI, 9), fg=C['faint'], bg=C['card'], anchor='w', cursor='hand2')
        self.more.pack(fill='x', padx=20, pady=(12, 16))
        self.more.bind('<Button-1>', lambda e: self.show_details(not self.details_open))
        self.details = tk.Label(d, font=(UI, 9), fg=C['muted'], bg=C['card'], anchor='w', justify='left', wraplength=420)
        self.details_open = False

    def show_art(self, g):
        """The game's Steam header image across the top of the right column, fetched once in the background."""
        if not Image:
            return
        if 'art' in g:
            return self.art.configure(image=g['art'] or '')
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
        """fixes/previews/<id>-before.jpg and -after.jpg, if the fix has them (then the Compare button shows)."""
        if 'previews' not in g:
            paths = [widetweaks.FIXES / 'previews' / f"{g['gid']}-{n}.jpg" for n in ('before', 'after')]
            g['previews'] = [Image.open(p).convert('RGB') for p in paths] if Image and all(p.is_file() for p in paths) else None
        self.compare(False)
        if g['previews']:
            self.compare_button.pack(side='right', padx=(0, 12))
        else:
            self.compare_button.pack_forget()

    def compare(self, on):
        self.comparing = on and bool(self.selected and self.selected.get('previews'))
        self.compare_button.configure(fg=C['bg'] if self.comparing else C['accent'], bg=C['accent'] if self.comparing else C['card'],
                                      text='✕  Close' if self.comparing else '◐  Compare')
        self.art.configure(cursor='sb_h_double_arrow' if self.comparing else '')
        if self.comparing:
            self.draw_compare(None)
        elif self.selected:
            self.art.configure(image=self.selected.get('art') or '')

    def draw_compare(self, x):
        """Original left of x, fixed right of it, with a divider and corner labels."""
        before, after = self.selected['previews']
        w = max(1, self.detail.winfo_width() - 2)
        if self.selected.get('compare_size') != w:            # scaled to the column once, then reused while moving
            self.selected['compare_size'] = w
            self.selected['compare'] = [im.resize((w, round(im.height * w / im.width)), Image.LANCZOS) for im in (before, after)]
        b, a = self.selected['compare']
        x = w // 2 if x is None else max(0, min(w, x))
        out = a.copy(); out.paste(b.crop((0, 0, x, b.height)), (0, 0))
        d = ImageDraw.Draw(out)
        d.rectangle((x - 1, 0, x, out.height), fill=C['accent'])
        d.ellipse((x - 11, out.height // 2 - 11, x + 11, out.height // 2 + 11), fill=C['accent'])
        y = out.height // 2
        d.polygon(((x - 7, y), (x - 2, y - 5), (x - 2, y + 5)), fill=C['bg'])
        d.polygon(((x + 7, y), (x + 2, y - 5), (x + 2, y + 5)), fill=C['bg'])
        for text, left in (('ORIGINAL', True), ('WIDETWEAKS', False)):
            tw = d.textlength(text, font=FONT)
            x0 = 10 if left else w - tw - 26
            d.rounded_rectangle((x0, 10, x0 + tw + 16, 32), 5, fill=C['bg'])
            d.text((x0 + 8, 21), text, font=FONT, fill=C['text'], anchor='lm')
        art = self.selected.get('art')
        if art and art.height() > out.height:                 # same height as the Steam picture, so nothing jumps
            framed = Image.new('RGB', (w, art.height()), C['bg']); framed.paste(out, (0, (art.height() - out.height) // 2))
            out = framed
        self.compare_image = ImageTk.PhotoImage(out)
        self.art.configure(image=self.compare_image)

    def assets(self, g):
        """The game's Steam store image names (asked once per game, shared by the icon and the header)."""
        if 'assets' not in g:
            q = {'ids': [{'appid': g['fix']['steam_appid']}], 'context': {'language': 'english', 'country_code': 'US'},
                 'data_request': {'include_assets': True}}
            url = 'https://api.steampowered.com/IStoreBrowseService/GetItems/v1/?' + urllib.parse.urlencode({'input_json': json.dumps(q)})
            g['assets'] = json.loads(download(url))['response']['store_items'][0]['assets']
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
        g['art'] = None
        if data:
            im = Image.open(io.BytesIO(data))
            w = max(1, self.detail.winfo_width() - 2)
            g['art'] = ImageTk.PhotoImage(im.resize((w, round(im.height * w / im.width)), Image.LANCZOS))
        if g is self.selected and not self.comparing:
            self.art.configure(image=g['art'] or '')

    def show_details(self, open_):
        self.details_open = open_
        self.more.configure(text='Details ▾' if open_ else 'Details ▸')
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
        for o in self.games:
            bg = C['pick'] if o is g else C['card']
            for w in (o['row'], o['icon'], o['dot'], o['name']):
                w.configure(bg=bg)
            o['name'].configure(fg=C['text'] if o is g else C['muted'])
        f = g['fix']
        self.title.configure(text=f['name'])
        self.summary.configure(text=f['summary'])
        self.toggle_label.configure(text=f.get('toggle', 'Ultrawide fix'))
        where = str(g['game'] / f['exe']) if g['game'] else f"Steam app {f['steam_appid']}, not found in your Steam libraries"
        self.details.configure(text=f"{f.get('notes', '')}\n\n{where}".strip())
        self.show_art(g)
        self.load_previews(g)
        self.refresh(g)

    def refresh(self, g, message=None, color=None):
        g['state'] = widetweaks.status(g['fix'], g['game'])
        text, tone = STATES[g['state']]
        g['dot'].configure(fg=C[tone])
        if g is self.selected:
            self.state.configure(text=message or text, fg=color or C[tone])
            self.switch.set(g['state'] == 'on', enabled=g['state'] in ('on', 'off'))

    def toggle(self, g, on):
        try:
            if on:
                r = self.resolution()
                if not r:
                    return self.refresh(g, 'ENTER YOUR RESOLUTION FIRST, E.G. 3440X1440', C['warn'])
                widetweaks.patch(g['fix'], g['game'], *r)
                self.refresh(g, f'PATCHED FOR {r[0]}×{r[1]}', C['ok'])
            else:
                widetweaks.restore(g['fix'], g['game'])
                self.refresh(g)
        except (ValueError, OSError) as e:          # e.g. game running (file in use), unknown version
            self.refresh(g, str(e).upper()[:160], C['bad'])


def run():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    run()
