from startup_dialog import StartupDialog


def test_startup_dialog_constructs(qapp):
    dlg = StartupDialog(detected_ids=[1, 2, 3])
    assert dlg.windowTitle() == "Syringe Pump Controller — Startup"
    assert dlg.choice is None


def test_startup_dialog_choice_is_none_before_click(qapp):
    dlg = StartupDialog(detected_ids=[1, 2])
    assert dlg.choice is None


def test_home_choice(qapp):
    dlg = StartupDialog(detected_ids=[1, 2, 3])
    dlg._home_btn.click()
    assert dlg.choice == StartupDialog.HOME


def test_resume_choice(qapp):
    dlg = StartupDialog(detected_ids=[1, 3])
    dlg._resume_btn.click()
    assert dlg.choice == StartupDialog.RESUME


def test_startup_dialog_empty_detected_ids(qapp):
    dlg = StartupDialog(detected_ids=[])
    dlg._home_btn.click()
    assert dlg.choice == StartupDialog.HOME
