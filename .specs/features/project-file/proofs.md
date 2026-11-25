# project-file proofs

**HEAD**: 35baa8c
**Tree**: clean
**Shell**: /bin/sh
**Result**: 58 pass, 0 fail

| Check | Proof | Result |
| --- | --- | --- |
| C1 | `run project / tests/test_gui_project.py::test_menu_and_shortcuts PASSED` | pass |
| C2 | `run project / tests/test_gui_project.py::test_reopen_restores_every_control PASSED` | pass |
| C3 | `run project / tests/test_gui_project.py::test_reopen_restores_every_row PASSED` | pass |
| C4 | `run project / tests/test_project.py::test_masks_equal_after_round_trip PASSED` | pass |
| C5 | `run project / tests/test_gui_project.py::test_open_runs_no_detection PASSED` | pass |
| C6 | `run project / tests/test_project.py::test_later_sample_edit_gives_same_masks PASSED` | pass |
| C7 | `run project / tests/test_gui_project.py::test_later_redetection_carries_edited_rows PASSED` | pass |
| C8 | `run project / tests/test_gui_project.py::test_save_overwrites_without_asking PASSED` | pass |
| C9 | `run project / tests/test_gui_project.py::test_first_save_suggests_image_name PASSED` | pass |
| C10 | `run project / tests/test_gui_project.py::test_save_as_changes_the_file PASSED` | pass |
| C11 | `run project / tests/test_gui_project.py::test_suffix_is_appended PASSED` | pass |
| C12 | `run project / tests/test_gui_project.py::test_appended_name_asks_before_overwriting PASSED` | pass |
| C13 | `run project / tests/test_gui_project.py::test_output_folder_beside_project PASSED` | pass |
| C14 | `run project / tests/test_gui_project.py::test_open_clears_undo PASSED` | pass |
| C15 | `run project / tests/test_gui_project.py::test_open_discards_running_tasks PASSED` | pass |
| C16 | `run project / tests/test_gui_project.py::test_open_shows_project_image PASSED` | pass |
| C17 | `run project / tests/test_gui_project.py::test_save_without_image PASSED` | pass |
| C18 | `run project / tests/test_gui_project.py::test_save_while_detecting PASSED` | pass |
| C19 | `run project / tests/test_gui_project.py::test_save_after_failed_detection PASSED` | pass |
| C20 | `run project / tests/test_gui_project.py::test_save_reports_file_name PASSED` | pass |
| C21 | `run project / tests/test_gui_project.py::test_saves_bytes_as_loaded PASSED` | pass |
| C22 | `run project / tests/test_gui_project.py::test_opens_and_saves_without_original_image PASSED` | pass |
| C23 | `run project / tests/test_gui_project.py::test_file_holds_no_local_path PASSED` | pass |
| C24 | `run project / tests/test_gui_project.py::test_missing_printer_uses_default PASSED` | pass |
| C25 | `run project / tests/test_gui_project.py::test_missing_process_and_filament_use_printer_defaults PASSED` | pass |
| C26 | `run project / tests/test_gui_project.py::test_substitutions_in_one_warning PASSED` | pass |
| C27 | `run project / tests/test_gui_project.py::test_substitutions_in_log PASSED` | pass |
| C28 | `run project / tests/test_gui_project.py::test_saving_writes_substitutes PASSED` | pass |
| C29 | `run project / tests/test_gui_project.py::test_no_presets_keeps_names PASSED` | pass |
| C30 | `run project / tests/test_gui_project.py::test_no_presets_warns_once PASSED` | pass |
| C31 | `run project / tests/test_gui_project.py::test_empty_preset_keeps_selection PASSED` | pass |
| C32 | `run project / tests/test_gui_project.py::test_open_writes_no_settings PASSED` | pass |
| C33 | `run project / tests/test_gui_project.py::test_bad_file_shows_error PASSED` | pass |
| C34 | `run project / tests/test_gui_project.py::test_newer_format_is_refused PASSED` | pass |
| C35 | `run project / tests/test_project.py::test_invalid_values_are_refused PASSED` | pass |
| C36 | `run project / tests/test_project.py::test_mismatched_detection_is_refused PASSED` | pass |
| C37 | `run project / tests/test_gui_project.py::test_failed_open_changes_nothing PASSED` | pass |
| C38 | `run project / tests/test_project.py::test_failed_save_keeps_old_file PASSED` | pass |
| C39 | `run project / tests/test_gui_project.py::test_failed_save_shows_error PASSED` | pass |
| C40 | `run project / tests/test_gui_project.py::test_missing_setting_uses_default_and_logs PASSED` | pass |
| C41 | `run project / tests/test_project.py::test_load_writes_and_runs_nothing PASSED` | pass |
| C42 | `run project / tests/test_gui_project.py::test_title_shows_project PASSED` | pass |
| C43 | `run project / tests/test_gui_project.py::test_every_saved_value_marks_unsaved PASSED` | pass |
| C44 | `run project / tests/test_gui_project.py::test_undo_clears_mark PASSED` | pass |
| C45 | `run project / tests/test_gui_project.py::test_no_project_never_asks PASSED` | pass |
| C46 | `run project / tests/test_gui_project.py::test_guard_asks_on_close_open_and_image PASSED` | pass |
| C47 | `run project / tests/test_gui_project.py::test_guard_save_continues PASSED` | pass |
| C48 | `run project / tests/test_gui_project.py::test_guard_discard_continues PASSED` | pass |
| C49 | `run project / tests/test_gui_project.py::test_guard_cancel_changes_nothing PASSED` | pass |
| C50 | `run project / tests/test_gui_project.py::test_guard_failed_save_stops PASSED` | pass |
| C51 | `run project / tests/test_gui_project.py::test_discard_then_cancelled_dialog_keeps_work PASSED` | pass |
| C52 | `run project / tests/test_gui_project.py::test_new_image_detaches_project PASSED` | pass |
| C53 | `run project / tests/test_gui_project.py::test_local_settings_do_not_mark PASSED` | pass |
| C54 | `run project / tests/test_gui_project.py::test_reopening_same_project_reloads PASSED` | pass |
| C55 | `run project / tests/test_gui_project.py::test_save_recreates_deleted_file PASSED` | pass |
| C56 | `run project / tests/test_gui_project.py::test_export_keeps_its_values PASSED` | pass |
| Build | `python -m ruff check .` | pass |
| Build | `timeout 900 python -m pytest -m "not slow"` | pass |

