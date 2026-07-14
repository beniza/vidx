# 🌟 Welcome to VIDX — The Scripture Video Engine
*The Complete Guide to Generating and Publishing Audio Bibles*

**Repository:** https://github.com/beniza/vidx

---

## 💡 Why Do We Need VIDX? (The "WHY")

Audio Bibles change lives, but sharing them online requires visual engagement. To publish scripture on YouTube, Facebook, or WhatsApp, you need **timed lyric and subtitle videos** where the text highlights in perfect sync with the audio narration.

Creating timed videos for **28 chapters of Matthew** or **260 chapters of the New Testament** using traditional video editing software (like DaVinci Resolve or Adobe Premiere) takes hundreds of hours of repetitive manual work: importing audio, positioning text, adjusting fonts, adding background music, and exporting one chapter at a time.

**How VIDX Solves This:**
VIDX automates the entire video production pipeline. You provide your scripture translation text (USFM files), your audio narration recordings, and your timing files. VIDX acts as an automated studio technician:
1. It reads your text and aligns it with your timing files.
2. It blends your background video, ministry logo watermark, introductory title cards, and background music (with automatic audio ducking).
3. It renders broadcast-quality widescreen (16:9) or vertical Shorts/Reels (9:16) MP4 videos in minutes!
4. Finally, it organizes your videos and thumbnails, ready for one-click publishing or automated background uploading to YouTube!

---

## 📦 What is Inside Your VIDX Package? (The "WHAT")

When you receive a VIDX project package from your team coordinator, here is what you will find inside your project folder:

| Item | What is it? | Why is it needed? |
| :--- | :--- | :--- |
| **`vidx.exe`** | The standalone software engine | A portable Windows executable that runs without needing Python or complex installations. |
| **Scripture Files (`.SFM`)** | Your translation text | Standard USFM scripture files containing books, chapters, and verses. |
| **Timing Files (`-timing.txt`)** | Audacity timing labels | Text files that tell VIDX the exact millisecond when each verse or phrase is spoken. |
| **Media Assets (`src/`)** | Videos, music, and logos | Background motion videos (`bg.mp4`), audio narrations, background music (`bg-music.mp3`), and your logo watermark (`logo.png`). |
| **Recipe File (`.yaml`)** | Your Project Configuration | A simple text file (like `sindhi_matthew_batch.yaml`) where you choose your font, colors, watermark position, and chapter list. |

---

## 🚀 How to Create Your Scripture Videos (The "HOW")

Generating your entire book of videos is a simple 3-step process:

### Step 1: Open Your Terminal / Command Prompt
1. Open your Windows File Explorer and navigate to your project folder.
2. Click on the address bar at the top, type `powershell` (or `cmd`), and press **Enter**. This opens a command window right inside your project folder.

### Step 2: Review or Adjust Your Recipe File (Optional)
Open your project's `.yaml` file (e.g., `examples/sindhi_matthew_batch.yaml`) in Notepad or any text editor. Everything is pre-configured by your project coordinator, but you can easily tweak visual settings:
```yaml
style:
  verse:
    font: "Nirmala UI"          # The font used for scripture text
    color: "&H00FFFFFF"         # White text
    outline_color: "&H00000000" # Black outline for readability
  heading:
    color: "&H00FFFFFF"         # White chapter headings
    position: 5                 # Position on screen (Numpad: 5=Center, 8=Top, 2=Bottom)

video:
  watermark:
    image: "src/logo/logo.png"  # Your ministry logo
    position: 4                 # Numpad position (4=Middle-Left, 9=Top-Right, 1=Bottom-Left)
    opacity: 50                 # 50% transparency so it doesn't distract from text

audio:
  background_music_volume: 0.80 # Volume of instrumental background music
```

### Step 3: Run the Video Generator!
In your command window, type the following command and press **Enter**:

```powershell
.\dist\vidx.exe -c examples/sindhi_matthew_batch.yaml
```
*(Tip: If your `vidx.exe` is in the main folder, type `.\vidx.exe -c your_config.yaml`).*

> **💡 Producing a full book on a GPU machine:** if you have an NVIDIA/Intel GPU and a whole book
> to render, this is the command pattern actually used in production across multiple books:
> ```powershell
> .\dist\vidx.exe -c examples/sindhi_matthew_batch.yaml --gpu -y -w 4
> ```
> `--gpu` turns on hardware encoding, `-w 4` renders 4 chapters at once, and `-y` auto-confirms
> the one-time prompt to downscale an oversized (e.g. 4K) background video to 1080p.

**What happens next:**
VIDX will begin processing your chapters. You will see a live progress bar on your screen showing the speed and rendering status of each chapter. Sit back and let VIDX do the heavy lifting! When it finishes, your completed videos will be waiting inside the `output/` folder.

> **💡 Subtitle-Only Mode:** Need just subtitle files (`.srt` or `.ass`) for YouTube or broadcast without waiting for video rendering? Add `--generate-only`:
> ```powershell
> .\dist\vidx.exe -c examples/sindhi_matthew_batch.yaml --generate-only --format both
> ```

---

## 📺 How to Publish Your Videos to YouTube

