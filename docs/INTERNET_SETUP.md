# How to Give Raspberry Pi Internet Access

## Overview

Your Raspberry Pi (GREEN-BEAN) runs as a WiFi hotspot for cameras. To give the RP internet access while keeping the hotspot active, your desktop computer will share its internet connection with the RP.

**What happens:**
- RP connects to your desktop's WiFi hotspot
- Desktop shares its internet with RP via NAT (Network Address Translation)
- RP can now download updates, access websites, etc.
- GREEN-BEAN hotspot still works for ESP32-CAM cameras

---

## Prerequisites

1. **RP and desktop on same network:**
   - Desktop connected to GREEN-BEAN (RP's WiFi hotspot) ✓
   - Both can ping each other

2. **Desktop has internet:**
   - Desktop is connected to ethernet or WiFi with internet ✓

3. **Linux desktop** (Windows/Mac not covered here)

---

## Step 1: Find Your Desktop's Network Interface Names

On your desktop, open terminal and run:

```bash
ip link show
```

You'll see output like:
```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN
2: enp3s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
3: wlp4s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
```

**Identify:**
- `INTERNET_INTERFACE` = the one with internet (your ethernet cable or WiFi)
- `GREEN_INTERFACE` = the one connected to GREEN-BEAN (RP's hotspot)

In the example above:
- `enp3s0` = ethernet (likely your internet)
- `wlp4s0` = WiFi connected to GREEN-BEAN

**To find which one has internet:**
```bash
ip route | grep default
```

Output will show something like:
```
default via 192.168.1.1 dev enp3s0
```

This means `enp3s0` is your internet interface.

---

## Step 2: Find Your Desktop's IP on GREEN-BEAN Network

Run:
```bash
ip addr show | grep "10.42.0"
```

Output example:
```
inet 10.42.0.83/24 brd 10.42.0.255 scope global dynamic noprefixloute wlp4s0
```

**Remember:** `10.42.0.83` is your desktop's IP on GREEN-BEAN network.

---

## Step 3: Enable IP Forwarding (Desktop)

This allows your desktop to forward traffic from RP to the internet.

```bash
sudo bash << 'EOF'
echo 1 > /proc/sys/net/ipv4/ip_forward
echo "IP forwarding enabled"
EOF
```

---

## Step 4: Set Up NAT Rules (Desktop)

Replace `INTERNET_INTERFACE` and `GREEN_INTERFACE` with your actual interface names (e.g., `enp3s0` and `wlp4s0`).

```bash
INET_IFACE="enp3s0"
GREEN_IFACE="wlp4s0"

sudo bash << EOF
# Clear old rules (if any exist from previous setup)
iptables -t nat -F POSTROUTING 2>/dev/null || true
iptables -F FORWARD 2>/dev/null || true

# Set firewall policy to allow forwarding
iptables -P FORWARD ACCEPT

# Enable masquerading (NAT) on internet interface
iptables -t nat -A POSTROUTING -o $INET_IFACE -j MASQUERADE

# Allow traffic from GREEN-BEAN network to internet
iptables -A FORWARD -i $GREEN_IFACE -o $INET_IFACE -j ACCEPT

# Allow return traffic from internet back to GREEN-BEAN
iptables -A FORWARD -i $INET_IFACE -o $GREEN_IFACE -m state --state RELATED,ESTABLISHED -j ACCEPT

echo "NAT configured!"
EOF
```

---

## Step 5: Configure RP's Default Gateway

Tell the RP to use your desktop as the gateway to reach the internet.

```bash
ssh pi@10.42.0.1 'sudo ip route add default via 10.42.0.83'
```

Replace `10.42.0.83` with your desktop's IP from Step 2.

---

## Step 6: Verify It Works (RP)

Test from RP:

```bash
ssh pi@10.42.0.1 'ping -c 2 8.8.8.8'
```

Expected output:
```
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=114 time=57.2 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=114 time=65.0 ms
```

Test DNS (DNS server address):

```bash
ssh pi@10.42.0.1 'ping -c 2 index.hu'
```

Expected output:
```
PING index.hu (81.0.120.158) 56(84) bytes of data.
64 bytes from 81.0.120.158: icmp_seq=1 ttl=48 time=64.3 ms
64 bytes from 81.0.120.158: icmp_seq=2 ttl=48 time=171 ms
```

**If both work:** ✓ RP has internet!

---

## Troubleshooting

### "ping: Temporary failure in name resolution"
DNS is not working. Check RP's DNS servers:

```bash
ssh pi@10.42.0.1 'cat /etc/resolv.conf'
```

If empty or wrong, set DNS:

```bash
ssh pi@10.42.0.1 'sudo bash << EOF
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 1.1.1.1" >> /etc/resolv.conf
EOF'
```

### "ping: Destination unreachable"
The gateway route is not set. Check:

```bash
ssh pi@10.42.0.1 'ip route show'
```

Should show:
```
default via 10.42.0.83 dev wlan0
```

If missing, re-run Step 5.

### Desktop's IP changed
If your desktop reconnects to GREEN-BEAN, it might get a new IP (like 10.42.0.84). Update the RP's gateway:

```bash
DESKTOP_IP=$(ip addr show | grep "10.42.0" | awk '{print $2}' | cut -d/ -f1)
ssh pi@10.42.0.1 "sudo ip route change default via $DESKTOP_IP"
```

---

## How to Revert (Disable Internet Sharing)

### On RP: Remove the default gateway route

```bash
ssh pi@10.42.0.1 'sudo ip route del default'
```

Verify it's gone:

```bash
ssh pi@10.42.0.1 'ip route show'
```

Should NOT show `default via ...`

### On Desktop: Disable NAT and forwarding

```bash
# Disable IP forwarding
sudo bash << 'EOF'
echo 0 > /proc/sys/net/ipv4/ip_forward

# Clear NAT and firewall rules
iptables -F FORWARD
iptables -t nat -F POSTROUTING

# Reset firewall policy to default
iptables -P FORWARD DROP

echo "NAT disabled, forwarding disabled"
EOF
```

### Verify revert works:

From RP, this should fail:
```bash
ssh pi@10.42.0.1 'ping -c 2 8.8.8.8'
```

Expected output:
```
From 10.42.0.83 icmp_seq=1 Destination unreachable
```

**✓ Internet sharing is now disabled.**

---

## How to Make It Permanent (Optional)

The settings above are temporary and reset on reboot. To make them permanent:

### On Desktop: Save IP forwarding

```bash
sudo bash << 'EOF'
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
EOF
```

### On Desktop: Save iptables rules

```bash
# Save current rules
sudo bash << 'EOF'
INET_IFACE="enp3s0"
GREEN_IFACE="wlp4s0"

iptables-save > /tmp/iptables-rules.txt

# Make them persistent (Debian/Ubuntu)
apt-get install iptables-persistent
iptables-save | sudo tee /etc/iptables/rules.v4 > /dev/null
EOF
```

### On RP: Make gateway permanent

```bash
ssh pi@10.42.0.1 'sudo bash << EOF
# Add to network config (if using NetworkManager)
nmcli connection modify Hotspot +ipv4.routes "0.0.0.0/0 10.42.0.83"
nmcli connection up Hotspot
EOF'
```

---

## What This Means

**Simple explanation:**

Your desktop acts like a **router/gateway** for the RP:
1. RP sends packets destined for the internet to your desktop
2. Desktop forwards them to the real internet
3. Internet replies back to your desktop
4. Desktop forwards replies back to RP

This is called **Network Address Translation (NAT)** - your desktop translates RP's local IP (10.42.0.x) to its own when talking to the internet.

---

## Common Questions

**Q: Will this affect the cameras?**
A: No. Cameras still connect to GREEN-BEAN hotspot normally. This only affects the RP itself.

**Q: What if I unplug the ethernet from my desktop?**
A: RP loses internet (unless your desktop has WiFi with internet too).

**Q: Can I do this with Windows/Mac?**
A: Yes, but steps are different. Windows has "Internet Connection Sharing" in settings. Mac has a similar feature. Search for "[OS] share internet connection" for step-by-step guides.

**Q: How do I know if it's working?**
A: Run `ping index.hu` on the RP. If it works, internet is working.

**Q: What if DNS doesn't work but ping 8.8.8.8 works?**
A: DNS servers aren't configured on RP. Follow the "Troubleshooting" section to set them.

