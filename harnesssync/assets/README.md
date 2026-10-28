# Achievement card font

`card-font.otf` is a subset of Noto Sans CJK JP Regular, with Latin, Japanese,
Korean and Simplified Chinese glyphs used by the bundled translation catalogs.
It is licensed under the SIL Open Font License; see `OFL.txt`.

Source: https://github.com/notofonts/noto-cjk/tree/main/Sans/OTF/Japanese

To regenerate after changing translations, install `fonttools` in a build
environment, download `NotoSansCJKjp-Regular.otf` from the source repository,
then run `python scripts/build_card_font.py /path/to/NotoSansCJKjp-Regular.otf`.
No font download or translation service is used at runtime.
