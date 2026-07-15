# Raw dataset downloads

Place the original datasets here (or anywhere; the prepare scripts take a
`--root` path). None of these files are committed. Re-check the license text
of each dataset when you download it.

| Dataset | Get it from | Used for |
|---|---|---|
| LLVIP | https://bupt-ai-cz.github.io/LLVIP/ (GitHub: bupt-ai-cz/LLVIP) | Stage A thermal-to-visible |
| FLIR ADAS v2 | https://oem.flir.com/solutions/automotive/adas-dataset-form/ (Kaggle mirror: samdazel/teledyne-flir-adas-thermal-dataset-v2) | Stage A extra thermal |
| KAIST Multispectral | https://soonminhwang.github.io/rgbt-ped-detection/ | Stage A pretraining scale |
| M3FD | https://github.com/JinyuanLiu-CV/TarDAL | Stage A scene diversity |
| BatVision v1 | https://github.com/SaschaHornauer/Batvision | Stage B echoes |
| Audio-Visual BatVision | https://github.com/AmandineBtto/Batvision-Dataset | Stage B main echoes |
| SoundSpaces 2.0 + Replica | https://github.com/facebookresearch/sound-spaces | Stage B synthetic echoes (Linux/WSL recommended) |

Then run, from `NOVIS_Model/`:

```
python scripts/prepare_llvip.py --root data/raw/LLVIP --out data/processed/llvip
python scripts/prepare_batvision.py --audio "data/raw/batvision/**/audio/*.wav" ^
    --rgb "data/raw/batvision/**/rgb/*.png" --depth "data/raw/batvision/**/depth/*.png" ^
    --out data/processed/batvision
```

`prepare_batvision.py` pairs files by sorted order: adjust its glob patterns
to the exact folder layout of the release you downloaded and spot-check a few
pairs before a full run. FLIR/KAIST/M3FD reuse `prepare_llvip.py` if you
arrange them into the same infrared/visible folder layout.

`data/real_capture/` is reserved for the prototype's recorded dataset
(Stage D); its capture protocol is in NOVIS/docs/methodology.md Section 7.
