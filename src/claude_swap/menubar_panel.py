"""Click popover for the macOS menu bar — drawn usage bars, not a text menu.

Imported only from ``menubar.run`` after rumps/AppKit are available. The
status item stays a short title; this panel is what opens on click.
"""

from __future__ import annotations

import objc
from AppKit import (
    NSAppearanceNameAqua,
    NSAppearanceNameDarkAqua,
    NSBezierPath,
    NSButton,
    NSButtonTypeSwitch,
    NSColor,
    NSFont,
    NSFontWeightMedium,
    NSFontWeightRegular,
    NSFontWeightSemibold,
    NSImage,
    NSImageLeft,
    NSImageSymbolConfiguration,
    NSImageSymbolScaleMedium,
    NSLineBreakByTruncatingTail,
    NSPopover,
    NSPopoverBehaviorTransient,
    NSRectEdgeMinY,
    NSTextField,
    NSTrackingArea,
    NSTrackingActiveAlways,
    NSTrackingMouseEnteredAndExited,
    NSView,
    NSViewController,
    NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectMaterialMenu,
    NSVisualEffectStateActive,
    NSVisualEffectView,
)
from Foundation import NSMakeRect, NSObject, NSPointInRect

from claude_swap.menubar import panel_accounts
from claude_swap.tui.theme import (
    ACCENT,
    ACCENT_LIGHT,
    CRIT_PCT,
    FOREGROUND,
    FOREGROUND_LIGHT,
    MUTED,
    MUTED_LIGHT,
    SEV_CRIT,
    SEV_CRIT_LIGHT,
    SEV_OK,
    SEV_OK_LIGHT,
    SEV_WARN,
    SEV_WARN_LIGHT,
    TRACK,
    TRACK_LIGHT,
    WARN_PCT,
)

STATUS_SYMBOL_NAME = "arrow.triangle.2.circlepath"
STATUS_AUTOSAVE_NAME = "com.cswap.menubar"


def pin_status_item(nsstatusitem) -> None:
    """Remember Cmd-drag order across launches.

    macOS has no API to sit next to another app's extra (e.g. Claude). Setting
    an autosave name is what makes a user-placed position actually stick.
    """
    nsstatusitem.setAutosaveName_(STATUS_AUTOSAVE_NAME)


def apply_status_symbol(nsstatusitem) -> None:
    """Put the circular-swap SF Symbol on the status item as a template image.

    Template mode tints with the menu bar (light/dark). Title text is separate
    and sits to the right of the symbol.
    """
    img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
        STATUS_SYMBOL_NAME, "Switch Claude account"
    )
    if img is None:
        return
    config = NSImageSymbolConfiguration.configurationWithPointSize_weight_scale_(
        13.0, NSFontWeightRegular, NSImageSymbolScaleMedium
    )
    if config is not None:
        configured = img.imageWithSymbolConfiguration_(config)
        if configured is not None:
            img = configured
    img.setTemplate_(True)
    button = nsstatusitem.button()
    if button is not None:
        button.setImage_(img)
        button.setImagePosition_(NSImageLeft)
    else:
        nsstatusitem.setImage_(img)


PANEL_WIDTH = 312.0
PAD = 12.0
HEADER_H = 36.0
FOOTER_H = 38.0
CARD_GAP = 8.0
CARD_PAD = 11.0
CARD_RADIUS = 10.0
TITLE_H = 18.0
ROW_H = 22.0
BAR_H = 6.0
LABEL_W = 44.0
PCT_W = 36.0
COUNT_W = 52.0


def _hex(color: str, alpha: float = 1.0):
    h = color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, alpha)


def _is_dark(view) -> bool:
    try:
        name = view.effectiveAppearance().bestMatchFromAppearancesWithNames_(
            [NSAppearanceNameDarkAqua, NSAppearanceNameAqua]
        )
        return name == NSAppearanceNameDarkAqua
    except Exception:
        return True


def _palette(view) -> dict:
    if _is_dark(view):
        return {
            "fg": _hex(FOREGROUND),
            "muted": _hex(MUTED),
            "accent": _hex(ACCENT),
            "card": _hex("#ffffff", 0.06),
            "card_hover": _hex("#ffffff", 0.10),
            "card_active": _hex("#ffffff", 0.09),
            "ok": _hex(SEV_OK),
            "warn": _hex(SEV_WARN),
            "crit": _hex(SEV_CRIT),
            "track": _hex(TRACK),
            "hairline": _hex("#ffffff", 0.08),
        }
    return {
        "fg": _hex(FOREGROUND_LIGHT),
        "muted": _hex(MUTED_LIGHT),
        "accent": _hex(ACCENT_LIGHT),
        "card": _hex("#000000", 0.04),
        "card_hover": _hex("#000000", 0.07),
        "card_active": _hex("#000000", 0.06),
        "ok": _hex(SEV_OK_LIGHT),
        "warn": _hex(SEV_WARN_LIGHT),
        "crit": _hex(SEV_CRIT_LIGHT),
        "track": _hex(TRACK_LIGHT),
        "hairline": _hex("#000000", 0.08),
    }


