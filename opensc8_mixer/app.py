# OpenSC8 Mixer - interface gráfica (GTK)
# Usa GTK 3 (PyGObject do sistema). GTK 4/libadwaita ficam para quando o
# typelib gir1.2-gtk-4.0 estiver instalado.
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import config as C  # noqa: E402
from . import pw, pwconf, soundboard  # noqa: E402

AUDIO_PATTERNS = ["*.wav", "*.ogg", "*.oga", "*.opus", "*.mp3", "*.flac", "*.m4a", "*.aac"]

APP_TITLE = "OpenSC8 Mixer"

CSS = b"""
.canal { padding: 8px; border-radius: 10px; background: alpha(@theme_fg_color, 0.05); }
.canal-master { background: alpha(@theme_selected_bg_color, 0.18); }
.titulo-canal { font-weight: bold; font-size: 1.1em; }
.dica { opacity: 0.7; font-size: 0.85em; }
.prog { font-size: 0.9em; }
"""


def _vscale(value, on_change):
    adj = Gtk.Adjustment(value=value * 100, lower=0, upper=100, step_increment=1, page_increment=10)
    s = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=adj)
    s.set_inverted(True)
    s.set_digits(0)
    s.set_value_pos(Gtk.PositionType.BOTTOM)
    s.set_size_request(-1, 180)
    s.add_mark(100, Gtk.PositionType.LEFT, None)
    s.connect("value-changed", lambda w: on_change(w.get_value() / 100.0))
    return s


class Debouncer:
    """Agrupa mudanças rápidas de slider e aplica no máximo a cada 60 ms."""

    def __init__(self):
        self.pending = {}
        self.src = None

    def put(self, key, fn):
        self.pending[key] = fn
        if self.src is None:
            self.src = GLib.timeout_add(60, self._flush)

    def _flush(self):
        items, self.pending, self.src = self.pending, {}, None

        def work():
            for fn in items.values():
                fn()
        threading.Thread(target=work, daemon=True).start()
        return False


