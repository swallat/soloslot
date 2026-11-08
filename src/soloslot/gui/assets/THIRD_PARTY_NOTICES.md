# Licenses

## soloslot

Copyright (c) 2026 Sebastian Wallat. soloslot is released under the **MIT License**
(<https://github.com/swallat/soloslot/blob/main/LICENSE>).

soloslot is built on the open-source software below. Each component stays under its own license.
This list covers what the installed app ships and what it downloads when you set up stem
separation.

## Shipped with the app

### Qt and PySide6 (Qt for Python) · LGPL-3.0

The window is built with Qt 6 through PySide6 (<https://pyside.org>, <https://www.qt.io>), used
under the **GNU Lesser General Public License v3.0**
(<https://www.gnu.org/licenses/lgpl-3.0.html>). Qt is linked dynamically: the Qt and PySide6
libraries are separate files in the app folder, and you may replace them with a compatible
version of your own. The source code of Qt and PySide6 is available at
<https://code.qt.io> and <https://download.qt.io/official_releases/QtForPython/>.

### click · BSD-3-Clause

Copyright (c) Pallets. <https://github.com/pallets/click>

### NumPy · BSD-3-Clause

Copyright (c) NumPy Developers. <https://numpy.org>

### python-soundfile and libsndfile · BSD-3-Clause and LGPL-2.1-or-later

python-soundfile, copyright (c) Bastian Bechtold: <https://github.com/bastibe/python-soundfile>.
It loads the libsndfile library (<https://libsndfile.github.io/libsndfile/>), copyright (c) Erik de
Castro Lopo and contributors, under the **GNU Lesser General Public License v2.1 or later**
(<https://www.gnu.org/licenses/lgpl-2.1.html>). libsndfile is a separate shared library in the
app folder and can be replaced.

### sounddevice and PortAudio · MIT

python-sounddevice, copyright (c) Matthias Geier: <https://github.com/spatialaudio/python-sounddevice>.
It plays the preview through PortAudio (<http://www.portaudio.com>), copyright (c) Ross Bencina and
Phil Burk, under the MIT license. PortAudio is a separate shared library in the app folder.

### CFFI · MIT

Copyright (c) Armin Rigo, Maciej Fijalkowski. <https://cffi.readthedocs.io>

### Python · PSF License

The app embeds the Python runtime, copyright (c) Python Software Foundation, under the Python
Software Foundation License (<https://docs.python.org/3/license.html>).

### PyInstaller · GPL-2.0-or-later with bootloader exception

The installers are built with PyInstaller (<https://pyinstaller.org>). Its license has a
special exception that lets the bundled app use any license.

## Downloaded when you set up stem separation

### Demucs · MIT

Copyright (c) Meta Platforms, Inc. and affiliates. <https://github.com/facebookresearch/demucs>
(maintained fork: <https://github.com/adefossez/demucs>). The model weights it downloads have
their own terms; see the Demucs project.

### PyTorch · BSD-3-Clause

Copyright (c) the PyTorch contributors. <https://pytorch.org>

### Other Python packages

Demucs and PyTorch pull in further packages (for example torchaudio, einops, julius, lameenc,
openunmix, pyyaml, tqdm). Each comes with its own license in its distribution; they are
permissive (MIT, BSD, Apache-2.0) licenses.

## MIT License text

Permission is hereby granted, free of charge, to any person obtaining a copy of this software
and associated documentation files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