def _sev(pct: float, pal: dict):
    if pct >= CRIT_PCT:
        return pal["crit"]
    if pct >= WARN_PCT:
        return pal["warn"]
    return pal["ok"]


def _label(text, font, color, frame, align="left"):
    field = NSTextField.alloc().initWithFrame_(frame)
    field.setStringValue_(text or "")
    field.setBezeled_(False)
    field.setBordered_(False)
    field.setDrawsBackground_(False)
    field.setEditable_(False)
    field.setSelectable_(False)
    field.setFont_(font)
    field.setTextColor_(color)
    field.setLineBreakMode_(NSLineBreakByTruncatingTail)
    if align == "right":
        field.setAlignment_(2)  # NSTextAlignmentRight
    elif align == "center":
        field.setAlignment_(1)
    return field


class _Trampoline(NSObject):
    """ObjC target that forwards ``act:`` to a Python callable."""

    def initWithCallback_(self, callback):
        self = objc.super(_Trampoline, self).init()
        if self is None:
            return None
        self._callback = callback
        return self

    def act_(self, sender):
        cb = getattr(self, "_callback", None)
        if cb:
            cb(sender)


class _BarView(NSView):
    def initWithPct_palette_threshold_(self, pct, pal, threshold):
        self = objc.super(_BarView, self).initWithFrame_(NSMakeRect(0, 0, 100, BAR_H))
        if self is None:
            return None
        self.pct = max(0.0, min(float(pct), 100.0))
        self.pal = pal
        self.threshold = threshold
        return self

    def isFlipped(self):
        return True

    def drawRect_(self, _rect):
        bounds = self.bounds()
        radius = bounds.size.height / 2.0
        track = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            bounds, radius, radius
        )
        self.pal["track"].setFill()
        track.fill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            bounds, radius, radius
        ).addClip()
        if self.pct > 0:
            width = max(bounds.size.height, bounds.size.width * self.pct / 100.0)
            fill_rect = NSMakeRect(0, 0, width, bounds.size.height)
            fill = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                fill_rect, radius, radius
            )
            _sev(self.pct, self.pal).setFill()
            fill.fill()
        if self.threshold:
            x = bounds.size.width * max(0.0, min(float(self.threshold), 100.0)) / 100.0
            self.pal["warn"].colorWithAlphaComponent_(0.7).setFill()
            NSBezierPath.bezierPathWithRect_(
                NSMakeRect(x - 0.5, 0, 1.0, bounds.size.height)
            ).fill()


class _CardView(NSView):
    def initWithCard_palette_onSwitch_(self, card, pal, on_switch):
        self = objc.super(_CardView, self).initWithFrame_(NSMakeRect(0, 0, 100, 40))
        if self is None:
            return None
        self.card = card
        self.pal = pal
        self.on_switch = on_switch
        self._hover = False
        self.setWantsLayer_(True)
        layer = self.layer()
        layer.setCornerRadius_(CARD_RADIUS)
        layer.setMasksToBounds_(True)
        self._apply_bg()
        return self

    def isFlipped(self):
        return True

    def _apply_bg(self):
        if self._hover:
            color = self.pal["card_hover"]
        elif self.card.get("active"):
            color = self.pal["card_active"]
        else:
            color = self.pal["card"]
        self.layer().setBackgroundColor_(color.CGColor())

    def updateTrackingAreas(self):
        areas = list(self.trackingAreas() or [])
        for area in areas:
            self.removeTrackingArea_(area)
        options = NSTrackingMouseEnteredAndExited | NSTrackingActiveAlways
        area = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            self.bounds(), options, self, None
        )
        self.addTrackingArea_(area)
        objc.super(_CardView, self).updateTrackingAreas()

    def mouseEntered_(self, _event):
        self._hover = True
        self._apply_bg()

    def mouseExited_(self, _event):
        self._hover = False
        self._apply_bg()

    def hitTest_(self, point):
        # Labels sit on top of the card; route every hit to the card so a
        # click anywhere on the row switches.
        if objc.super(_CardView, self).hitTest_(point) is not None:
            return self
        return None

    def mouseUp_(self, event):
        loc = self.convertPoint_fromView_(event.locationInWindow(), None)
        if not NSPointInRect(loc, self.bounds()):
            return
        if self.on_switch and not self.card.get("disabled"):
            self.on_switch(self.card["num"])


