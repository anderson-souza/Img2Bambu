# Project File verification

**Verdict**: FAIL
**Proofs**: `proofs.md` at a27bdbe
**Verifier**: independent sub-agent (author != verifier)

## Checks

| Check | Test | Holds |
| --- | --- | --- |
| C1 | `test_gui_project.py` `test_menu_and_shortcuts` | yes |
| C2 | `test_gui_project.py` `test_reopen_restores_every_control` | yes |
| C3 | `test_gui_project.py` `test_reopen_restores_every_row` | yes |
| C4 | `test_project.py` `test_masks_equal_after_round_trip` | no - masks compared on one mostly dark/mid image only; a white cluster saves a file that does not load (F1) |
| C5 | `test_gui_project.py` `test_open_runs_no_detection` | yes |
| C6 | `test_project.py` `test_later_sample_edit_gives_same_masks` | yes |
| C7 | `test_gui_project.py` `test_later_redetection_carries_edited_rows` | yes |
| C8 | `test_gui_project.py` `test_save_overwrites_without_asking` | yes |
| C9 | `test_gui_project.py` `test_first_save_suggests_image_name` | yes |
| C10 | `test_gui_project.py` `test_save_as_changes_the_file` | yes |
| C11 | `test_gui_project.py` `test_suffix_is_appended` | yes |
| C12 | `test_gui_project.py` `test_appended_name_asks_before_overwriting` | yes |
| C13 | `test_gui_project.py` `test_output_folder_beside_project` | yes |
| C14 | `test_gui_project.py` `test_open_clears_undo` | yes |
| C15 | `test_gui_project.py` `test_open_discards_running_tasks` | no - the late 3D result is delivered only with the 3D tab current, where `run_model` takes a new tag anyway; removing `self.req3d += 1` from `apply_project` keeps it green |
| C16 | `test_gui_project.py` `test_open_shows_project_image` | yes |
| C17 | `test_gui_project.py` `test_save_without_image` | yes |
| C18 | `test_gui_project.py` `test_save_while_detecting` | yes |
| C19 | `test_gui_project.py` `test_save_after_failed_detection` | no - no earlier image was detected, so `elif self.analysis is None` in place of `self.fresh_image` keeps it green; "of the current image" is not held |
| C20 | `test_gui_project.py` `test_save_reports_file_name` | yes |
| C21 | `test_gui_project.py` `test_saves_bytes_as_loaded` | yes |
| C22 | `test_gui_project.py` `test_opens_and_saves_without_original_image` | yes |
| C23 | `test_gui_project.py` `test_file_holds_no_local_path` | yes |
| C24 | `test_gui_project.py` `test_missing_printer_uses_default` | yes |
| C25 | `test_gui_project.py` `test_missing_process_and_filament_use_printer_defaults` | yes |
| C26 | `test_gui_project.py` `test_substitutions_in_one_warning` | yes |
| C27 | `test_gui_project.py` `test_substitutions_in_log` | yes |
| C28 | `test_gui_project.py` `test_saving_writes_substitutes` | yes |
| C29 | `test_gui_project.py` `test_no_presets_keeps_names` | yes |
| C30 | `test_gui_project.py` `test_no_presets_warns_once` | yes |
| C31 | `test_gui_project.py` `test_empty_preset_keeps_selection` | yes |
| C32 | `test_gui_project.py` `test_open_writes_no_settings` | yes |
| C33 | `test_gui_project.py` `test_bad_file_shows_error` | yes |
| C34 | `test_gui_project.py` `test_newer_format_is_refused` | yes |
| C35 | `test_project.py` `test_invalid_values_are_refused` | no - RGB upper bound 254 stays green; `centers` range, text in `detection.samples` and out of range `edited`/`detection.samples` are not tried |
| C36 | `test_project.py` `test_mismatched_detection_is_refused` | yes |
| C37 | `test_gui_project.py` `test_failed_open_changes_nothing` | yes |
| C38 | `test_project.py` `test_failed_save_keeps_old_file` | yes |
| C39 | `test_gui_project.py` `test_failed_save_shows_error` | yes |
| C40 | `test_gui_project.py` `test_missing_setting_uses_default_and_logs` | yes |
| C41 | `test_project.py` `test_load_writes_and_runs_nothing` | yes |
| C42 | `test_gui_project.py` `test_title_shows_project` | yes |
| C43 | `test_gui_project.py` `test_every_saved_value_marks_unsaved` | yes |
| C44 | `test_gui_project.py` `test_undo_clears_mark` | yes |
| C45 | `test_gui_project.py` `test_no_project_never_asks` | yes |
| C46 | `test_gui_project.py` `test_guard_asks_on_close_open_and_image` | yes |
| C47 | `test_gui_project.py` `test_guard_save_continues` | yes |
| C48 | `test_gui_project.py` `test_guard_discard_continues` | yes |
| C49 | `test_gui_project.py` `test_guard_cancel_changes_nothing` | yes |
| C50 | `test_gui_project.py` `test_guard_failed_save_stops` | yes |
| C51 | `test_gui_project.py` `test_discard_then_cancelled_dialog_keeps_work` | yes |
| C52 | `test_gui_project.py` `test_new_image_detaches_project` | yes |
| C53 | `test_gui_project.py` `test_local_settings_do_not_mark` | yes |
| C54 | `test_gui_project.py` `test_reopening_same_project_reloads` | yes |
| C55 | `test_gui_project.py` `test_save_recreates_deleted_file` | yes |
| C56 | `test_gui_project.py` `test_export_keeps_its_values` | yes |

