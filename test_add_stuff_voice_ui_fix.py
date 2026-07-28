from __future__ import annotations

from pathlib import Path


def test_popup_source() -> None:
    source = Path('ui/window.py').read_text(encoding='utf-8')
    required = (
        'WA_StyledBackground',
        'WA_TranslucentBackground, False',
        'background-color: #171C29',
        'background-color: #1D2332',
        'VOICE//RETRYING',
    )
    missing = [item for item in required if item not in source]
    if missing:
        raise AssertionError(f'Missing popup/UI fixes: {missing}')


def test_voice_recovery() -> None:
    import speech_recognition as sr

    from voice.voice_assistant import VoiceAssistant

    statuses: list[str] = []
    messages: list[str] = []
    assistant = VoiceAssistant(
        command_callback=lambda _command: None,
        status_callback=statuses.append,
        message_callback=messages.append,
    )
    assistant.running_event.set()
    assistant._recognition_retry_delay_seconds = 0

    def unavailable(_audio, language='en-IN'):
        raise sr.RequestError('test outage')

    assistant.recognizer.recognize_google = unavailable
    assistant.recognize_audio(None)

    if not any('retrying' in status.lower() for status in statuses):
        raise AssertionError(f'Retry status not emitted: {statuses}')
    if not statuses or statuses[-1] != 'Listening for Hey MV':
        raise AssertionError(f'Voice did not recover to listening: {statuses}')


if __name__ == '__main__':
    test_popup_source()
    test_voice_recovery()
    print('[PASSED] ADD Stuff popup uses a visible opaque background.')
    print('[PASSED] Temporary speech-service errors recover to listening.')
