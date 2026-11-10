Package: texlive-local
Version: 99999
Architecture: all
Maintainer: examc <examc@localhost>
Provides: texlive-base (= 99999), texlive-binaries (= 99999),
 texlive-latex-base (= 99999), texlive-latex-recommended (= 99999), texlive-latex-extra (= 99999),
 texlive-fonts-recommended (= 99999), texlive-fonts-extra (= 99999), texlive-xetex (= 99999),
 texlive-pictures (= 99999), texlive-plain-generic (= 99999),
 texlive-lang-european (= 99999), texlive-lang-french (= 99999),
 cm-super (= 99999), lmodern (= 99999), latexmk (= 99999)
Description: TeX Live installed outside apt
 TeX Live comes from the official TeX Live image, in the texlive volume (/opt/texlive).
 This package tells apt it is present, so packages depending on Debian's TeX Live
 (auto-multiple-choice) install without it. If the image build fails with
 "Debian TeX Live got installed", add the package it names to Provides.