# ---------- soundboard ----------
class SoundboardMixin:
    def _soundboard_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=6)
        bar = Gtk.Box(spacing=6)
        add = Gtk.Button(label="Adicionar som")
        add.connect("clicked", lambda *_: self.edit_pad(None))
        stop = Gtk.Button(label="Parar tudo")
        stop.connect("clicked", lambda *_: soundboard.stop_all())
        hint = Gtk.Label(label="Os sons tocam no canal \"Efeitos\" (fone + live). "
                               "Atalhos funcionam com a janela em foco; para atalho global, "
                               "use no sistema: opensc8-mixer --play <número>", xalign=0)
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("dica")
        bar.pack_start(add, False, False, 0)
        bar.pack_start(stop, False, False, 0)
        box.pack_start(bar, False, False, 0)
        box.pack_start(hint, False, False, 0)
        self.pads_flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                                     max_children_per_line=8, row_spacing=8, column_spacing=8,
                                     homogeneous=True, valign=Gtk.Align.START)
        sc = Gtk.ScrolledWindow()
        sc.add(self.pads_flow)
        box.pack_start(sc, True, True, 0)
        return box

    def build_pads(self):
        for c in self.pads_flow.get_children():
            self.pads_flow.remove(c)
        pads = self.cfg.setdefault("soundboard", [])
        if not pads:
            l = Gtk.Label(label="Nenhum som ainda. Clique em \"Adicionar som\" e escolha um arquivo "
                                "(wav, ogg, mp3, flac…).")
            l.get_style_context().add_class("dica")
            self.pads_flow.add(l)
        for i, pad in enumerate(pads):
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            card.get_style_context().add_class("canal")
            play = Gtk.Button(label=pad.get("name") or "Som %d" % (i + 1))
            play.set_size_request(150, 70)
            play.set_tooltip_text(pad.get("file", ""))
            play.connect("clicked", lambda _w, p=pad: self.play_pad(p))
            card.pack_start(play, True, True, 0)
            info = "%d · vol %d%%" % (i + 1, round(float(pad.get("volume", 1.0)) * 100))
            if pad.get("hotkey"):
                info += " · " + pad["hotkey"]
            lab = Gtk.Label(label=info)
            lab.get_style_context().add_class("dica")
            card.pack_start(lab, False, False, 0)
            row = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER)
            ed = Gtk.Button.new_from_icon_name("document-edit-symbolic", Gtk.IconSize.BUTTON)
            ed.set_tooltip_text("Editar")
            ed.connect("clicked", lambda _w, n=i: self.edit_pad(n))
            rm = Gtk.Button.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.BUTTON)
            rm.set_tooltip_text("Remover")
            rm.connect("clicked", lambda _w, n=i: self.remove_pad(n))
            row.pack_start(ed, False, False, 0)
            row.pack_start(rm, False, False, 0)
            card.pack_start(row, False, False, 0)
            self.pads_flow.add(card)
        self.pads_flow.show_all()

    def play_pad(self, pad):
        ok, err = soundboard.play(pad)
        if not ok:
            self._msg("Soundboard: " + err)

    def remove_pad(self, n):
        del self.cfg["soundboard"][n]
        C.save(self.cfg)
        self.build_pads()

    def edit_pad(self, n):
        pads = self.cfg.setdefault("soundboard", [])
        pad = dict(pads[n]) if n is not None else {"name": "", "file": "", "volume": 0.8, "hotkey": ""}
        dlg = Gtk.Dialog(title="Som da soundboard", transient_for=self, modal=True)
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Salvar", Gtk.ResponseType.OK)
        g = Gtk.Grid(column_spacing=8, row_spacing=8, margin=10)
        name = Gtk.Entry(text=pad.get("name", ""), placeholder_text="Ex.: Aplausos")
        fc = Gtk.FileChooserButton(title="Escolha um arquivo de áudio", action=Gtk.FileChooserAction.OPEN)
        flt = Gtk.FileFilter()
        flt.set_name("Áudio")
        for pat in AUDIO_PATTERNS:
            flt.add_pattern(pat)
            flt.add_pattern(pat.upper())
        fc.add_filter(flt)
        if pad.get("file"):
            fc.set_filename(pad["file"])
        vol = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        vol.set_value(float(pad.get("volume", 0.8)) * 100)
        vol.set_hexpand(True)
        hot = Gtk.Entry(text=pad.get("hotkey", ""), placeholder_text="Clique e aperte a tecla (Esc limpa)")
        hot.set_editable(False)

        def grab(_w, ev):
            if ev.keyval == Gdk.KEY_Escape:
                hot.set_text("")
                return True
            mods = ev.state & Gtk.accelerator_get_default_mod_mask()
            if Gtk.accelerator_valid(ev.keyval, mods) or Gdk.KEY_F1 <= ev.keyval <= Gdk.KEY_F35:
                hot.set_text(Gtk.accelerator_name(ev.keyval, mods))
            return True
        hot.connect("key-press-event", grab)
        test = Gtk.Button(label="Testar")
        test.connect("clicked", lambda *_: self.play_pad(
            {"name": name.get_text(), "file": fc.get_filename() or "", "volume": vol.get_value() / 100}))
        for r, (lbl, w) in enumerate((("Nome", name), ("Arquivo", fc), ("Volume (%)", vol),
                                      ("Atalho", hot))):
            g.attach(Gtk.Label(label=lbl, xalign=1), 0, r, 1, 1)
            g.attach(w, 1, r, 1, 1)
        g.attach(test, 1, 4, 1, 1)
        dlg.get_content_area().add(g)
        dlg.show_all()
        resp = dlg.run()
        f = fc.get_filename() or ""
        new = {"name": name.get_text().strip() or os.path.splitext(os.path.basename(f))[0],
               "file": f, "volume": round(vol.get_value() / 100, 2), "hotkey": hot.get_text()}
        dlg.destroy()
        if resp != Gtk.ResponseType.OK or not f:
            return
        if n is None:
            pads.append(new)
        else:
            pads[n] = new
        C.save(self.cfg)
        self.build_pads()

    def on_key(self, _w, ev):
        if isinstance(self.get_focus(), Gtk.Entry):
            return False
        mods = ev.state & Gtk.accelerator_get_default_mod_mask()
        for pad in self.cfg.get("soundboard", []):
            hk = pad.get("hotkey")
            if not hk:
                continue
            key, m = Gtk.accelerator_parse(hk)
            if key and Gdk.keyval_to_lower(ev.keyval) == Gdk.keyval_to_lower(key) and mods == m:
                self.play_pad(pad)
                return True
        return False


