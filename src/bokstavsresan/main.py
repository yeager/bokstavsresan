#!/usr/bin/env python3
"""Bokstavsresan — Phonetics and letter learning game for children with dyspraxia."""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk, Pango
import gettext
import locale
import os
import sys
import json
import random
import subprocess
import time
from pathlib import Path
from bokstavsresan import __version__

APP_ID = "se.danielnylander.bokstavsresan"
LOCALE_DIR = os.path.join(sys.prefix, "share", "locale")

locale.bindtextdomain(APP_ID, LOCALE_DIR)
gettext.bindtextdomain(APP_ID, LOCALE_DIR)
gettext.textdomain(APP_ID)
_ = gettext.gettext

# Swedish phonetic sounds for each letter
LETTER_PHONETICS = {
    "A": "ah", "B": "beh", "C": "seh", "D": "deh", "E": "eh",
    "F": "eff", "G": "geh", "H": "hå", "I": "ih", "J": "jih",
    "K": "kå", "L": "ell", "M": "emm", "N": "enn", "O": "oh",
    "P": "peh", "Q": "kuh", "R": "err", "S": "ess", "T": "teh",
    "U": "uh", "V": "veh", "W": "dubbelveh", "X": "eks", "Y": "yh",
    "Z": "seta", "Å": "å", "Ä": "äh", "Ö": "öh",
}

# Short phonetic sounds (how the letter sounds in a word)
# Elongated for TTS clarity — children with verbal dyspraxia need slow, clear phonemes
LETTER_SOUNDS = {
    "A": "aaa", "B": "bbb", "C": "sss", "D": "ddd", "E": "eee",
    "F": "fff", "G": "ggg", "H": "hhh", "I": "iii", "J": "jjj",
    "K": "kkk", "L": "lll", "M": "mmm", "N": "nnn", "O": "ooo",
    "P": "ppp", "Q": "kkk", "R": "rrr", "S": "sss", "T": "ttt",
    "U": "uuu", "V": "vvv", "W": "vvv", "X": "ks", "Y": "yyy",
    "Z": "sss", "Å": "ååå", "Ä": "äää", "Ö": "ööö",
}

# Simple Swedish words grouped by difficulty
WORDS_EASY = [
    ("SOL", _("sun")), ("KAT", _("cat")), ("HUS", _("house")),
    ("BIL", _("car")), ("MUS", _("mouse")), ("HÅR", _("hair")),
    ("BÅT", _("boat")), ("ÖGA", _("eye")), ("ARM", _("arm")),
    ("BEN", _("leg")), ("LÅS", _("lock")), ("NÄS", _("nose")),
]

WORDS_MEDIUM = [
    ("BOLL", _("ball")), ("LAMM", _("lamb")), ("FISK", _("fish")),
    ("GRIS", _("pig")), ("HUND", _("dog")), ("KATT", _("cat")),
    ("STOL", _("chair")), ("DÖRR", _("door")), ("BLAD", _("leaf")),
    ("SNÄL", _("kind")), ("GLAD", _("happy")), ("STOR", _("big")),
]

WORDS_HARD = [
    ("ÄPPLE", _("apple")), ("SKOLA", _("school")), ("BJÖRN", _("bear")),
    ("BLOMMA", _("flower")), ("STJÄRNA", _("star")), ("TRÄD", _("tree")),
    ("SJUNGA", _("sing")), ("HIMMEL", _("sky")), ("VATTEN", _("water")),
]

ENCOURAGEMENTS = [
    _("Great job! ⭐"), _("Fantastic! 🌟"), _("You're a star! ✨"),
    _("Amazing! 🎉"), _("Well done! 👏"), _("Keep going! 💪"),
    _("Super! 🚀"), _("Brilliant! 🌈"), _("You did it! 🎊"),
    _("Wow, incredible! 🏆"), _("Perfect! 💯"), _("Champion! 🥇"),
]

