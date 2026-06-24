# 🤖 Copiertelebot - Telegram Forward Bot

A powerful Telegram bot that automatically forwards messages from one channel/group to another. Perfect for content aggregation, deal sharing, and team collaboration.

---

## 📌 **What Does This Bot Do?**

This bot copies messages from any Telegram channel/group and forwards them to your chosen destinations automatically.

**Think of it as a content aggregator that works 24/7!**

---

## 🚀 **Quick Start Guide**

### Step 1: Start the Bot

1. Open Telegram
2. Search for **@Copiertelebot**
3. Send the `/start` command
4. The main menu will appear

### Step 2: Create Your First Forwarding Job

Click **"▶️ Start Forwarding"** and follow these steps:

---

#### 1️⃣ **Enter Source Channel**

Where to copy messages from.

**Examples:**
✅ https://t.me/examplechannel/200 (starts from message #200)
✅ https://t.me/examplechannel (starts from message #1)
✅ @examplechannel
✅ -1001234567890

text

---

#### 2️⃣ **Add Destination Channel(s)**

Where to send messages. You can add multiple destinations!

**Examples:**
✅ @mychannel
✅ https://t.me/mychannel
✅ -1009876543210

text

Type `/done` when you've added all destinations.

---

#### 3️⃣ **Choose Message Count**

How many messages to forward from the starting point.

**⚠️ IMPORTANT:** The bot forwards messages **FORWARD** (to newer messages), not backward!

| Your Input | Starting At | Bot Forwards               |
| ---------- | ----------- | -------------------------- |
| `4`        | #50         | #50, #51, #52, #53         |
| `10`       | #100        | #100 to #109               |
| `30`       | #599        | #599 to #629               |
| `all`      | #100        | #100 to the END of channel |

---

#### 4️⃣ **Set Delay Between Messages**

Controls how fast messages are forwarded.

| Delay    | Speed        | Best For                        |
| -------- | ------------ | ------------------------------- |
| **0.5s** | 🚀 Fast      | Small jobs (under 200 messages) |
| **1s**   | ⚡ Balanced  | Recommended for most jobs       |
| **2s**   | 🐢 Safe      | Medium jobs (200-1000 messages) |
| **3s**   | 🐌 Very Safe | Large jobs (1000+ messages)     |

---

#### 5️⃣ **Choose Message Filter**

Select what type of messages to forward.

| Filter           | Description                                      |
| ---------------- | ------------------------------------------------ |
| **All Messages** | Forwards everything (text, photos, videos, etc.) |
| **Media Only**   | Only photos, videos, audio, documents            |
| **Text Only**    | Only text messages                               |
| **Photos Only**  | Only photos                                      |
| **Videos Only**  | Only videos                                      |
| **Docs Only**    | Only files and documents                         |

---

#### 6️⃣ **Confirm and Start**

Review your settings and click **"▶️ Start Now"** to begin forwarding!

---

## 📱 **Live Progress**

While forwarding, you'll see real-time updates:
🔄 COPYING IN PROGRESS
━━━━━━━━━━━━━━━━━━━━
📤 Source: @ChannelName
📥 Destination: 2 chats
━━━━━━━━━━━━━━━━━━━━
✅ Forwarded: 40/50 messages
⏭ Skipped: 2
❌ Errors: 0
📍 Current: msg #351
⏱ Elapsed: 3m 20s
⚡ Speed: ~12.5 msg/min
━━━━━━━━━━━━━━━━━━━━
📊 Progress: ████████░░ 80%
━━━━━━━━━━━━━━━━━━━━
[⏸️ Pause] [🛑 Stop]

text

**Buttons:**

- **⏸️ Pause** - Temporarily stop the job
- **▶️ Resume** - Continue a paused job
- **🛑 Stop** - Cancel the job permanently

---

## 📋 **Bot Features**

### For Users

| Feature                       | Description                                      |
| ----------------------------- | ------------------------------------------------ |
| 📥 **Source with Message ID** | Start from any specific message                  |
| 📤 **Multiple Destinations**  | Forward to multiple channels at once             |
| 📩 **Message Count**          | Choose exactly how many messages to forward      |
| ⏱️ **Delay Control**          | Control speed between messages                   |
| 🎛️ **Message Filters**        | All, Media Only, Text Only, Photos, Videos, Docs |
| 🔄 **Live Progress**          | See real-time progress with speed                |
| ⏸️ **Pause/Resume**           | Pause and resume anytime                         |
| 🛑 **Cancel Job**             | Stop running jobs                                |
| 📋 **My Jobs**                | View and manage all your jobs                    |
| 📜 **Job History**            | See completed jobs                               |
| 📊 **Statistics**             | Track total forwarded messages                   |
| ⚙️ **Settings**               | Strip links, mentions, default delay             |

