"""Click popover for the macOS menu bar — drawn usage bars, not a text menu.

Imported only from ``menubar.run`` after rumps/AppKit are available. The
status item stays a short title; this panel is what opens on click.
"""

from __future__ import annotations

import objc
from AppKit import (
    NSApp,
    NSAppearance,
    NSAppearanceNameAqua,
    NSAppearanceNameDarkAqua,
    NSApplication,
    NSBezierPath,
    NSButton,
    NSButtonTypeSwitch,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSFontWeightMedium,
    NSFontWeightRegular,
    NSFontWeightSemibold,
    NSForegroundColorAttributeName,
    NSGraphicsContext,
    NSLineBreakByTruncatingTail,
    NSNoImage,
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
from Foundation import (
    NSAttributedString,
    NSDistributedNotificationCenter,
    NSMakeRect,
    NSObject,
    NSPointInRect,
    NSUserDefaults,
)

from claude_swap.menubar import panel_accounts, resolve_popover_theme, status_item_length
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

STATUS_AUTOSAVE_NAME = "com.cswap.menubar"


def pin_status_item(nsstatusitem) -> None:
    """Remember Cmd-drag order across launches.

    macOS has no API to sit next to another app's extra (e.g. Claude). Setting
    an autosave name is what makes a user-placed position actually stick.
    """
    nsstatusitem.setAutosaveName_(STATUS_AUTOSAVE_NAME)


def fit_status_item(nsstatusitem, *, compact: bool) -> None:
    """Shrink the extra to the title when the leading icon is off.

    AppKit's default title item is ~10pt inset on each side; with no icon
    that left gap is empty. Measuring the title and setting length keeps
    about 3pt per side.
    """
    button = nsstatusitem.button()
    if button is None:
        return
    if compact:
        try:
            button.setImagePosition_(NSNoImage)
        except Exception:
            pass
    title = str(button.title() or "")
    width = 0.0
    if title:
        font = button.font() or NSFont.menuBarFontOfSize_(0)
        width = (
            NSAttributedString.alloc()
            .initWithString_attributes_(title, {NSFontAttributeName: font})
            .size()
            .width
        )
    nsstatusitem.setLength_(status_item_length(width, compact=compact))


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
BAR_MAX_W = 80.0
LABEL_W = 44.0
PCT_W = 48.0
COUNT_W = 60.0
COL_GAP = 8.0


def _hex(color: str, alpha: float = 1.0):
    h = color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, alpha)


# Dynamic NSColor providers are ObjC blocks over Python callables; keep them
# rooted so the GC cannot collect a provider the catalog still calls.
_DYNAMIC_PROVIDERS: list = []
_PALETTE = None


def _dynamic(light_hex, dark_hex, light_alpha=1.0, dark_alpha=1.0, *, name=None):
    def provider(appearance):
        match = appearance.bestMatchFromAppearancesWithNames_(
            [NSAppearanceNameDarkAqua, NSAppearanceNameAqua]
        )
        if match == NSAppearanceNameDarkAqua:
            return _hex(dark_hex, dark_alpha)
        return _hex(light_hex, light_alpha)

    _DYNAMIC_PROVIDERS.append(provider)
    return NSColor.colorWithName_dynamicProvider_(name, provider)


