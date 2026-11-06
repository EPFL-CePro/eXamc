# TeX Live installation profile for install-tl (run on the server, see the deployment docs).
# Installs into the texlive volume, without documentation or sources.
# Same collections as the Debian packages the image used to install.

selected_scheme scheme-custom

TEXDIR /opt/texlive
TEXMFLOCAL /opt/texlive/texmf-local
TEXMFSYSCONFIG /opt/texlive/texmf-config
TEXMFSYSVAR /opt/texlive/texmf-var
TEXMFHOME ~/texmf
TEXMFCONFIG ~/.texlive/texmf-config
TEXMFVAR ~/.texlive/texmf-var

binary_x86_64-linux 1
binary_aarch64-linux 0

collection-basic 1
collection-latex 1
collection-latexrecommended 1
collection-latexextra 1
collection-pictures 1
collection-plaingeneric 1
collection-fontsrecommended 1
collection-fontsextra 1
collection-xetex 1
collection-langeuropean 1
collection-langfrench 1
collection-binextra 1

instopt_adjustpath 0
instopt_adjustrepo 1
instopt_letter 0
instopt_write18_restricted 1

tlpdbopt_autobackup 0
tlpdbopt_install_docfiles 0
tlpdbopt_install_srcfiles 0
