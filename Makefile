PACKAGE_VERSION=0.0.1
prefix=/usr

all:

install:
	install -d -m 0755 "$(DESTDIR)/$(prefix)/sbin"
	install -m 0755 wrtd "$(DESTDIR)/$(prefix)/sbin"

	install -d -m 0755 "$(DESTDIR)/$(prefix)/bin"
	install -m 0755 wrtctl "$(DESTDIR)/$(prefix)/bin"

	install -d -m 0755 "$(DESTDIR)/$(prefix)/lib/wrtd"
	cp -r lib/* "$(DESTDIR)/$(prefix)/lib/wrtd"
	find "$(DESTDIR)/$(prefix)/lib/wrtd" -path "$(DESTDIR)/$(prefix)/lib/wrtd/plugins" -prune -o -type f | xargs chmod 644
	find "$(DESTDIR)/$(prefix)/lib/wrtd" -path "$(DESTDIR)/$(prefix)/lib/wrtd/plugins" -prune -o -type d | xargs chmod 755

	install -d -m 0755 "$(DESTDIR)/etc/wrtd"

	install -d -m 0755 "$(DESTDIR)/$(prefix)/lib/systemd/system"
	install -m 0644 data/wrtd.service "$(DESTDIR)/$(prefix)/lib/systemd/system"

	install -d -m 0755 "$(DESTDIR)/etc/dbus-1/system.d"
	install -m 0644 data/org.fpemud.WRT.conf "$(DESTDIR)/etc/dbus-1/system.d"
	install -m 0644 data/org.fpemud.IpForward.conf "$(DESTDIR)/etc/dbus-1/system.d"

uninstall:
	rm -f "$(DESTDIR)/$(prefix)/bin/wrtctl"
	rm -f "$(DESTDIR)/$(prefix)/sbin/wrtd"
	rm -f "$(DESTDIR)/$(prefix)/lib/systemd/system/wrtd.service"
	rm -f "$(DESTDIR)/$(prefix)/etc/dbus-1/system.d/org.fpemud.WRT.conf"
	rm -rf "$(DESTDIR)/$(prefix)/lib/wrtd"
	rm -rf "$(DESTDIR)/etc/wrtd"

.PHONY: all install uninstall