def _colors() -> dict:
    """TUI light/dark tokens that resolve against the drawing appearance."""
    global _PALETTE
    if _PALETTE is None:
        _PALETTE = {
            "fg": _dynamic(FOREGROUND_LIGHT, FOREGROUND, name="cswap.fg"),
            "muted": _dynamic(MUTED_LIGHT, MUTED, name="cswap.muted"),
            "accent": _dynamic(ACCENT_LIGHT, ACCENT, name="cswap.accent"),
            "card": _dynamic("#000000", "#ffffff", 0.04, 0.06, name="cswap.card"),
            "card_hover": _dynamic(
                "#000000", "#ffffff", 0.07, 0.10, name="cswap.cardHover"
            ),
            "card_active": _dynamic(
                "#000000", "#ffffff", 0.06, 0.09, name="cswap.cardActive"
            ),
            "ok": _dynamic(SEV_OK_LIGHT, SEV_OK, name="cswap.ok"),
            "warn": _dynamic(SEV_WARN_LIGHT, SEV_WARN, name="cswap.warn"),
            "crit": _dynamic(SEV_CRIT_LIGHT, SEV_CRIT, name="cswap.crit"),
            "track": _dynamic(TRACK_LIGHT, TRACK, name="cswap.track"),
            "hairline": _dynamic(
                "#000000", "#ffffff", 0.08, 0.08, name="cswap.hairline"
            ),
        }
    return _PALETTE


def _system_popover_appearance():
    """Named Aqua/DarkAqua for the popover, matching System Settings."""
    try:
        app_name = NSApplication.sharedApplication().effectiveAppearance().name()
    except Exception:
        app_name = None
    try:
        style = NSUserDefaults.standardUserDefaults().stringForKey_("AppleInterfaceStyle")
    except Exception:
        style = None
    theme = resolve_popover_theme(
        app_appearance_name=app_name, interface_style=style
    )
    key = NSAppearanceNameDarkAqua if theme == "dark" else NSAppearanceNameAqua
    return NSAppearance.appearanceNamed_(key)


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


class _AppearanceObserver(NSObject):
    """KVO + distributed-notification shim so the popover tracks Dark Mode."""

    def initWithCallback_(self, callback):
        self = objc.super(_AppearanceObserver, self).init()
        if self is None:
            return None
        self._callback = callback
        return self

    def observeValueForKeyPath_ofObject_change_context_(self, keyPath, obj, change, context):
        cb = getattr(self, "_callback", None)
        if cb:
            cb()

    def themeChanged_(self, _note):
        cb = getattr(self, "_callback", None)
        if cb:
            cb()


class _FillView(NSView):
    """1px hairline (or other strip) that re-resolves its fill on appearance changes."""

    def initWithColor_(self, color):
        self = objc.super(_FillView, self).initWithFrame_(NSMakeRect(0, 0, 1, 1))
        if self is None:
            return None
        self._fill = color
        return self

    def isFlipped(self):
        return True

    def viewDidChangeEffectiveAppearance(self):
        objc.super(_FillView, self).viewDidChangeEffectiveAppearance()
        self.setNeedsDisplay_(True)

    def drawRect_(self, _rect):
        self._fill.setFill()
        NSBezierPath.bezierPathWithRect_(self.bounds()).fill()


class _BarView(NSView):
    def initWithPct_threshold_(self, pct, threshold):
        self = objc.super(_BarView, self).initWithFrame_(NSMakeRect(0, 0, 100, BAR_H))
        if self is None:
            return None
        self.pct = max(0.0, min(float(pct), 100.0))
        self.threshold = threshold
        return self

    def isFlipped(self):
        return True

    def viewDidChangeEffectiveAppearance(self):
        objc.super(_BarView, self).viewDidChangeEffectiveAppearance()
        self.setNeedsDisplay_(True)

    def drawRect_(self, _rect):
        pal = _colors()
        bounds = self.bounds()
        radius = bounds.size.height / 2.0
        track = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            bounds, radius, radius
        )
        pal["track"].setFill()
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
            _sev(self.pct, pal).setFill()
            fill.fill()
        if self.threshold:
            x = bounds.size.width * max(0.0, min(float(self.threshold), 100.0)) / 100.0
            pal["warn"].colorWithAlphaComponent_(0.7).setFill()
            NSBezierPath.bezierPathWithRect_(
                NSMakeRect(x - 0.5, 0, 1.0, bounds.size.height)
            ).fill()