Once your videos are generated, you need to get them onto your YouTube channel. Because uploading dozens of chapters manually is tedious, and because **Google limits automated uploads** (to around **5 to 6 videos per day** per project), VIDX provides two smart publishing workflows:

---

### 📁 Method 1: The Easy Drag-and-Drop Method (No Setup Needed)
*Best for team members with slower internet or those who prefer uploading via their web browser without developer setup.*

When you run your video generation, VIDX automatically creates a special folder inside your output directory called **`YouTube_Upload_Package`**. Inside it, every chapter gets its own isolated folder (e.g., `Matthew_Ch01/`, `Matthew_Ch02/`).

Each chapter folder contains exactly 3 items:
1. **The Video (`.mp4`)**: Your rendered scripture video.
2. **The Thumbnail (`title_card.jpg`)**: Your title card image, ready to be used as your YouTube cover photo!
3. **The Metadata (`metadata.txt`)**: A text file containing the pre-written video title, verse description, copyright text, and hashtags!

**How to publish:**
1. Open **[YouTube Studio](https://studio.youtube.com/)** in your web browser and click **Create -> Upload Videos**.
2. Drag and drop the `.mp4` video file from your folder into the browser.
3. Open `metadata.txt` and copy-paste the Title and Description directly into YouTube.
4. Under Thumbnail, upload `title_card.jpg`.
5. Select your playlist and click **Publish**!

---

### 🚀 Method 2: Automated Background Uploading (Google Cloud API)
*Best for users with stable internet who want VIDX to upload directly to YouTube in the background.*

To let VIDX upload videos automatically, Google requires a one-time free developer setup to create an OAuth Client Key:

#### Step A: Create your Google Cloud Key (Updated for 2026 Console UI)
1. Go to the **[Google Cloud Console](https://console.cloud.google.com/)** in your browser and sign in.
2. Click **Select a project -> New Project**, name it `VIDX Uploader`, and click **Create**.
3. Go to **APIs & Services > Library**, search for **"YouTube Data API v3"**, and click **Enable**.
4. Go to **APIs & Services > OAuth consent screen** (or **Google Auth Platform / Audience** in newer layouts):
   - Select **External** and click **Create**. Give your app a name.
   - **⚠️ CRITICAL STEP — Add Team Emails:** On the **Test users** (or Audience) step, click **"+ ADD USERS"**. Type your Google/YouTube email address and the emails of any teammates who will be uploading. *(Apps in testing status will reject logins from anyone not on this list!)*
5. Go to **APIs & Services > Credentials**:
   - Click **+ CREATE CREDENTIALS -> OAuth client ID -> Desktop app**.
   - Click **DOWNLOAD JSON** to download your secret key file.

#### Step B: Place Your Key File
1. On your Windows PC, open File Explorer, go to your home folder (`C:\Users\YourUsername\`), and create a new folder named `.vidx`.
2. Copy the downloaded JSON file into that folder and rename it to **`client_secrets.json`**.

#### Step C: Launch the Upload!
Once your video generation is done, run this command in your terminal:
```powershell
.\dist\vidx.exe --manifest output/matthew_sindhi/publish_manifest.json
```
1. A browser window will open asking you to sign in with your Google account.
2. If Google warns *"Google hasn't verified this app"*, don't worry! This is normal for private tools. Click **Advanced -> Go to VIDX Uploader (unsafe) -> Allow**.
3. VIDX will immediately begin uploading your videos, attaching thumbnails, and assigning them to your playlist!

> **💡 How VIDX Handles Daily Limits:** When you upload 5 or 6 chapters, Google's daily quota will pause the upload. VIDX cleanly saves its place in `publish_manifest.json`. Tomorrow morning, simply run the exact same command (`.\dist\vidx.exe --manifest ...`), and VIDX will instantly resume from Chapter 07 without re-rendering any video files!

---

## ❓ Troubleshooting & Common Questions

### Q1: My scripture text appears as square "tofu" boxes or question marks.
**Answer:** The font specified in your `.yaml` recipe file (e.g., `"Nirmala UI"`, `"Mangal"`, `"Bailey"`) is not installed on your Windows computer. Check your installed Windows fonts and update `style.verse.font` in your `.yaml` file to match an installed font!

### Q2: Why did my upload fail with "Error 403: access_denied" when logging in?
**Answer:** The Google account you are trying to sign in with has not been added to the **Test Users** list in Google Cloud Console. Go back to Method 2 Step A (OAuth Consent Screen / Audience), click **+ Add Users**, add that exact email address, and try again!

### Q3: How do I change between horizontal 16:9 widescreen and vertical 9:16 Shorts/Reels?
**Answer:** In your `.yaml` recipe file under `video:`, simply change `resolution: "1920x1080"` (widescreen) to `resolution: "1080x1920"` (vertical) and set `scaling_mode: "crop"`. VIDX will automatically crop your background video to fit mobile screens!

### Q4: If my internet disconnects during an upload, do I lose my progress?
**Answer:** No! VIDX uses Google's *resumable chunked upload protocol*. If your internet disconnects at 80% completion on Chapter 04, running the manifest command again will resume uploading from byte 80% without restarting from zero!
