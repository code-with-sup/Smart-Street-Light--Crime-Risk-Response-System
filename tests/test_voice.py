"""Voice warnings: OS speech commands and when the service speaks."""

from sentinel.risk import RiskResult
from sentinel.voice import speech_command


def test_each_os_has_a_speech_command():
    assert speech_command("hi", "darwin") == ["say", "hi"]
    windows = speech_command("it's late", "win32")
    assert windows[0] == "powershell" and "it''s late" in windows[-1]  # quote escaped for PowerShell


class RecordingSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append(text)
        return True


def high():
    return RiskResult(level="HIGH")


def test_voice_is_off_by_default(service):
    service.speaker = RecordingSpeaker()
    service._voice(high(), "LOW", sos=False, now=1000)
    assert not service.speaker.said


def test_speaks_when_risk_rises_then_repeats_every_30_s(service):
    service.settings = service.store.save_settings({"voice_warnings": "high"})
    service.speaker = RecordingSpeaker()
    service._voice(high(), "LOW", sos=False, now=1000)
    service._voice(high(), "HIGH", sos=False, now=1010)   # still HIGH, too soon
    service._voice(high(), "HIGH", sos=False, now=1031)   # 30 s later: repeat
    assert len(service.speaker.said) == 2 and "surveillance" in service.speaker.said[0]


def test_medium_only_spoken_in_medium_mode(service):
    service.speaker = RecordingSpeaker()
    service.settings = service.store.save_settings({"voice_warnings": "high"})
    service._voice(RiskResult(level="MEDIUM"), "LOW", sos=False, now=1000)
    assert not service.speaker.said
    service.settings = service.store.save_settings({"voice_warnings": "medium"})
    service._voice(RiskResult(level="MEDIUM"), "LOW", sos=False, now=1001)
    assert service.speaker.said == [service.settings["voice_medium"]]


def test_sos_has_its_own_message(service):
    service.settings = service.store.save_settings({"voice_warnings": "high"})
    service.speaker = RecordingSpeaker()
    service._voice(high(), "HIGH", sos=True, now=1000)
    assert service.speaker.said == [service.settings["voice_sos"]]
