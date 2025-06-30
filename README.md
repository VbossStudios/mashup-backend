# Mashup Backend

Upload two songs → split vocals/instrumentals → choose sources → mix → download mashup.

## POST /mashup/

Form data:
- file1: Song A (for either vocals or beat)
- file2: Song B (for either vocals or beat)
- vocals_from: 1 or 2 (which song provides vocals)

Returns: mashup.wav