class _CardView(NSView):
    def initWithCard_onSwitch_(self, card, on_switch):
        self = objc.super(_CardView, self).initWithFrame_(NSMakeRect(0, 0, 100, 40))
        if self is None:
            return None
        self.card = card
        self.on_switch = on_switch
        self._hover = False
        return self

    def isFlipped(self):
        return True

    def viewDidChangeEffectiveAppearance(self):
        objc.super(_CardView, self).viewDidChangeEffectiveAppearance()
        self.setNeedsDisplay_(True)

    def drawRect_(self, _rect):
        pal = _colors()
        if self._hover:
            color = pal["card_hover"]
        elif self.card.get("active"):
            color = pal["card_active"]
        else:
            color = pal["card"]
        bounds = self.bounds()
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            bounds, CARD_RADIUS, CARD_RADIUS
        )
        color.setFill()
        path.fill()
        if self.card.get("active"):
            NSGraphicsContext.saveGraphicsState()
            path.addClip()
            pal["accent"].setFill()
            NSBezierPath.bezierPathWithRect_(
                NSMakeRect(0, 0, 3, bounds.size.height)
            ).fill()
            NSGraphicsContext.restoreGraphicsState()

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
        self.setNeedsDisplay_(True)

    def mouseExited_(self, _event):
        self._hover = False
        self.setNeedsDisplay_(True)

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
        self._appearance_obs = None

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
        self._sync_popover_appearance()
        self._watch_appearance()

    def _watch_appearance(self) -> None:
        if self._appearance_obs is not None:
            return
        obs = _AppearanceObserver.alloc().initWithCallback_(self._on_system_appearance)
        self._appearance_obs = obs
        try:
            NSApp.addObserver_forKeyPath_options_context_(
                obs, "effectiveAppearance", 1, None
            )
        except Exception:
            pass
        try:
            NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(
                obs,
                "themeChanged:",
                "AppleInterfaceThemeChangedNotification",
                None,
            )
        except Exception:
            pass

    def _sync_popover_appearance(self) -> None:
        if self._popover is None:
            return
        try:
            self._popover.setAppearance_(_system_popover_appearance())
        except Exception:
            pass

    def _on_system_appearance(self) -> None:
        self._sync_popover_appearance()
        if self.is_shown():
            self.reload()

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
        self._sync_popover_appearance()
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
        pal = _colors()

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
        auto.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                "Auto-switch",
                {
                    NSFontAttributeName: font_small,
                    NSForegroundColorAttributeName: pal["fg"],
                },
            )
        )
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
                card_view = _CardView.alloc().initWithCard_onSwitch_(
                    card, self._on_switch
                )
                card_view.setFrame_(NSMakeRect(PAD, y, inner_w, card_h))
                if card.get("disabled"):
                    card_view.setAlphaValue_(0.45)

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
                    label_x = CARD_PAD + 6
                    count_x = inner_w - CARD_PAD - COUNT_W
                    pct_x = count_x - COL_GAP - PCT_W
                    bar_x = label_x + LABEL_W
                    bar_w = min(BAR_MAX_W, max(24.0, pct_x - COL_GAP - bar_x))
                    for win in card["windows"]:
                        card_view.addSubview_(
                            _label(
                                win["label"],
                                font_label,
                                pal["muted"],
                                NSMakeRect(label_x, row_y - 2, LABEL_W - 4, ROW_H),
                            )
                        )
                        bar = _BarView.alloc().initWithPct_threshold_(
                            win["pct"], self._threshold()
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
                                NSMakeRect(pct_x, row_y - 2, PCT_W, ROW_H),
                                align="right",
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
                                NSMakeRect(count_x, row_y - 2, COUNT_W, ROW_H),
                                align="right",
                            )
                        )
                        row_y += ROW_H

                root.addSubview_(card_view)
                y += card_h + CARD_GAP

        # Footer
        fy = height - FOOTER_H
        hairline = _FillView.alloc().initWithColor_(pal["hairline"])
        hairline.setFrame_(NSMakeRect(PAD, fy, inner_w, 1))
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
