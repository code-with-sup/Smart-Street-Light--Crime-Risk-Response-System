from sentinel.hardware import HardwareLink


def test_no_ldr_report_keeps_clock_fallback_available():
    link = HardwareLink()
    link._handle_line('READY smart-street-esp32 v3')
    link._handle_line('STATE 1 -1 100 1 0')
    assert link.ldr is None
    assert link.pir and link.buzzer and link.brightness == 100
    assert link.firmware == 'smart-street-esp32 v3'


def test_ldr_reports_still_work():
    link = HardwareLink()
    link._handle_line('STATE 0 1200 20 0 1')
    assert link.ldr == 1200 and link.strobe and not link.buzzer
