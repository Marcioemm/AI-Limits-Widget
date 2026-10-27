import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ai_limits_widget.ui import app, dynamic_island
from ai_limits_widget.ui.meters import CircularMeter
from ai_limits_widget.ui.theme import RED

RUN_TK_SMOKE = os.environ.get("AI_LIMITS_RUN_TK_SMOKE") == "1"


@unittest.skipUnless(RUN_TK_SMOKE, "smoke gráfico executado manualmente")
class CompactMeterTests(unittest.TestCase):
    @staticmethod
    def _provider(_profile):
        return SimpleNamespace(
            minimum_refresh_interval_seconds=0,
            read_limits=lambda: {"five_hour": None, "weekly": None},
            close=lambda: None,
        )

    def _finish_compact_animation(self, widget, timeout=1.0):
        heights = []
        deadline = time.perf_counter() + timeout
        while widget.compact_animation_after and time.perf_counter() < deadline:
            widget.root.update()
            heights.append(widget.root.winfo_height())
            time.sleep(0.005)
        widget.root.update()
        self.assertIsNone(widget.compact_animation_after)
        return heights

    def test_renders_segments_percentage_and_error_state(self):
        root = app.tk.Tk()
        try:
            meter = CircularMeter(root, app.ORANGE)
            meter.pack()
            root.update_idletasks()

            meter.set_data(29, None)
            self.assertEqual("71%", meter.itemcget(meter.find_all()[-1], "text"))
            # Contorno, 28 segmentos e texto central.
            self.assertEqual(30, len(meter.find_all()))

            meter.set_error("indisponível")
            self.assertEqual("—", meter.itemcget(meter.find_all()[-1], "text"))
            self.assertEqual(RED, meter.itemcget(meter.find_all()[0], "outline"))
        finally:
            root.destroy()

    def test_compact_battery_renders_five_segments_and_percentage(self):
        root = app.tk.Tk()
        try:
            meter = app.CompactBatteryMeter(root, app.ORANGE)
            meter.pack()
            root.update_idletasks()

            meter.set_data(17, None)
            self.assertEqual("83%", meter.itemcget(meter.find_all()[-1], "text"))
            # Corpo, terminal, cinco segmentos e texto central.
            self.assertEqual(8, len(meter.find_all()))

            meter.set_error("indisponível")
            self.assertEqual("—", meter.itemcget(meter.find_all()[-1], "text"))
            self.assertEqual(RED, meter.itemcget(meter.find_all()[0], "outline"))
        finally:
            root.destroy()

    def test_compact_island_expands_and_keeps_selected_profile_primary(self):
        profiles = [
            {"id": "codex-default", "provider": "codex", "label": "Padrão", "executable": None, "configDir": None},
            {"id": "claude-default", "provider": "claude", "label": "Padrão", "executable": None, "configDir": None},
            {"id": "gemini-default", "provider": "gemini", "label": "Padrão", "executable": None, "configDir": None},
        ]
        config = {
            "providers": ["codex", "claude", "gemini"],
            "refreshMinutes": 5,
            "layout": "compact",
            "compactPrimaryProfileId": "claude-default",
            "compactVisibleCount": 2,
            "startWithWindows": False,
            "executables": {"codex": None, "claude": None, "gemini": None},
            "profiles": profiles,
        }
        with (
            patch.object(app, "load_config", return_value=config),
            patch.object(app, "load_profiles", return_value=profiles),
            patch.object(app, "save_config", side_effect=lambda value: value),
            patch.object(app, "create_provider", side_effect=self._provider),
            patch.object(app, "profile_is_available", return_value=True),
            patch.object(app, "profile_unavailable_reason", return_value=None),
            patch.object(app.UsageWidget, "_poll_hover_target", return_value=None),
            patch.object(app.UsageWidget, "refresh", return_value=None),
        ):
            widget = app.UsageWidget()
            try:
                widget.root.update_idletasks()
                self.assertEqual("claude-default", widget.compact_meter_order[0][0]["id"])
                self.assertEqual("", widget.titlebar.winfo_manager())
                self.assertEqual(widget._compact_island_width(), widget.root.winfo_width())
                self.assertEqual(app.COMPACT_METER_WIDTH, int(widget.compact_meter_order[0][1].cget("width")))
                self.assertTrue(widget.compact_cells["codex-default"].winfo_manager())
                self.assertEqual("", widget.compact_cells["gemini-default"].winfo_manager())
                widget._render_profile_meters(
                    profiles[0],
                    None,
                    {"usedPercent": 7, "resetsAt": 1800600000},
                )
                codex_meter = widget.meters["codex-default"][0]
                self.assertEqual(93, codex_meter.percent)
                self.assertEqual("SEMANA", widget.compact_details["codex-default"]["window"])
                collapsed_x = widget.root.winfo_x()
                collapsed_y = widget.root.winfo_y()
                collapsed_height = widget.root.winfo_height()

                widget._expand_compact_island()
                self.assertIsNotNone(widget.compact_animation_after)
                expanding_heights = self._finish_compact_animation(widget)
                self.assertTrue(widget.compact_expanded)
                self.assertEqual(widget._compact_expanded_width(), widget.root.winfo_width())
                self.assertEqual(
                    collapsed_x + widget._compact_island_width(),
                    widget.root.winfo_x() + widget.root.winfo_width(),
                )
                self.assertEqual(collapsed_y, widget.root.winfo_y())
                self.assertFalse(widget.compact_expand_upward)
                self.assertGreater(widget.root.winfo_height(), collapsed_height)
                expanded_height = widget.root.winfo_height()
                self.assertEqual(sorted(expanding_heights), expanding_heights)
                meter_sizes = {
                    (meter.winfo_width(), meter.winfo_height()) for _profile, meter in widget.compact_meter_order
                }
                self.assertEqual(
                    {(app.COMPACT_METER_WIDTH, app.COMPACT_METER_HEIGHT)},
                    meter_sizes,
                )
                battery_shapes = {
                    tuple(meter.coords(meter.find_all()[0])) for _profile, meter in widget.compact_meter_order
                }
                self.assertEqual(1, len(battery_shapes))
                for profile, meter in widget.compact_meter_order:
                    widgets = widget.compact_detail_widgets[profile["id"]]
                    self.assertTrue(widgets["panel"].winfo_manager())
                    self.assertGreater(widgets["panel"].winfo_y(), meter.winfo_y())
                    self.assertNotIn("updated", widgets)
                self.assertEqual(
                    1,
                    len({cell.grid_info()["row"] for cell in widget.compact_cells.values()}),
                )
                for field in ("title", "window", "value", "reset"):
                    field_positions = {
                        profile_id: widgets[field].winfo_y()
                        for profile_id, widgets in widget.compact_detail_widgets.items()
                    }
                    self.assertEqual(1, len(set(field_positions.values())), (field, field_positions))
                self.assertIn(
                    "CLAUDE CODE",
                    widget.compact_detail_widgets["claude-default"]["title"].cget("text"),
                )

                # Inverte um recolhimento ainda em curso a partir da altura atual.
                widget._collapse_compact_island()
                reverse_deadline = time.perf_counter() + 0.08
                while time.perf_counter() < reverse_deadline:
                    widget.root.update()
                    time.sleep(0.005)
                reversing_height = widget.root.winfo_height()
                self.assertLess(reversing_height, expanded_height)
                self.assertGreater(reversing_height, collapsed_height)
                widget._expand_compact_island()
                reversed_heights = self._finish_compact_animation(widget)
                self.assertGreaterEqual(reversed_heights[0], reversing_height)
                self.assertEqual(expanded_height, widget.root.winfo_height())
                self.assertEqual(widget._compact_expanded_width(), widget.root.winfo_width())

                widget._collapse_compact_island()
                collapsing_heights = self._finish_compact_animation(widget)
                self.assertFalse(widget.compact_expanded)
                self.assertEqual(widget._compact_island_width(), widget.root.winfo_width())
                self.assertEqual(collapsed_x, widget.root.winfo_x())
                self.assertEqual(collapsed_y, widget.root.winfo_y())
                self.assertEqual(collapsed_height, widget.root.winfo_height())
                self.assertEqual(sorted(collapsing_heights, reverse=True), collapsing_heights)
                self.assertEqual(app.COMPACT_METER_WIDTH, int(widget.compact_meter_order[0][1].cget("width")))
                self.assertTrue(widget.compact_cells["codex-default"].winfo_manager())
                self.assertEqual(
                    "",
                    widget.compact_detail_widgets["claude-default"]["panel"].winfo_manager(),
                )

                # Pressionar para arrastar mantém a ilha compacta até soltar.
                widget._expand_compact_island(animate=False)
                widget.root.update_idletasks()
                drag_event = SimpleNamespace(
                    x_root=widget.root.winfo_x() + 10,
                    y_root=widget.root.winfo_y() + 10,
                )
                widget._start_drag(drag_event)
                self.assertTrue(widget.compact_pointer_pressed)
                self.assertFalse(widget.compact_expanded)
                self.assertIsNotNone(widget.compact_animation_after)
                drag_collapse_heights = self._finish_compact_animation(widget)
                self.assertEqual(collapsed_height, widget.root.winfo_height())
                self.assertEqual(sorted(drag_collapse_heights, reverse=True), drag_collapse_heights)
                widget._schedule_compact_expand()
                self.assertIsNone(widget.compact_expand_after)
                with patch.object(widget.root, "winfo_containing", return_value=widget.compact_island):
                    widget._finish_drag(drag_event)
                self.assertFalse(widget.compact_pointer_pressed)
                self.assertIsNotNone(widget.compact_expand_after)
                widget._cancel_compact_timers()

                # Próximo ao rodapé, mantém a borda inferior e expande para cima.
                work_area = (0, 0, 1920, 500)
                bottom_y = 488
                widget.root.geometry(
                    f"{widget._compact_island_width()}x{collapsed_height}+100+{bottom_y - collapsed_height}"
                )
                widget.root.update_idletasks()
                anchored_meter_y = {
                    profile["id"]: meter.winfo_rooty() for profile, meter in widget.compact_meter_order[:2]
                }
                with patch.object(dynamic_island, "monitor_work_area", return_value=work_area):
                    widget._expand_compact_island()
                    self._finish_compact_animation(widget)
                    self.assertTrue(widget.compact_expand_upward)
                    self.assertLess(widget.root.winfo_y(), bottom_y - collapsed_height)
                    self.assertEqual(
                        bottom_y,
                        widget.root.winfo_y() + widget.root.winfo_height(),
                    )
                    for profile, meter in widget.compact_meter_order[:2]:
                        self.assertEqual(anchored_meter_y[profile["id"]], meter.winfo_rooty())
                        panel = widget.compact_detail_widgets[profile["id"]]["panel"]
                        self.assertLess(panel.winfo_rooty(), meter.winfo_rooty())
                    widget._collapse_compact_island()
                    self._finish_compact_animation(widget)
                self.assertEqual(bottom_y - collapsed_height, widget.root.winfo_y())
                self.assertEqual(collapsed_height, widget.root.winfo_height())

                settings = app.SettingsDialog(widget)
                settings.update_idletasks()
                self.assertEqual(
                    "claude-default",
                    settings.primary_choice_ids[settings.primary_profile_var.get()],
                )
                self.assertEqual(2, settings.compact_visible_count_var.get())
                settings.destroy()

                widget.toggle_layout()
                widget.root.update_idletasks()
                self.assertEqual("cards", widget.layout)
                self.assertTrue(widget.titlebar.winfo_manager())
                self.assertEqual(app.WINDOW_WIDTH, widget.root.winfo_width())

                widget.toggle_layout()
                widget.root.update_idletasks()
                self.assertEqual("compact", widget.layout)
                self.assertEqual("", widget.titlebar.winfo_manager())
            finally:
                widget.close()


if __name__ == "__main__":
    unittest.main()
