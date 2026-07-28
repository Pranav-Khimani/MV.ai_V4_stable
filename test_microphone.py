import speech_recognition as sr


MICROPHONE_INDEX = 1
# Replace 1 with your microphone index.


recognizer = sr.Recognizer()

recognizer.dynamic_energy_threshold = True
recognizer.energy_threshold = 100
recognizer.pause_threshold = 1.0
recognizer.phrase_threshold = 0.2
recognizer.non_speaking_duration = 0.5


try:
    microphone = sr.Microphone(
        device_index=MICROPHONE_INDEX
    )

    print("Stay silent. Calibrating microphone...")

    with microphone as source:
        recognizer.adjust_for_ambient_noise(
            source,
            duration=2,
        )

        print(
            f"Calibration complete.\n"
            f"Energy threshold: "
            f"{recognizer.energy_threshold}\n"
        )

        print(
            "Speak a full sentence clearly."
        )

        audio = recognizer.listen(
            source,
            timeout=10,
            phrase_time_limit=8,
        )

    print("Audio captured. Recognizing...")

    text = recognizer.recognize_google(
        audio,
        language="en-US",
        show_all=False,
    )

    print(f"You said: {text}")

except sr.WaitTimeoutError:
    print(
        "No speech was detected."
    )

except sr.UnknownValueError:
    print(
        "Audio was captured, but speech was unclear.\n"
        "Try speaking louder, closer to the microphone, "
        "and use a longer sentence."
    )

except sr.RequestError as error:
    print(
        f"Speech recognition service error: {error}"
    )

except Exception as error:
    print(
        f"Error: {type(error).__name__}: {error}"
    )