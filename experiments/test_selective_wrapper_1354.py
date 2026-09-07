from stt.ispot_stt import SelectiveFallbackSTTProvider


provider = SelectiveFallbackSTTProvider()

result = provider.transcribe(
    "test_sample/1354.mp3"
)


print("=" * 70)
print("SelectiveFallbackSTTProvider 결과")
print("=" * 70)

print(
    "Deepgram segments:",
    len(result.get("segments", []))
)

print(
    "fallback_used:",
    result.get("fallback_used")
)

print(
    "fallback 개수:",
    len(result.get("fallback_evidence", []))
)


for item in result.get(
    "fallback_evidence",
    []
):
    print()
    print("-" * 70)

    print(
        "trigger:",
        item.get("trigger")
    )

    print(
        "gap:",
        item.get("gap_start_ms"),
        "→",
        item.get("gap_end_ms"),
    )

    print(
        "clip:",
        item.get("clip_start_ms"),
        "→",
        item.get("clip_end_ms"),
    )

    print(
        "speaker_hint:",
        item.get("speaker_hint")
    )

    print(
        "Whisper:",
        item.get("text")
    )

    if item.get("error"):
        print(
            "ERROR:",
            item["error"]
        )