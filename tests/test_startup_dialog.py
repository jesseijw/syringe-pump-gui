from startup_dialog import StartupDialog


def test_startup_dialog_constructs(qapp):
    assert StartupDialog(detected_ids=[1, 2, 3]) is not None


def test_home_choice(qapp):
    dlg = StartupDialog(detected_ids=[1, 2, 3])
    dlg._home_btn.click()
    assert dlg.choice == StartupDialog.HOME


def test_resume_choice(qapp):
    dlg = StartupDialog(detected_ids=[1, 3])
    dlg._resume_btn.click()
    assert dlg.choice == StartupDialog.RESUME