## Findings

| Finding | Evidence | Fix | Closed |
| --- | --- | --- | --- |
| F1 (blocker, PROJ-01 AC 2-4): projects of images with a large white area save without error and can never be opened | Own example: red and white square, 2 colors. 600 px with 60%, 80% or 95% white, likewise 1000 and 2000 px: `save` succeeds, `load` raises "valor inválido no projeto: centers." Solid white `synthetic()` fails for 2, 3 and 8 colors. cv2 k-means sums in float32, so the center's L is 255.00002 to 255.43 (`centers` written unclipped, `project.py` `_build` allows 0-255) | accept the float32 drift (for example -1 to 257) or only require finite values; do not clip, the exact centers feed `auto_merge`. Test a round trip of a large mostly white image | 2f64e0f, C4 (`test_mostly_white_image_round_trips`) |
| F2 (minor, PROJ-03 AC 3): a lone surrogate in a text field is accepted, after which the project cannot be saved | Own example: `image_name` = `"a\ud800b"` opens without error; Ctrl+S then shows "'utf-8' codec can't encode character". `current_project` writes `image_name` and, with no presets, `kept_presets` as loaded | refuse text that does not encode to UTF-8 in `_typed` (or reduce it with a note); add to `INVALID` | 2f64e0f, C35 (`test_invalid_values_are_refused`) |
| F3 (minor, C19): test does not hold "of the current image" | mutation `elif self.fresh_image` -> `elif self.analysis is None` in `can_save` survives; with it, a failed second image would be saved with the first image's palette and detection | in `test_save_after_failed_detection`, open a good image first, then the empty one | 2f64e0f, C19 (`test_save_after_failed_detection_of_a_second_image`) |
| F4 (minor, C15): the 3D discard is not proven | removing `self.req3d += 1` from `apply_project` survives the whole GUI project file; in the 2D tab the late model is then accepted | deliver the late 3D result with the 2D tab current and assert that the parts and `reframe3d` are unchanged | 2f64e0f, C15 (`test_open_discards_late_3d_with_2d_tab_shown`) |
| F5 (minor, C35): bounds looser than the claim | mutations survive: RGB `0, 254`; centers `-9, 999`; `detection.samples` unvalidated; offset limit | add a color `[255, 255, 255]` that loads, and `centers` far out of range/text, `detection.samples` `[0, 0, 256]`/text and `edited` `[4]` to `INVALID` | 2f64e0f, C35 (`test_invalid_values_are_refused`, `test_object_far_from_the_corner_round_trips`) |
| F6 (minor, PROJ-01 AC 2): an output name with a folder is not restored | Own example: Nome do arquivo `sub/peça` saves, reopens as `peça` (logged). The design reduces received names, but the spec criterion has no exception and it is not in `Assumptions` | confirm with the user and record the exception in the spec; code can stay (it protects the output folder) | 2f64e0f, spec Assumptions, from the approved design; C41 |
| F7 (minor, PROJ-01 AC 9-11): valid long names cannot be saved | Own example: 246 letters + `.i2b` (250 bytes, legal) fails, because the temporary name adds 13 bytes over the 255 limit | use a short temporary name in the target's folder | 2f64e0f, C38 (`test_longest_file_name_is_saved`) |
| F8 (minor, rule without a check): the `*` after a redetection that comes back to the saved values | removing `update_title()` from `analysis_done` survives the title, undo and guard tests; only undo is tested | change Nº de cores and back by the control, wait, assert that the title has no `*` | 2f64e0f, `test_control_back_to_saved_value_clears_mark` |

Probed and held: 1819 mutations of `project.json` (every key x 17 bad values) raised only `ProjectError` or loaded a valid value; deep JSON, 6000-digit integer, non UTF-8 JSON, empty image, pixel bomb, newer format, names `..`, empty, NUL, newline, HTML, drive prefix; machine empty with process set; printer without filaments. Observed, not required by the spec: saving over a 0600 file widens it to the umask.
