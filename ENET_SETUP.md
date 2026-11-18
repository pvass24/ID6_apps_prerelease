# ENET Cable Connection Guide — Mac Setup

## Hardware
- **Wired ENET cable** (OBD2 → RJ45 Ethernet) — NOT the WiFi OBD adapter
- **USB Ethernet adapter** (you have one — shows as `en8` / "USB 10/100/1000 LAN")
- MacBook

## Before Going to the Car

### 1. Test your USB Ethernet adapter
Plug the USB Ethernet adapter into your Mac (without the ENET cable). Check it appears:
```bash
ifconfig en8
```
You should see `en8` with `status: active` or at least the interface listed.

### 2. Set a manual IP (optional but recommended)
The ENET connection uses link-local addresses (169.254.x.x). macOS should auto-configure this, but to be safe you can set it manually:

**System Settings → Network → USB 10/100/1000 LAN → Details → TCP/IP:**
- Configure IPv4: **Manually**
- IP Address: **169.254.10.2**
- Subnet Mask: **255.255.0.0**
- Router: (leave blank)

The head unit will be at 169.254.10.3 (the diagnostic gateway) or similar. Bavarian SSH Client will tell you the exact IP.

### 3. Disable WiFi initially, re-enable after verifying ENET
Turn WiFi OFF before connecting the ENET cable — this prevents macOS routing confusion during initial setup.

Once ENET is working (you can ping the head unit), turn WiFi back ON so you can use Claude Code / internet on the same laptop. Then verify the car route didn't break:
```bash
route get 169.254.10.3
# Must show: interface: en8 (your USB Ethernet)
# If it shows en0 (WiFi), the route is wrong — turn WiFi off again
```

If the route is correct (`en8`), both connections work simultaneously — car on Ethernet, internet on WiFi.

## At the Car

### 1. Physical connection
1. Plug ENET cable's OBD2 end into the car's OBD port (driver footwell, left side)
2. Plug ENET cable's RJ45 end into the USB Ethernet adapter
3. Plug USB Ethernet adapter into Mac

### 2. Verify connection
```bash
# Check the interface got an IP
ifconfig en8 | grep inet

# You should see: inet 169.254.x.x

# Ping the diagnostic gateway (standard BMW address)
ping -c 3 169.254.10.3

# If ping fails, try:
ping -c 3 169.254.21.3
```

### 3. Test diagnostic access
```bash
# Try connecting to HSFZ port
nc -z -w 3 169.254.10.3 6801 && echo "HSFZ: OPEN" || echo "HSFZ: CLOSED"
```

### 4. If the car doesn't respond
- Make sure iDrive is ON (not sleeping). Tap the screen or press a button.
- Try both gateway IPs: 169.254.10.3 and 169.254.21.3
- Check `ifconfig en8` has a 169.254.x.x address
- Unplug and replug the ENET cable
- Make sure WiFi is OFF

## Troubleshooting: "Connected but nothing responds"

If your Mac shows an IP on en8 but can't reach the car:

1. **Check the cable** — some cheap ENET cables are wired wrong. If you have a multimeter, verify pins 1,2,3,6 have continuity.

2. **Check macOS routing** — sometimes macOS routes traffic through WiFi instead of Ethernet:
```bash
# Check which interface is used for 169.254.x.x
route get 169.254.10.3
# Should show: interface: en8
```

3. **ARP check** — see if the car is on the network at all:
```bash
arp -a | grep 169.254
```

4. **Firewall** — your firewall is currently disabled (good). If it gets re-enabled:
```bash
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off
```

## The WiFi OBD Adapter

Your WiFi OBD adapter is a **separate tool** for different purposes:
- Use it for: MHD, BimmerCode, Torque, OBD Fusion
- DON'T use it for: SSH, plugin install, HSFZ diagnostics, signal probing

**Never plug both the WiFi adapter AND the ENET cable into the OBD port at the same time.**