## Output

`Run project` - exit 0

```
tests/test_gui_project.py::test_substituted_presets_do_not_mark PASSED   [ 82%]
tests/test_gui_project.py::test_every_saved_value_marks_unsaved PASSED   [ 83%]
tests/test_gui_project.py::test_undo_clears_mark PASSED                  [ 85%]
tests/test_gui_project.py::test_control_back_to_saved_value_clears_mark PASSED [ 86%]
tests/test_gui_project.py::test_no_project_never_asks PASSED             [ 88%]
tests/test_gui_project.py::test_guard_asks_on_close_open_and_image PASSED [ 89%]
tests/test_gui_project.py::test_guard_save_continues PASSED              [ 91%]
tests/test_gui_project.py::test_guard_discard_continues PASSED           [ 92%]
tests/test_gui_project.py::test_guard_cancel_changes_nothing PASSED      [ 94%]
tests/test_gui_project.py::test_guard_failed_save_stops PASSED           [ 95%]
tests/test_gui_project.py::test_discard_then_cancelled_dialog_keeps_work PASSED [ 97%]
tests/test_gui_project.py::test_new_image_detaches_project PASSED        [ 98%]
tests/test_gui_project.py::test_local_settings_do_not_mark PASSED        [100%]

============================= 68 passed in 58.14s ==============================
```
