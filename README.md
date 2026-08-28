# GForms-Nuker v1.1.0
- Fixed add field button not working

A Python application for sending Google Forms submissions through a modern, cross-platform PySide6 GUI.
Functionality with forms that require you to be signed in or are limited to one response do not currently work, a fix is planned in the future!

---
## 📋 Overview
This application provides a graphical interface for configuring and sending repeated Google Forms submissions. It supports multiple answer sets, configurable submission speeds, progress tracking, error logging, and automatic configuration saving.
Built with Python, PySide6, and Requests, and designed to work on Linux & Windows.

---
## 🎯 How to Use
### 1. Get the form link
1. Open the Google Form.
2. Press **F12** (or right-click → Inspect) to open Developer Tools.
3. Go to the **Network** tab.
4. Fill out every required question with any valid answers and click **Submit**.
5. Stay on the “Your response has been recorded” page.
6. Copy the **entire URL** from the address bar and paste it into the **Google Form** field in the tool.
7. Click **Validate**.  
   You should see the green message **“Valid submission endpoint.”**

### 2. Extract the entry IDs (the questions)
1. In the Network tab, click the request named **`formResponse`**.
2. Open the **Payload** (or **Form Data**) tab.
3. You will see lines like:
entry.1394937983: I love mangoes
entry.9876543210: Yes
entry.1122334455: Option B
4. **For every `entry.XXXXXXXXX` you see:**
- Click **+ Add Field** inside Answer Set 1 (or use the existing empty field).
- Paste the full `entry.XXXXXXXXX` into the **Form Field** box.
- Paste the answer you submitted into the **Value** box next to it.
5. Repeat until **all** entry IDs from the Payload are added.  
(Do not skip any required questions or the submissions will fail.)

### 3. Add multiple answers (for randomisation)
- For questions with several options, list them in the **Value** field separated by `|`:
I love mangoes | Mangoes love me | Fried Chicken | Giga Nugget

- The tool will randomly choose one value for each submission.
- Click **+ Add Answer Set** if you need different combinations of answers.

### 4. Configure and run
1. Set the **Total submissions to send**.
2. Choose a **Submission Speed** (or leave on “No delay”).
3. Click **START**.
4. Monitor the Progress bar and Success / Failed counters.
5. Click **STOP** if you need to halt early.

### Troubleshooting
| “Valid submission endpoint” never appears | You copied a viewform URL instead of the formResponse URL. Re-submit the form and copy the new URL. |
| Submissions fail | Make sure every required entry is present and the values match the expected format. |
| Too many failures | Slow down the submission speed or reduce the total number of submissions. |

---
## ❗ Notice
This project is intended for educational purposes, testing forms you own or are authorised to test, and development use.
Do not use this application to spam, disrupt, or abuse third-party services.
Parts of this code repository were generated or assisted using artificial intelligence tools. Some functions, scripts, documentation, and development decisions were created with assistance from AI models.
