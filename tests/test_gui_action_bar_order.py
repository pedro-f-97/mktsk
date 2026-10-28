"""The archive button stands last in the action bar of a selected row."""

from mktsk.gui.reminders_scheduler import ReminderScheduler
from mktsk.tasks import close_task
from tests.gui_helpers import action_bar, select_tab


class _FakeTray:
    """Records nothing: the tests never reach a notification."""

    def notify(self, title, message):
        pass


def _scheduler(tmp_path):
    return ReminderScheduler(_FakeTray(), tmp_path / "reminders.json")


def _bar_buttons(bar):
    """The widgets of the bar, in the order the layout lays them out."""
    layout = bar.layout()
    return [
        widget
        for index in range(layout.count())
        if (item := layout.itemAt(index)) is not None
        and (widget := item.widget()) is not None
    ]


def test_the_archive_button_is_last_with_a_scheduler(window, tmp_path, make_task):
    file = make_task(tmp_path, "261027", "Teste")
    window.navigate_to(tmp_path)
    window.reminder_scheduler = _scheduler(tmp_path)

    bar = action_bar(window, file)

    ordered = tuple(_bar_buttons(bar))
    assert ordered == (
        bar.open_button,
        bar.resume_button,
        bar.rename_button,
        bar.state_button,
        bar.reminders_button,
        bar.close_button,
    )
    positions = [button.geometry().x() for button in ordered]
    assert positions == sorted(positions)
    assert ordered[-1] is bar.close_button
    assert bar.close_button.geometry().x() == max(positions)


def test_the_archive_button_is_last_without_a_scheduler(window, tmp_path, make_task):
    file = make_task(tmp_path, "261027", "Teste")
    window.navigate_to(tmp_path)

    bar = action_bar(window, file)

    assert [button.isVisible() for button in bar.reminder_buttons()] == [False]
    ordered = tuple(
        button for button in _bar_buttons(bar) if button.isVisible()
    )
    assert ordered == (
        bar.open_button,
        bar.resume_button,
        bar.rename_button,
        bar.state_button,
        bar.close_button,
    )
    positions = [button.geometry().x() for button in ordered]
    assert positions == sorted(positions)
    assert ordered[-1] is bar.close_button


def test_the_other_buttons_keep_their_order(window, tmp_path, make_task):
    file = make_task(tmp_path, "261027", "Teste")
    window.navigate_to(tmp_path)
    window.reminder_scheduler = _scheduler(tmp_path)

    bar = action_bar(window, file)

    positions = {
        button: button.geometry().x()
        for button in (
            bar.open_button,
            bar.resume_button,
            bar.rename_button,
            bar.state_button,
            bar.reminders_button,
        )
    }
    assert positions[bar.open_button] < positions[bar.resume_button]
    assert positions[bar.resume_button] < positions[bar.rename_button]
    assert positions[bar.rename_button] < positions[bar.state_button]
    assert positions[bar.state_button] < positions[bar.reminders_button]


def test_the_closed_tab_still_offers_only_reopen(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    close_task(file.parent, "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Closed")

    bar = action_bar(window, tmp_path / "260918 - Foo.zip", "Closed")

    visible = [
        button
        for button in (
            bar.open_button,
            bar.resume_button,
            bar.rename_button,
            bar.state_button,
            bar.close_button,
            bar.reminders_button,
        )
        if button.isVisible()
    ]
    assert visible == [bar.resume_button]