---

## 💡 **Common Use Cases**

### 📰 **News Aggregator**

Collect news from multiple channels to one personal channel:
Sources: @BBCNews, @CNN, @TechCrunch
→ Forward to: @MyNewsChannel

text

### 🏷️ **Deal Sharing**

Share deals with friends automatically:
Source: @DealHunter
→ Forward to: @MyFriendsDeals

text

### 💾 **Content Backup**

Backup important channels to private archive:
Source: @ImportantChannel
→ Forward to: @BackupChannel

text

### 🤝 **Team Collaboration**

Share industry news with your team:
Source: @IndustryNews
→ Forward to: @TeamChannel

text

### 🔬 **Research Collection**

Collect data from multiple sources:
Sources: @MarketData, @StockNews
→ Forward to: @ResearchArchive

text

---

## 💡 **Tips & Best Practices**

### ✅ **Do's**

- Use **1-2 seconds delay** for large jobs (1000+ messages)
- Use **private channels** for personal archives
- Add bot as **admin** in destination channels
- Use **filters** to save space (Media Only for photos/videos)
- Check **live progress** to monitor jobs

### ❌ **Don'ts**

- Don't forward copyrighted content
- Don't use very low delay (0.1s) - may hit rate limits
- Don't forward spam or inappropriate content
- Don't remove bot from destination channels while job is running

---

## ❓ **Frequently Asked Questions**

### **Q: How does the message count work?**

A: The bot forwards **from the starting message ID forward**. For example:

- Start at #50, count=4 → Forwards #50, #51, #52, #53
- Start at #100, count=10 → Forwards #100 to #109
- Start at #599, count=30 → Forwards #599 to #629

### **Q: What does "all" do?**

A: "all" forwards from your starting message ID to the **very end of the channel**.

### **Q: Can I forward to multiple destinations?**

A: Yes! Add multiple destinations in the wizard. Type `/done` when finished.

### **Q: What happens if a message fails?**

A: The bot retries automatically (up to 3 times).

### **Q: Can I pause and resume?**

A: Yes! Use the pause/resume buttons on the status message.

### **Q: Is my content private?**

A: Yes! Only you and people you add to destinations can see the forwarded content.

### **Q: What happens if the bot restarts?**

A: The bot saves progress automatically and resumes from where it stopped.

### **Q: Does the bot work with private channels?**

A: Yes, but the bot must be added as an admin to the private channel.

### **Q: What message types are supported?**

A: All types! Text, Photos, Videos, Documents, Audio, Voice, Stickers, GIFs, Polls, Contacts, Locations, and Albums.

---

## 🔗 **Supported Formats**

### Source/Destination Formats:

✅ https://t.me/channelname
✅ https://t.me/channelname/200 (starts from message #200)
✅ https://t.me/c/1234567890/5
✅ @channelname
✅ -1001234567890

text

### Message Filters:

✅ All Messages → Everything
✅ Media Only → Photos, videos, audio, documents
✅ Text Only → Only text messages
✅ Photos Only → Only photos
✅ Videos Only → Only videos
✅ Docs Only → Only files

text

---

## 🛡️ **Requirements**

- Bot must be **admin** in destination channels
- Bot must be **member** of source channels (or public)
- Telegram account with bot token
- Stable internet connection

---

## 📝 **Commands**

| Command             | Description                |
| ------------------- | -------------------------- |
| `/start`            | Main menu                  |
| **Buttons**         |                            |
| ▶️ Start Forwarding | Create new forwarding job  |
| 📋 My Jobs          | View and manage your jobs  |
| ⚙️ Settings         | Configure your preferences |
| 📜 History          | View completed jobs        |
| 📊 Stats            | View your statistics       |
| ❓ Help             | Help guide                 |

---

## 🌟 **Why Choose This Bot?**

| Feature       | Benefit                                 |
| ------------- | --------------------------------------- |
| **Automatic** | No manual work, runs 24/7               |
| **Fast**      | Forward messages at high speed          |
| **Reliable**  | Saves progress on crash                 |
| **Flexible**  | Multiple sources, destinations, filters |
| **Real-time** | Live progress updates                   |
| **Control**   | Pause, resume, cancel anytime           |
| **Private**   | Your content stays private              |

---

## 📞 **Support**

For issues or questions:

- Check the **Help** section in the bot
- Contact bot admin
- Read the FAQ above

---

**Enjoy using @Copiertelebot!** 🚀
