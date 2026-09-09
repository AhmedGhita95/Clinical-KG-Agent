# Demo clip

`demo/animated_patient_transfer.mp4` is an eight-second synthetic animated scene
created from programmatic geometric shapes by `demo/generate_demo_clip.py`.

The animation depicts a nurse pushing a seated patient in a wheelchair along a
clinical corridor. It intentionally matches the reviewed fixture in
`fixtures/patient_transfer.json`.

Regenerate it from the repository root after installing the full dependencies:

```powershell
python clips/demo/generate_demo_clip.py
```