TRY_AGAIN = [
    _("Almost! Try again! 💪"), _("So close! One more time! 🌟"),
    _("You can do it! 🎯"), _("Don't give up! Keep trying! 💫"),
]

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "bokstavsresan"


def _get_tts_engine():
    """Get TTS engine: Piper first, espeak-ng fallback."""
    try:
        subprocess.run(["piper", "--help"], capture_output=True, timeout=2)
        return "piper"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    try:
        subprocess.run(["espeak-ng", "--help"], capture_output=True, timeout=2)
        return "espeak-ng"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _speak(text, engine=None):
    """Speak text using TTS."""
    if engine is None:
        engine = _get_tts_engine()
    if engine is None:
        return
    try:
        if engine == "piper":
            proc = subprocess.Popen(
                ["piper", "--model",
                 os.path.expanduser("~/.local/share/piper-voices/sv_SE-nst-medium.onnx"),
                 "--output-raw", "--length-scale", "1.5"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            audio, _ = proc.communicate(text.encode(), timeout=10)
            if audio:
                subprocess.Popen(
                    ["aplay", "-r", "22050", "-f", "S16_LE", "-c", "1", "-q"],
                    stdin=subprocess.PIPE,
                ).communicate(audio, timeout=10)
        elif engine == "espeak-ng":
            subprocess.run(
                ["espeak-ng", "-v", "sv", text],
                capture_output=True, timeout=10,
            )
    except Exception:
        pass


class ProgressStore:
    """Track learning progress."""

    def __init__(self):
        self.path = CONFIG_DIR / "progress.json"
        self.data = {"letters_mastered": [], "streak": 0, "total_correct": 0,
                     "total_attempts": 0, "stars": 0, "level": 1}
        self._load()

    def _load(self):
        try:
            if self.path.exists():
                with open(self.path) as f:
                    self.data.update(json.load(f))
        except Exception:
            pass

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def record_correct(self, letter):
        self.data["total_correct"] += 1
        self.data["total_attempts"] += 1
        self.data["streak"] += 1
        self.data["stars"] += 1
        if letter not in self.data["letters_mastered"]:
            self.data["letters_mastered"].append(letter)
        if self.data["streak"] % 5 == 0:
            self.data["stars"] += 2  # bonus stars
        self.save()

    def record_wrong(self):
        self.data["total_attempts"] += 1
        self.data["streak"] = 0
        self.save()


class LetterButton(Gtk.Button):
    """A big colorful letter button."""

    COLORS = [
        "#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6",
        "#1abc9c", "#e67e22", "#e91e63", "#00bcd4", "#8bc34a",
    ]

    def __init__(self, letter, idx):
        super().__init__()
        self.letter = letter
        label = Gtk.Label(label=letter)
        label.add_css_class("letter-btn-label")
        self.set_child(label)
        self.add_css_class("letter-btn")
        color = self.COLORS[idx % len(self.COLORS)]
        css = f"""
            .letter-btn {{ 
                background: {color}; color: white; border-radius: 16px;
                min-width: 64px; min-height: 64px; font-size: 28px; 
                font-weight: bold; border: 3px solid rgba(255,255,255,0.3);
                transition: all 200ms ease;
            }}
            .letter-btn:hover {{ 
                transform: scale(1.1); 
                box-shadow: 0 4px 12px rgba(0,0,0,0.3); 
            }}
            .letter-btn.correct {{
                background: #27ae60; animation: pulse 500ms;
            }}
            .letter-btn.wrong {{
                background: #c0392b; 
            }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        self.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.connect("activate", self._on_activate)
        self.tts_engine = _get_tts_engine()
        self.progress = ProgressStore()
        self.current_mode = "explore"  # explore, find, soundout
        self.target_letter = None
        self.current_word = None
        self.current_word_idx = 0
        
        # Easter egg state
        self._egg_clicks = 0
        self._egg_timer = None

    def _on_activate(self, app):
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_title(_("Letter Journey"))
        self.win.set_default_size(900, 700)

        # CSS
        css = Gtk.CssProvider()
        css.load_from_string("""
            .title-big { font-size: 32px; font-weight: bold; }
            .subtitle { font-size: 16px; color: alpha(@theme_fg_color, 0.7); }
            .star-label { font-size: 24px; color: #f39c12; }
            .streak-label { font-size: 18px; font-weight: bold; color: #e74c3c; }
            .encourage-label { font-size: 22px; font-weight: bold; color: #27ae60; }
            .word-display { font-size: 48px; font-weight: bold; letter-spacing: 8px; }
            .word-letter { font-size: 48px; font-weight: bold; }
            .word-letter-active { color: #e74c3c; font-size: 56px; }
            .word-letter-done { color: #27ae60; }
            .word-hint { font-size: 16px; color: alpha(@theme_fg_color, 0.5); }
            .mode-btn { min-height: 80px; border-radius: 16px; }
            .game-header { padding: 12px; }
            .level-badge { 
                background: #3498db; color: white; border-radius: 20px; 
                padding: 4px 16px; font-weight: bold; 
            }
            .letter-btn-label { font-size: 28px; font-weight: bold; }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Setup actions
        for name, cb, accels in [
            ("about", self._on_about, ["F1"]),
            ("quit", lambda *_a: self.quit(), ["<Control>q"]),
        ]:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)

        # Menu
        menu = Gio.Menu()
        menu.append(_("About"), "app.about")
        menu.append(_("Quit"), "app.quit")

        # Header bar
        self.header = Adw.HeaderBar()
        
        # Add clickable app icon for easter egg
        app_btn = Gtk.Button()
        app_btn.set_icon_name(APP_ID)
        app_btn.add_css_class("flat")
        app_btn.set_tooltip_text(_("Bokstavsresan"))
        app_btn.connect("clicked", self._on_icon_clicked)
        self.header.pack_start(app_btn)
        
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        self.header.pack_end(menu_btn)

        # Stars display
        self.stars_label = Gtk.Label(label=f"⭐ {self.progress.data['stars']}")
        self.stars_label.add_css_class("star-label")
        self.header.pack_start(self.stars_label)

        # Streak display
        self.streak_label = Gtk.Label(label=f"🔥 {self.progress.data['streak']}")
        self.streak_label.add_css_class("streak-label")
        self.header.pack_start(self.streak_label)

        # Main stack
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        # Create pages
        self._build_menu_page()
        self._build_explore_page()
        self._build_find_page()
        self._build_soundout_page()

        # Layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.append(self.header)
        vbox.append(self.stack)
        self.win.set_content(vbox)

        # Encouragement overlay
        self.encourage_label = Gtk.Label()
        self.encourage_label.add_css_class("encourage-label")
        self.encourage_label.set_visible(False)

        # Welcome dialog on first run
        self._check_welcome()

        self.win.present()

    def _check_welcome(self):
        welcome_path = CONFIG_DIR / "welcome.json"
        if welcome_path.exists():
            return
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(welcome_path, "w") as f:
            json.dump({"shown": True}, f)

        dialog = Adw.AlertDialog(
            heading=_("Welcome to Letter Journey! 🎉"),
            body=_(
                "Learn letters and sounds through fun games!\n\n"
                "🔤 Explore — Tap letters to hear how they sound\n"
                "🎯 Find the Letter — Listen and find the right one\n"
                "📖 Sound Out — Break words into letter sounds\n\n"
                "You earn ⭐ stars for every correct answer.\n"
                "Keep your 🔥 streak going for bonus stars!\n\n"
                "Let's go! 💪"
            ),
        )
        dialog.add_response("start", _("Let's start! 🚀"))
        dialog.set_default_response("start")
        dialog.present(self.win)

    def _build_menu_page(self):
        """Main menu with game mode selection."""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24,
                       valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        page.set_margin_top(32)
        page.set_margin_bottom(32)
        page.set_margin_start(48)
        page.set_margin_end(48)

        title = Gtk.Label(label=_("Letter Journey"))
        title.add_css_class("title-big")
        page.append(title)

        subtitle = Gtk.Label(label=_("Choose your adventure! 🗺️"))
        subtitle.add_css_class("subtitle")
        page.append(subtitle)

        # Level badge
        level = self.progress.data.get("level", 1)
        badge = Gtk.Label(label=f"⭐ {_('Level')} {level}")
        badge.add_css_class("level-badge")
        page.append(badge)

        # Mode buttons
        modes = [
            ("explore", "🔤", _("Explore Letters"),
             _("Tap letters to hear their name and sound")),
            ("find", "🎯", _("Find the Letter"),
             _("Listen to a sound and find the right letter")),
            ("soundout", "📖", _("Sound Out Words"),
             _("Break words into individual letter sounds")),
        ]
        for mode_id, emoji, title_text, desc in modes:
            btn = Gtk.Button()
            btn.add_css_class("mode-btn")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            lbl = Gtk.Label(label=f"{emoji} {title_text}")
            lbl.add_css_class("title-4")
            box.append(lbl)
            dlbl = Gtk.Label(label=desc, wrap=True)
            dlbl.add_css_class("subtitle")
            box.append(dlbl)
            btn.set_child(box)
            btn.connect("clicked", self._on_mode_select, mode_id)
            page.append(btn)

        # Progress summary
        p = self.progress.data
        stats = Gtk.Label(
            label=_("Letters mastered: {mastered}/29 | Total correct: {correct}").format(
                mastered=len(p["letters_mastered"]), correct=p["total_correct"]
            )
        )
        stats.add_css_class("subtitle")
        page.append(stats)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(page)
        self.stack.add_named(scroll, "menu")

    def _build_explore_page(self):
        """Letter exploration grid."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_top(12)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)

        # Back button
        back = Gtk.Button(icon_name="go-previous-symbolic", halign=Gtk.Align.START)
        back.connect("clicked", lambda _b: self.stack.set_visible_child_name("menu"))
        vbox.append(back)

        # Title
        title = Gtk.Label(label=_("🔤 Tap a letter to hear it!"))
        title.add_css_class("title-3")
        vbox.append(title)

        # Feedback label
        self.explore_feedback = Gtk.Label(label="")
        self.explore_feedback.add_css_class("encourage-label")
        vbox.append(self.explore_feedback)

        # Letter grid
        grid = Gtk.FlowBox(
            max_children_per_line=7, min_children_per_line=5,
            selection_mode=Gtk.SelectionMode.NONE,
            row_spacing=8, column_spacing=8,
            homogeneous=True, halign=Gtk.Align.CENTER,
        )
        letters = list(LETTER_PHONETICS.keys())
        for i, letter in enumerate(letters):
            btn = LetterButton(letter, i)
            btn.connect("clicked", self._on_explore_letter)
            grid.append(btn)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(grid)
        vbox.append(scroll)

        self.stack.add_named(vbox, "explore")

    def _build_find_page(self):
        """Find the letter game."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        vbox.set_margin_top(12)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)

        # Back button
        back = Gtk.Button(icon_name="go-previous-symbolic", halign=Gtk.Align.START)
        back.connect("clicked", lambda _b: self.stack.set_visible_child_name("menu"))
        vbox.append(back)

        # Instruction
        self.find_instruction = Gtk.Label(label=_("🎯 Listen and find the letter!"))
        self.find_instruction.add_css_class("title-3")
        vbox.append(self.find_instruction)

        # Play sound button
        play_btn = Gtk.Button(label=_("🔊 Play sound again"))
        play_btn.connect("clicked", self._on_replay_find)
        vbox.append(play_btn)

        # Feedback
        self.find_feedback = Gtk.Label(label="")
        self.find_feedback.add_css_class("encourage-label")
        vbox.append(self.find_feedback)

        # Letter grid (subset based on difficulty)
        self.find_grid = Gtk.FlowBox(
            max_children_per_line=5, min_children_per_line=3,
            selection_mode=Gtk.SelectionMode.NONE,
            row_spacing=12, column_spacing=12,
            homogeneous=True, halign=Gtk.Align.CENTER,
        )
        vbox.append(self.find_grid)

        # Next button
        self.find_next_btn = Gtk.Button(label=_("Next letter ➡️"))
        self.find_next_btn.add_css_class("suggested-action")
        self.find_next_btn.connect("clicked", lambda _b: self._start_find_round())
        self.find_next_btn.set_visible(False)
        vbox.append(self.find_next_btn)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(vbox)
        self.stack.add_named(scroll, "find")

    def _build_soundout_page(self):
        """Sound out words mode."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                       valign=Gtk.Align.CENTER)
        vbox.set_margin_top(12)
        vbox.set_margin_start(24)
        vbox.set_margin_end(24)

        # Back button
        back = Gtk.Button(icon_name="go-previous-symbolic", halign=Gtk.Align.START)
        back.connect("clicked", lambda _b: self.stack.set_visible_child_name("menu"))
        vbox.append(back)

        # Title
        self.soundout_title = Gtk.Label(label=_("📖 Sound out the word!"))
        self.soundout_title.add_css_class("title-3")
        vbox.append(self.soundout_title)

        # Word display with individual letters
        self.word_box = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        vbox.append(self.word_box)

        # Hint (translation)
        self.word_hint = Gtk.Label(label="")
        self.word_hint.add_css_class("word-hint")
        vbox.append(self.word_hint)

        # Feedback
        self.soundout_feedback = Gtk.Label(label="")
        self.soundout_feedback.add_css_class("encourage-label")
        vbox.append(self.soundout_feedback)

        # Sound out button
        sound_btn = Gtk.Button(label=_("🔊 Sound this letter"))
        sound_btn.connect("clicked", self._on_sound_current)
        vbox.append(sound_btn)

        # Next letter in word
        self.next_sound_btn = Gtk.Button(label=_("Next sound ➡️"))
        self.next_sound_btn.add_css_class("suggested-action")
        self.next_sound_btn.connect("clicked", self._on_next_sound)
        vbox.append(self.next_sound_btn)

        # New word button
        self.new_word_btn = Gtk.Button(label=_("New word 🔄"))
        self.new_word_btn.connect("clicked", lambda _b: self._start_soundout_round())
        vbox.append(self.new_word_btn)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(vbox)
        self.stack.add_named(scroll, "soundout")

    def _on_mode_select(self, _btn, mode):
        self.current_mode = mode
        self.stack.set_visible_child_name(mode)
        if mode == "find":
            self._start_find_round()
        elif mode == "soundout":
            self._start_soundout_round()

    def _on_explore_letter(self, btn):
        letter = btn.letter
        # Show phonetic info
        name = LETTER_PHONETICS.get(letter, letter)
        sound = LETTER_SOUNDS.get(letter, letter)
        self.explore_feedback.set_text(
            _("{letter} — Name: '{name}', Sound: '{sound}'").format(
                letter=letter, name=name, sound=sound
            )
        )
        # Speak
        GLib.timeout_add(50, lambda: _speak(
            f"{letter}. {name}. {sound}.", self.tts_engine
        ))
        # Record progress
        self.progress.record_correct(letter)
        self._update_stats()

    def _start_find_round(self):
        """Start a new 'find the letter' round."""
        self.find_feedback.set_text("")
        self.find_next_btn.set_visible(False)

        # Pick target and distractors
        letters = list(LETTER_PHONETICS.keys())
        self.target_letter = random.choice(letters)
        choices = [self.target_letter]
        distractors = [l for l in letters if l != self.target_letter]
        choices.extend(random.sample(distractors, min(5, len(distractors))))
        random.shuffle(choices)

        # Clear grid
        while True:
            child = self.find_grid.get_first_child()
            if child is None:
                break
            self.find_grid.remove(child)

        # Add letter buttons
        for i, letter in enumerate(choices):
            btn = LetterButton(letter, i)
            btn.connect("clicked", self._on_find_letter)
            self.find_grid.append(btn)

        # Speak the target letter sound
        GLib.timeout_add(500, lambda: _speak(
            LETTER_PHONETICS[self.target_letter], self.tts_engine
        ))
        self.find_instruction.set_text(
            _("🎯 Which letter says '{sound}'?").format(
                sound=LETTER_PHONETICS[self.target_letter]
            )
        )

    def _on_replay_find(self, _btn):
        if self.target_letter:
            _speak(LETTER_PHONETICS[self.target_letter], self.tts_engine)

    def _on_find_letter(self, btn):
        if btn.letter == self.target_letter:
            self.find_feedback.set_text(random.choice(ENCOURAGEMENTS))
            self.progress.record_correct(btn.letter)
            self._update_stats()
            btn.add_css_class("correct")
            self.find_next_btn.set_visible(True)
            # Cheer sound
            GLib.timeout_add(200, lambda: _speak(
                random.choice([_("Correct!"), _("Yes!"), _("Great!")]),
                self.tts_engine,
            ))
        else:
            self.find_feedback.set_text(random.choice(TRY_AGAIN))
            self.progress.record_wrong()
            self._update_stats()
            btn.add_css_class("wrong")
            GLib.timeout_add(1000, lambda: btn.remove_css_class("wrong"))

    def _start_soundout_round(self):
        """Start a new sound-out-the-word round."""
        self.soundout_feedback.set_text("")
        level = self.progress.data.get("level", 1)
        if level <= 1:
            words = WORDS_EASY
        elif level <= 2:
            words = WORDS_EASY + WORDS_MEDIUM
        else:
            words = WORDS_EASY + WORDS_MEDIUM + WORDS_HARD

        self.current_word, hint = random.choice(words)
        self.current_word_idx = 0
        self.word_hint.set_text(f"({hint})")

        self._update_word_display()

        # Speak the whole word first
        GLib.timeout_add(300, lambda: _speak(self.current_word, self.tts_engine))

    def _update_word_display(self):
        """Update the word display with highlighted current letter."""
        # Clear
        while True:
            child = self.word_box.get_first_child()
            if child is None:
                break
            self.word_box.remove(child)

        for i, ch in enumerate(self.current_word):
            lbl = Gtk.Label(label=ch)
            lbl.add_css_class("word-letter")
            if i < self.current_word_idx:
                lbl.add_css_class("word-letter-done")
            elif i == self.current_word_idx:
                lbl.add_css_class("word-letter-active")
            self.word_box.append(lbl)

    def _on_sound_current(self, _btn):
        """Sound out the current letter."""
        if self.current_word and self.current_word_idx < len(self.current_word):
            letter = self.current_word[self.current_word_idx]
            sound = LETTER_SOUNDS.get(letter, letter)
            _speak(sound, self.tts_engine)
            self.soundout_feedback.set_text(
                _("'{letter}' sounds like '{sound}'").format(letter=letter, sound=sound)
            )

    def _on_next_sound(self, _btn):
        """Move to next letter in the word."""
        if not self.current_word:
            return
        if self.current_word_idx < len(self.current_word):
            letter = self.current_word[self.current_word_idx]
            self.progress.record_correct(letter)
            self.current_word_idx += 1
            self._update_word_display()
            self._update_stats()

            if self.current_word_idx >= len(self.current_word):
                # Word complete!
                self.soundout_feedback.set_text(
                    random.choice(ENCOURAGEMENTS) + "\n" +
                    _("You sounded out '{word}'! 🎉").format(word=self.current_word)
                )
                # Level up check
                if self.progress.data["total_correct"] > 0 and \
                   self.progress.data["total_correct"] % 20 == 0:
                    self.progress.data["level"] = min(
                        self.progress.data.get("level", 1) + 1, 3
                    )
                    self.progress.save()
                    self.soundout_feedback.set_text(
                        _("🎊 LEVEL UP! You're now level {level}! 🎊").format(
                            level=self.progress.data["level"]
                        )
                    )
                GLib.timeout_add(200, lambda: _speak(
                    _("Amazing! You did it!"), self.tts_engine
                ))
            else:
                # Sound next letter
                letter = self.current_word[self.current_word_idx]
                sound = LETTER_SOUNDS.get(letter, letter)
                GLib.timeout_add(100, lambda: _speak(sound, self.tts_engine))
                self.soundout_feedback.set_text(
                    _("'{letter}' sounds like '{sound}'").format(letter=letter, sound=sound)
                )

    def _update_stats(self):
        """Update stars and streak display."""
        self.stars_label.set_text(f"⭐ {self.progress.data['stars']}")
        self.streak_label.set_text(f"🔥 {self.progress.data['streak']}")

    def _on_about(self, *_args):
        about = Adw.AboutDialog(
            application_name=_("Letter Journey"),
            application_icon=APP_ID,
            version=__version__,
            developer_name="Daniel Nylander",
            developers=["Daniel Nylander <daniel@danielnylander.se>"],
            copyright="© 2026 Daniel Nylander",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/yeager/bokstavsresan",
            issue_url="https://github.com/yeager/bokstavsresan/issues",
            support_url="https://www.autismappar.se",
            comments=_(
                "Phonetics and letter learning game for children with dyspraxia.\n\n"
                "Learn letter names and sounds through interactive games. "
                "Features text-to-speech, progress tracking, and encouraging "
                "feedback to build confidence.\n\n"
                "Part of the Autismappar suite — free tools for "
                "communication and daily structure."
            ),
        )
        about.add_credit_section(_("Thanks to"), [
            "GTK https://gtk.org",
            "libadwaita https://gnome.pages.gitlab.gnome.org/libadwaita/",
            "Python https://python.org",
            "Transifex https://transifex.com",
            "Piper TTS https://github.com/rhasspy/piper",
            "espeak-ng https://github.com/espeak-ng/espeak-ng",
        ])
        about.present(self.props.active_window)

    def _on_icon_clicked(self, *args):
        """Handle clicks on app icon for easter egg."""
        self._egg_clicks += 1
        if self._egg_timer:
            GLib.source_remove(self._egg_timer)
        self._egg_timer = GLib.timeout_add(500, self._reset_egg)
        if self._egg_clicks >= 7:
            self._trigger_easter_egg()
            self._egg_clicks = 0

    def _reset_egg(self):
        """Reset easter egg click counter."""
        self._egg_clicks = 0
        self._egg_timer = None
        return False

    def _trigger_easter_egg(self):
        """Show the secret easter egg!"""
        try:
            # Play a fun sound
            import subprocess
            subprocess.Popen(['paplay', '/usr/share/sounds/freedesktop/stereo/complete.oga'], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            # Fallback beep
            try:
                subprocess.Popen(['pactl', 'play-sample', 'bell'], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                pass

        # Show confetti message
        toast = Adw.Toast.new(_("🎉 Du hittade hemligheten!"))
        toast.set_timeout(3)
        
        # Create toast overlay if it doesn't exist
        if not hasattr(self, '_toast_overlay'):
            content = self.win.get_content()
            self._toast_overlay = Adw.ToastOverlay()
            self._toast_overlay.set_child(content)
            self.win.set_content(self._toast_overlay)
        
        self._toast_overlay.add_toast(toast)


def main():
    app = App()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
