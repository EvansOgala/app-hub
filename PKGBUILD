pkgname=app-hub-git
pkgver=0.r3.g8c68fa8
pkgrel=1
pkgdesc="GTK4 download manager and AppImage launcher"
arch=('any')
url="https://github.com/EvansOgala/app-hub"
license=('MIT')
options=('!strip' '!debug')
depends=(
  'python'
  'python-gobject'
  'gtk4'
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

build() {
  cd "$srcdir/$pkgname"
  python3 -m PyInstaller --clean --noconfirm --log-level=ERROR AppHub.spec
}

package() {
  cd "$srcdir/$pkgname"

  install -d "$pkgdir/usr/lib/app-hub"
  cp -a dist/AppHub/. "$pkgdir/usr/lib/app-hub/"
  install -Dm755 /dev/stdin "$pkgdir/usr/bin/app-hub" <<'LAUNCHER'
#!/bin/sh
exec /usr/lib/app-hub/AppHub "$@"
LAUNCHER
  install -Dm644 org.evans.AppHub.desktop \
    "$pkgdir/usr/share/applications/org.evans.AppHub.desktop"
  install -Dm644 org.evans.AppHub.metainfo.xml \
    "$pkgdir/usr/share/metainfo/org.evans.AppHub.metainfo.xml"
  install -Dm644 org.evans.AppHub.svg \
    "$pkgdir/usr/share/icons/hicolor/scalable/apps/org.evans.AppHub.svg"
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"

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