class _RootView(NSVisualEffectView):
    def isFlipped(self):
        return True


class _PanelController(NSViewController):
    pass


class MenuBarPanel:
    """Status-item click target: transient popover with account usage bars."""

    def __init__(self, *, on_switch, on_rotate, on_best, on_toggle_auto, on_more, auto_enabled, snapshot, threshold):
        self._on_switch = on_switch
        self._on_rotate = on_rotate
        self._on_best = on_best
        self._on_toggle_auto = on_toggle_auto
        self._on_more = on_more
        self._auto_enabled = auto_enabled
        self._snapshot = snapshot
        self._threshold = threshold
        self._item = None
        self._popover = None
        self._controller = None
        self._tramps: list = []
        self._toggle_tramp = None

    def attach(self, nsstatusitem) -> None:
        self._item = nsstatusitem
        nsstatusitem.setMenu_(None)
        button = nsstatusitem.button()
        if button is None:
            return
        self._toggle_tramp = _Trampoline.alloc().initWithCallback_(self.toggle)
        button.setTarget_(self._toggle_tramp)
        button.setAction_("act:")
        self._popover = NSPopover.alloc().init()
        self._popover.setBehavior_(NSPopoverBehaviorTransient)
        self._popover.setAnimates_(True)

    def is_shown(self) -> bool:
        return bool(self._popover is not None and self._popover.isShown())

    def close(self) -> None:
        if self._popover is not None and self._popover.isShown():
            self._popover.performClose_(None)

    def toggle(self, _sender=None) -> None:
        if self._popover is None or self._item is None:
            return
        if self._popover.isShown():
            self._popover.performClose_(None)
            return
        self.reload()
        button = self._item.button()
        if button is None:
            return
        self._popover.showRelativeToRect_ofView_preferredEdge_(
            button.bounds(), button, NSRectEdgeMinY
        )

    def reload(self) -> None:
        if self._popover is None:
            return
        view = self._build()
        controller = _PanelController.alloc().init()
        controller.setView_(view)
        self._controller = controller
        self._popover.setContentSize_(view.frame().size)
        self._popover.setContentViewController_(controller)

    def _tramp(self, fn) -> _Trampoline:
        t = _Trampoline.alloc().initWithCallback_(fn)
        self._tramps.append(t)
        return t

    def _build(self):
        self._tramps = []
        cards = panel_accounts(self._snapshot())
        # Probe palette from the status button so the first paint matches the bar.
        probe = self._item.button() if self._item is not None else None
        pal = _palette(probe) if probe is not None else _palette(_RootView.alloc().init())

        body_h = 0.0
        if not cards:
            body_h = 48.0
        else:
            for card in cards:
                n = max(len(card["windows"]), 1 if card["note"] else 0, 1)
                body_h += CARD_PAD * 2 + TITLE_H + 6 + n * ROW_H
            body_h += CARD_GAP * (len(cards) - 1)

        height = PAD + HEADER_H + 4 + body_h + PAD + FOOTER_H
        root = _RootView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH, height))
        root.setMaterial_(NSVisualEffectMaterialMenu)
        root.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        root.setState_(NSVisualEffectStateActive)

        font_title = NSFont.systemFontOfSize_weight_(13, NSFontWeightSemibold)
        font_body = NSFont.systemFontOfSize_weight_(12, NSFontWeightRegular)
        font_small = NSFont.systemFontOfSize_weight_(11, NSFontWeightRegular)
        font_digits = NSFont.monospacedDigitSystemFontOfSize_weight_(11, NSFontWeightMedium)
        font_label = NSFont.monospacedDigitSystemFontOfSize_weight_(11, NSFontWeightRegular)

        # Header
        root.addSubview_(
            _label("cswap", font_title, pal["fg"], NSMakeRect(PAD, PAD, 120, 20))
        )
        auto = NSButton.alloc().initWithFrame_(
            NSMakeRect(PANEL_WIDTH - PAD - 118, PAD + 1, 118, 22)
        )
        auto.setButtonType_(NSButtonTypeSwitch)
        auto.setTitle_("Auto-switch")
        auto.setFont_(font_small)
        auto.setState_(1 if self._auto_enabled() else 0)
        auto.setTarget_(self._tramp(self._on_toggle_auto))
        auto.setAction_("act:")
        root.addSubview_(auto)

        y = PAD + HEADER_H + 4
        inner_w = PANEL_WIDTH - PAD * 2

        if not cards:
            root.addSubview_(
                _label(
                    "No managed accounts",
                    font_body,
                    pal["muted"],
                    NSMakeRect(PAD, y, inner_w, 20),
                )
            )
        else:
            for card in cards:
                n = max(len(card["windows"]), 1 if card["note"] else 0, 1)
                card_h = CARD_PAD * 2 + TITLE_H + 6 + n * ROW_H
                card_view = _CardView.alloc().initWithCard_palette_onSwitch_(
                    card, pal, self._on_switch
                )
                card_view.setFrame_(NSMakeRect(PAD, y, inner_w, card_h))
                if card.get("disabled"):
                    card_view.setAlphaValue_(0.45)

                if card.get("active"):
                    accent = NSView.alloc().initWithFrame_(
                        NSMakeRect(0, 0, 3, card_h)
                    )
                    accent.setWantsLayer_(True)
                    accent.layer().setBackgroundColor_(pal["accent"].CGColor())
                    card_view.addSubview_(accent)

                title = card["title"]
                if card.get("disabled"):
                    title = f"{title}  (disabled)"
                card_view.addSubview_(
                    _label(
                        title,
                        font_title,
                        pal["fg"],
                        NSMakeRect(CARD_PAD + 6, CARD_PAD, inner_w - CARD_PAD * 2 - 52, TITLE_H),
                    )
                )
                if card.get("active"):
                    badge = _label(
                        "active",
                        font_small,
                        pal["accent"],
                        NSMakeRect(inner_w - CARD_PAD - 48, CARD_PAD + 1, 48, TITLE_H),
                        align="right",
                    )
                    card_view.addSubview_(badge)

                row_y = CARD_PAD + TITLE_H + 6
                if card.get("note") and not card["windows"]:
                    card_view.addSubview_(
                        _label(
                            card["note"],
                            font_small,
                            pal["muted"],
                            NSMakeRect(CARD_PAD + 6, row_y, inner_w - CARD_PAD * 2 - 8, ROW_H),
                        )
                    )
                else:
                    bar_x = CARD_PAD + 6 + LABEL_W
                    bar_w = inner_w - CARD_PAD * 2 - 8 - LABEL_W - PCT_W - COUNT_W
                    for win in card["windows"]:
                        card_view.addSubview_(
                            _label(
                                win["label"],
                                font_label,
                                pal["muted"],
                                NSMakeRect(CARD_PAD + 6, row_y - 2, LABEL_W - 4, ROW_H),
                            )
                        )
                        bar = _BarView.alloc().initWithPct_palette_threshold_(
                            win["pct"], pal, self._threshold()
                        )
                        bar.setFrame_(
                            NSMakeRect(bar_x, row_y + (ROW_H - BAR_H) / 2 - 2, bar_w, BAR_H)
                        )
                        card_view.addSubview_(bar)
                        pct_color = _sev(win["pct"], pal)
                        card_view.addSubview_(
                            _label(
                                f"{win['pct']:.0f}%",
                                font_digits,
                                pct_color,
                                NSMakeRect(bar_x + bar_w + 6, row_y - 2, PCT_W, ROW_H),
                            )
                        )
                        suffix = win.get("countdown") or ""
                        if win.get("maxed"):
                            suffix = "max"
                        elif win.get("ahead") and not suffix:
                            suffix = "ahead"
                        card_view.addSubview_(
                            _label(
                                suffix,
                                font_small,
                                pal["muted"],
                                NSMakeRect(
                                    bar_x + bar_w + 6 + PCT_W, row_y - 2, COUNT_W - 8, ROW_H
                                ),
                                align="right",
                            )
                        )
                        row_y += ROW_H

                root.addSubview_(card_view)
                y += card_h + CARD_GAP

        # Footer
        fy = height - FOOTER_H
        hairline = NSView.alloc().initWithFrame_(
            NSMakeRect(PAD, fy, inner_w, 1)
        )
        hairline.setWantsLayer_(True)
        hairline.layer().setBackgroundColor_(pal["hairline"].CGColor())
        root.addSubview_(hairline)

        def _footer_btn(title, x, w, cb):
            btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, fy + 8, w, 22))
            btn.setTitle_(title)
            btn.setBezelStyle_(1)  # rounded
            btn.setControlSize_(1)  # small
            btn.setFont_(font_small)
            btn.setTarget_(self._tramp(cb))
            btn.setAction_("act:")
            root.addSubview_(btn)

        _footer_btn("Rotate", PAD, 72, self._on_rotate)
        _footer_btn("Best", PAD + 80, 64, self._on_best)
        _footer_btn("More", PANEL_WIDTH - PAD - 72, 72, self._on_more)

        return root
