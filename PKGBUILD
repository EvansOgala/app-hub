pkgname=app-hub-git
pkgver=0.r7.g87a8bde
pkgrel=1
pkgdesc="Qt download manager and AppImage launcher"
arch=('any')
url="https://github.com/EvansOgala/app-hub"
license=('MIT')
options=('!strip' '!debug')
depends=(
  'python'
  'pyside6'
)
makedepends=('git')
source=("$pkgname::git+https://github.com/EvansOgala/app-hub.git")
sha256sums=('SKIP')

pkgver() {
  cd "$srcdir/$pkgname"
  printf "0.r%s.g%s" \
    "$(git rev-list --count HEAD)" \
    "$(git rev-parse --short HEAD)"
}

package() {
  cd "$srcdir/$pkgname"

  install -d "$pkgdir/usr/lib/app-hub"
  install -Dm644 main.py "$pkgdir/usr/lib/app-hub/main.py"
  install -Dm644 ui.py "$pkgdir/usr/lib/app-hub/ui.py"
  install -Dm644 qt_style.py "$pkgdir/usr/lib/app-hub/qt_style.py"
  install -Dm644 downloads.py "$pkgdir/usr/lib/app-hub/downloads.py"
  install -Dm644 settings.py "$pkgdir/usr/lib/app-hub/settings.py"
  install -Dm644 appimage.py "$pkgdir/usr/lib/app-hub/appimage.py"

  install -Dm755 /dev/stdin "$pkgdir/usr/bin/app-hub" <<'LAUNCHER'
#!/bin/sh
exec /usr/bin/python3 /usr/lib/app-hub/main.py "$@"
LAUNCHER

  install -Dm755 /dev/stdin "$pkgdir/usr/bin/org.evans.AppHub" <<'LAUNCHER'
#!/bin/sh
exec /usr/bin/python3 /usr/lib/app-hub/main.py "$@"
LAUNCHER

  install -Dm644 org.evans.AppHub.desktop \
    "$pkgdir/usr/share/applications/org.evans.AppHub.desktop"
  install -Dm644 org.evans.AppHub.metainfo.xml \
    "$pkgdir/usr/share/metainfo/org.evans.AppHub.metainfo.xml"
  install -Dm644 org.evans.AppHub.svg \
    "$pkgdir/usr/share/icons/hicolor/scalable/apps/org.evans.AppHub.svg"
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