class MixerWindow(SoundboardMixin, Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_TITLE)
        self.set_default_size(1440, 600)
        self.cfg = C.load()
        self.ids = {}
        self.deb = Debouncer()
        self.save_src = None

        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(self.get_screen(), prov,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        hb = Gtk.HeaderBar(show_close_button=True, title=APP_TITLE,
                           subtitle="Mixer de canais para a fifine SC8")
        self.set_titlebar(hb)
        add_btn = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON)
        add_btn.set_tooltip_text("Adicionar canal")
        add_btn.connect("clicked", self.on_add_channel)
        hb.pack_start(add_btn)
        refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        refresh.set_tooltip_text("Atualizar")
        refresh.connect("clicked", lambda *_: self.refresh())
        hb.pack_end(refresh)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=10)
        self.status = Gtk.Label(xalign=0)
        self.status.get_style_context().add_class("dica")
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                      vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        self.row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        scroller.add(self.row)
        self.notebook = Gtk.Notebook()
        self.notebook.append_page(scroller, Gtk.Label(label="Mixer"))
        self.notebook.append_page(self._soundboard_page(), Gtk.Label(label="Soundboard"))
        outer.pack_start(self.notebook, True, True, 0)
        outer.pack_start(self.status, False, False, 0)
        self.add(outer)
        self.connect("key-press-event", self.on_key)

        self.build()
        self.build_pads()
        self.refresh()
        GLib.timeout_add_seconds(3, self._tick)

    # ---------- construção ----------
    def build(self):
        for c in self.row.get_children():
            self.row.remove(c)
        self.prog_boxes = {}
        for ch in self.cfg["channels"]:
            self.row.pack_start(self._channel_column(ch), False, False, 0)
        self.row.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 4)
        self.row.pack_start(self._mic_column(), False, False, 0)
        self.row.pack_start(self._master_column(), False, False, 0)
        self.row.show_all()

    def _column(self, title, master=False):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.get_style_context().add_class("canal")
        if master:
            box.get_style_context().add_class("canal-master")
        box.set_size_request(160, -1)
        lab = Gtk.Label(label=title)
        lab.get_style_context().add_class("titulo-canal")
        box.pack_start(lab, False, False, 0)
        return box, lab

    def _slider_pair(self, left_title, left_val, left_cb, right_title, right_val, right_cb):
        grid = Gtk.Grid(column_spacing=8, row_spacing=2, halign=Gtk.Align.CENTER)
        for col, (t, v, cb) in enumerate(((left_title, left_val, left_cb),
                                          (right_title, right_val, right_cb))):
            if t is None:
                continue
            l = Gtk.Label(label=t)
            l.get_style_context().add_class("dica")
            grid.attach(l, col, 0, 1, 1)
            grid.attach(_vscale(v, cb), col, 1, 1, 1)
        return grid

    def _channel_column(self, ch):
        cid = ch["id"]
        box, lab = self._column(ch["name"])
        out_txt = "→ SC8 Chat" if ch.get("output") == C.SC8_CHAT else "→ SC8 Game"
        hint = Gtk.Label(label=out_txt)
        hint.get_style_context().add_class("dica")
        box.pack_start(hint, False, False, 0)
        box.pack_start(self._slider_pair(
            "Fone", ch["fone"], lambda v: self.set_chan(cid, "fone", v),
            "Live", ch["live"], lambda v: self.set_chan(cid, "live", v)), False, False, 0)

        mute = Gtk.ToggleButton(label="Mudo")
        mute.set_active(ch["mute"])
        mute.connect("toggled", lambda w: self.set_chan(cid, "mute", w.get_active()))
        box.pack_start(mute, False, False, 0)

        progs_lab = Gtk.Label(label="Programas:", xalign=0)
        progs_lab.get_style_context().add_class("dica")
        box.pack_start(progs_lab, False, False, 0)
        pbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.prog_boxes[cid] = pbox
        box.pack_start(pbox, True, True, 0)

        if cid not in C.BUILTIN_IDS:
            opts = Gtk.Box(spacing=4)
            sw = Gtk.ComboBoxText()
            sw.append(C.SC8_GAME, "Fone: SC8 Game")
            sw.append(C.SC8_CHAT, "Fone: SC8 Chat")
            sw.set_active_id(ch.get("output", C.SC8_GAME))
            sw.connect("changed", lambda w: self.set_output(cid, w.get_active_id()))
            rm = Gtk.Button.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.BUTTON)
            rm.set_tooltip_text("Remover canal")
            rm.connect("clicked", lambda *_: self.on_remove_channel(cid))
            opts.pack_start(sw, True, True, 0)
            opts.pack_start(rm, False, False, 0)
            box.pack_end(opts, False, False, 0)
        return box

    def _mic_column(self):
        box, _ = self._column("Mic SC8")
        hint = Gtk.Label(label="→ SC8 Stream")
        hint.get_style_context().add_class("dica")
        box.pack_start(hint, False, False, 0)
        box.pack_start(self._slider_pair(
            None, 0, None,
            "Live", self.cfg["mic_live"], lambda v: self.set_global("mic_live", v)), False, False, 0)
        mute = Gtk.ToggleButton(label="Mudo na live")
        mute.set_active(self.cfg["mic_live_mute"])
        mute.connect("toggled", lambda w: self.set_global("mic_live_mute", w.get_active()))
        box.pack_start(mute, False, False, 0)
        return box

    def _master_column(self):
        box, _ = self._column("MASTER", master=True)
        hint = Gtk.Label(label="Fone: Chat + Game\nLive: SC8 Stream", justify=Gtk.Justification.CENTER)
        hint.get_style_context().add_class("dica")
        box.pack_start(hint, False, False, 0)
        box.pack_start(self._slider_pair(
            "Fone", self.cfg["master"], lambda v: self.set_global("master", v),
            "Live", self.cfg["live_master"], lambda v: self.set_global("live_master", v)),
            False, False, 0)
        mute = Gtk.ToggleButton(label="Mudo geral")
        mute.set_active(self.cfg["master_mute"])
        mute.connect("toggled", lambda w: self.set_global("master_mute", w.get_active()))
        box.pack_start(mute, False, False, 0)
        return box

    # ---------- ações ----------
    def _node(self, name):
        return self.ids.get(name)

    def _save_later(self):
        if self.save_src:
            GLib.source_remove(self.save_src)
        self.save_src = GLib.timeout_add(400, self._save_now)

    def _save_now(self):
        self.save_src = None
        C.save(self.cfg)
        return False

    def set_chan(self, cid, key, value):
        ch = next(c for c in self.cfg["channels"] if c["id"] == cid)
        ch[key] = value
        if key == "fone":
            nid = self._node(C.fone_name(cid))
            self.deb.put(("f", cid), lambda: nid and pw.set_volume(nid, value))
        elif key == "live":
            nid = self._node(C.live_name(cid))
            self.deb.put(("l", cid), lambda: nid and pw.set_volume(nid, value))
        elif key == "mute":
            nid = self._node(C.sink_name(cid))
            self.deb.put(("m", cid), lambda: nid and pw.set_mute(nid, value))
        self._save_later()

    def set_global(self, key, value):
        self.cfg[key] = value
        if key in ("master", "master_mute"):
            ids = [self._node(b) for b in C.BUS_FOR.values()]
            fn = pw.set_volume if key == "master" else pw.set_mute
            self.deb.put(key, lambda: [fn(i, value) for i in ids if i])
        elif key == "live_master":
            nid = self._node(C.STREAM_SOURCE)
            self.deb.put(key, lambda: nid and pw.set_volume(nid, value))
        elif key == "mic_live":
            nid = self._node(C.MIC_LIVE)
            self.deb.put(key, lambda: nid and pw.set_volume(nid, value))
        elif key == "mic_live_mute":
            nid = self._node(C.MIC_LIVE)
            self.deb.put(key, lambda: nid and pw.set_mute(nid, value))
        self._save_later()

    def set_output(self, cid, out):
        ch = next(c for c in self.cfg["channels"] if c["id"] == cid)
        if ch.get("output") == out:
            return
        ch["output"] = out
        self.apply_structure()

    def on_add_channel(self, *_):
        extras = [c for c in self.cfg["channels"] if c["id"] not in C.BUILTIN_IDS]
        if len(extras) >= C.MAX_EXTRA_CHANNELS:
            self._msg("Limite de %d canais extras atingido." % C.MAX_EXTRA_CHANNELS)
            return
        dlg = Gtk.Dialog(title="Novo canal", transient_for=self, modal=True)
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Adicionar", Gtk.ResponseType.OK)
        area = dlg.get_content_area()
        area.set_spacing(6)
        area.set_border_width(10)
        entry = Gtk.Entry(placeholder_text="Nome do canal (ex.: OBS, Alertas)")
        entry.set_activates_default(True)
        dlg.set_default_response(Gtk.ResponseType.OK)
        out = Gtk.ComboBoxText()
        out.append(C.SC8_GAME, "Fone pela saída SC8 Game")
        out.append(C.SC8_CHAT, "Fone pela saída SC8 Chat")
        out.set_active_id(C.SC8_GAME)
        area.add(entry)
        area.add(out)
        area.add(Gtk.Label(label="O áudio vai reiniciar por 1–2 segundos.", xalign=0))
        dlg.show_all()
        resp = dlg.run()
        name = entry.get_text().strip()
        output = out.get_active_id()
        dlg.destroy()
        if resp != Gtk.ResponseType.OK or not name:
            return
        base = C.slugify(name)
        cid, n = base, 2
        existing = {c["id"] for c in self.cfg["channels"]}
        while cid in existing:
            cid, n = "%s_%d" % (base, n), n + 1
        self.cfg["channels"].append({"id": cid, "name": name, "output": output,
                                     "fone": 1.0, "live": 1.0, "mute": False})
        self.apply_structure()

    def on_remove_channel(self, cid):
        ch = next(c for c in self.cfg["channels"] if c["id"] == cid)
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                              buttons=Gtk.ButtonsType.YES_NO,
                              text="Remover o canal \"%s\"?" % ch["name"])
        d.format_secondary_text("Os programas dele voltam para o canal Sistema. "
                                "O áudio vai reiniciar por 1–2 segundos.")
        r = d.run()
        d.destroy()
        if r != Gtk.ResponseType.YES:
            return
        self.cfg["channels"] = [c for c in self.cfg["channels"] if c["id"] != cid]
        self.cfg["rules"] = [r for r in self.cfg["rules"] if r.get("channel") != cid]
        self.apply_structure()

    def apply_structure(self):
        C.save(self.cfg)
        self.build()
        self._msg("Aplicando… reiniciando o PipeWire")

        def work():
            if pwconf.write(self.cfg):
                pwconf.restart_pipewire()
            import time
            time.sleep(3)
            pw.ensure_stream_links()
            pw.apply_volumes(self.cfg)
            GLib.idle_add(self.refresh)
        threading.Thread(target=work, daemon=True).start()

    def move_prog(self, stream, cid, remember):
        def work():
            ok = pw.move_stream(stream["id"], C.sink_name(cid))
            GLib.idle_add(self.refresh)
            if not ok:
                GLib.idle_add(self._msg, "Não consegui mover %s." % stream["label"])
        if remember:
            C.remember(self.cfg, stream["props"], cid)
            C.save(self.cfg)
        threading.Thread(target=work, daemon=True).start()

    def _msg(self, text):
        self.status.set_text(text)
        return False

    # ---------- atualização ----------
    def _tick(self):
        if self.is_visible():
            self.refresh()
        return True

    def refresh(self):
        def work():
            objs = pw.dump()
            ns = pw.nodes(objs)
            streams = pw.app_streams(objs)
            GLib.idle_add(self._apply_refresh, ns, streams)
        threading.Thread(target=work, daemon=True).start()
        return False

    def _apply_refresh(self, ns, streams):
        self.ids = {k: v[0] for k, v in ns.items()}
        missing = [n for n in (C.SC8_CHAT, C.SC8_GAME, C.STREAM_SOURCE) if n not in ns]
        if missing:
            self.status.set_text("Atenção: não encontrei %s. A SC8 está conectada? "
                                 "Rode o install.sh se for a primeira vez." % ", ".join(missing))
        else:
            self.status.set_text("SC8 conectada · OBS: use a fonte de entrada de áudio \"SC8 Stream\"")
        by_target = {}
        for s in streams:
            by_target.setdefault(s["target"], []).append(s)
        names = [(c["id"], c["name"]) for c in self.cfg["channels"]]
        for cid, pbox in self.prog_boxes.items():
            for c in pbox.get_children():
                pbox.remove(c)
            lst = by_target.get(C.sink_name(cid), [])
            if not lst:
                l = Gtk.Label(label="(nenhum)", xalign=0)
                l.get_style_context().add_class("dica")
                pbox.pack_start(l, False, False, 0)
            for s in lst:
                pbox.pack_start(self._prog_button(s, cid, names), False, False, 0)
            pbox.show_all()
        return False

    def _prog_button(self, s, cid, names):
        btn = Gtk.MenuButton(label=s["label"][:22])
        btn.set_tooltip_text("%s\n%s" % (s["label"], s["media"]))
        btn.get_style_context().add_class("prog")
        menu = Gtk.Menu()
        for other_id, other_name in names:
            if other_id == cid:
                continue
            for remember in (False, True):
                txt = ("Mover e lembrar → %s" if remember else "Mover → %s") % other_name
                it = Gtk.MenuItem(label=txt)
                it.connect("activate", lambda _w, o=other_id, r=remember: self.move_prog(s, o, r))
                menu.append(it)
        menu.show_all()
        btn.set_popup(menu)
        return btn


class MixerApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="io.github.opensc8.Mixer")

    def do_activate(self):
        win = self.props.active_window or MixerWindow(self)
        win.show_all()
        win.present()


def main():
    app = MixerApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
