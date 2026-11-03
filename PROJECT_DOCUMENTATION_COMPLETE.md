# 🛡️ ExamGuard AI — Full Technical Documentation & Architecture Report

> **Project Name:** ExamGuard AI (ExamGuard Pro)  
> **Type:** Full-Stack AI Proctored Assessment & Coding Platform  
> **Target Audience:** Universities, Colleges, Recruitment Firms & Technical Assessment Bodies  
> **Author / Maintainer:** Piyush Barnwal & Development Team  
> **Generated Date:** 2026-10-15  

---

## 📑 Table of Contents (अनुक्रमणिका)

1. [Executive Summary (प्रोजेक्ट का परिचय)](#1-executive-summary)
2. [Complete Technology Stack (कौन-कौन सी टेक्नोलॉजीज इस्तेमाल हुई हैं)](#2-complete-technology-stack)
3. [Core Features & Modules (क्या-क्या काम कर रहा है)](#3-core-features--modules)
4. [Internal Working Mechanism (कैसे काम करता है - Architecture & Logic)](#4-internal-working-mechanism)
5. [End-to-End Workflow (पूरा वर्कफ़्लो - Step-by-Step)](#5-end-to-end-workflow)
6. [UI & Screen Walkthrough (वेबसाइट पर क्या-क्या दिखता है)](#6-ui--screen-walkthrough)
7. [Security & Anti-Cheating Matrix (चीटिंग रोकने के सुरक्षा मानक)](#7-security--anti-cheating-matrix)
8. [Database Schema & Models (डेटाबेस संरचना)](#8-database-schema--models)
9. [API Endpoints Reference (बैकएंड API लिस्ट)](#9-api-endpoints-reference)
10. [Setup & Deployment Guide (प्रोजेक्ट चलाने की विधि)](#10-setup--deployment-guide)

---

## 1. Executive Summary

**ExamGuard AI** एक अत्याधुनिक, सिक्योर और ऑटोनॉमस **AI-Proctored Online Examination & Coding Assessment Platform** है। इसका मुख्य उद्देश्य दूरस्थ (remote) और कैंपस दोनों प्रकार की परीक्षाओं में नकल (cheating) को पूरी तरह रोकना और निष्पक्ष परीक्षा आयोजित करना है।

यह सिस्टम सामान्य ऑनलाइन क्विज़ सिस्टम्स से अलग है क्योंकि यह 4-लेयर सिक्योरिटी पर काम करता है:
1. **AI Computer Vision Proctoring:** वेबकैम के जरिए छात्र के चेहरे, पुतलियों (eyes gaze) और हरकतों को लाइव ट्रैक करता है।
2. **Browser Lockdown Security:** छात्र को टैब बदलने, शॉर्टकट दबाने (F12, Inspect, Alt+Tab, Esc) या स्क्रीन से हटने नहीं देता।
3. **Safe Exam Browser (SEB) Deep Integration:** एक कस्टम `.seb` फाइल और स्पेशल प्रोटोकॉल (`seb://`) के जरिए पूरे ऑपरेटिंग सिस्टम को लॉक कर देता है।
4. **Sandboxed Multi-Language Coding Arena:** Monaco Editor के साथ Python, C++ और Java के कोड को सुरक्षित रूप से टेस्ट केसों पर चलाता है और AI डिबगर सहायता प्रदान करता है।

---

## 2. Complete Technology Stack

ExamGuard AI में उद्योग-मानक (Industry standard) मॉडर्न टेक्नोलॉजीज का संयोजन किया गया है:

### 2.1 Backend (सर्वर साइड)
* **Python 3.10+**: मुख्य प्रोग्रामिंग भाषा।
* **FastAPI**: हाई-परफॉरमेंस, एसिंक्रोनस (Async/Await) REST API फ्रेमवर्क।
* **Uvicorn (Standard)**: लाइटवेट ASGI वेब सर्वर।
* **Pydantic v2 & Pydantic-Settings**: डेटा वैलिडेशन, स्ट्रिक्ट टाइप-चेकिंग और एनवायरनमेंट सेटिंग्स मैनेजमेंट।
* **SQLAlchemy (Asyncio)**: डेटाबेस ORM जो नॉन-ब्लॉकिंग क्वेरीज हैंडल करता है।
* **aiosqlite & asyncpg**: डेवलपमेंट में SQLite और प्रोडक्शन में PostgreSQL के लिए एसिंक्रोनस ड्राइवर्स।
* **Python-Jose (Cryptographic JWT)**: सुरक्षित एडमिन एवं स्टूडेंट सेशन ऑथेंटिकेशन।
* **Passlib & Bcrypt**: पासवर्ड्स और सीक्रेट 6-डिजिट PINs को क्रिप्टोग्राफिकली हैश करने के लिए।
* **Pandas, OpenPyXL, Xlrd**: एक्सेल शीट्स (`.xlsx`, `.xls`, `.csv`) से छात्रों का डेटा पढ़ने और डिटेल्ड रिपोर्ट फाइल बनाने के लिए।
* **Python-Multipart**: फाइल अपलोड्स (CSV/Excel) प्रोसेस करने के लिए।
* **SMTP (smtplib & ssl)**: Gmail/Sendgrid के जरिए ऑटोमेटेड इनविटेशन ईमेल भेजने के लिए।

### 2.2 Artificial Intelligence & Machine Learning (AI मॉडल्स)
* **Google MediaPipe Face Landmarker (v0.10.22)**:
  - ब्राउज़र में WebAssembly (WASM) और WebGL/GPU डेलिगेट पर रियल-टाइम चलता है।
  - 478 3D फेशियल लैंडमार्क्स ट्रैक करता है।
  - फेस एब्सेंस, लुकिंग अवे (Yaw/Pitch) और मल्टीपल फेसेज (एक से ज्यादा लोग) को 10-15 FPS पर ट्रैक करता है।
* **Google Gemini AI (LLM - `gemini-flash-latest`)**:
  - **AI Question Studio:** एडमिन जब टॉपिक और डिफिकल्टी देता है, तो Gemini ओरिजिनल प्रॉब्लम्स, 10 टेस्ट केसेस (2 विजिबल, 8 हिडन) और स्टार्टर कोड जनरेट करता है।
  - **AI Code Debugger:** कोडिंग एग्जाम के दौरान कंपाइलर एरर आने पर छात्र को टार्गेटेड हिंट देता है बिना डायरेक्ट कोड लीक किए।

### 2.3 Sandboxed Code Execution Engine (कोडिंग रनर)
* **Piston API (Remote Engine)**: डोकराइज्ड, आइसोलेटेड एनवायरनमेंट में कोड रन करने के लिए।
* **Local Subprocess Fallback Runner**: यदि रिमोट सर्वर डाउन हो, तो बैकएंड स्वतः लोकल `python`, `g++`, या `javac/java` सबप्रोसेस में सीमित टाइमआउट के साथ सुरक्षित रूप से कोड चलाता है।
* **Languages Supported**:
  - Python 3.x
  - C++ (C++17 standard)
  - Java (Java 17 standard)

### 2.4 Frontend (क्लाइंट साइड)
* **Core**: Modern HTML5, Semantic Elements, Vanilla JavaScript (ES Modules).
* **Styling**: Pure Vanilla CSS3 (नो हेवी फ्रेमवर्क, 100% कस्टमाइजेबल Glassmorphism, डार्क-थीम, रिस्पॉन्सिव ग्रिड, मॉडर्न स्टेट्स)।
* **Code Editor**: Microsoft Monaco Editor (वही एडिटर जो VS Code में होता है - सिंटैक्स हाइलाइटिंग, ऑटो-इंडेंटेशन, लाइन नंबर्स)।
* **Icons & Visuals**: SVG Icons, CSS Keyframe Micro-animations, Live Status Pills।

---

## 3. Core Features & Modules (क्या-क्या काम कर रहा है)

ExamGuard AI में 7 मुख्य मॉड्यूल्स पूरी तरह कार्यरत हैं:

### 1. Admin Command Center (एडमिन पैनल)
* **Secure Authentication**: यूजरनेम और पासवर्ड से एडमिन लॉगिन (JWT प्रोटेक्शन)।
* **Bulk Student Import**: कॉलेज या कंपनी की एक्सेल शीट (`.xlsx`, `.xls`, `.csv`) ड्रैग-एंड-ड्रॉप करके सैकड़ों छात्रों को एक क्लिक में अपलोड करना।
* **Automated PIN & Token Generation**: हर छात्र के लिए 6-अंकों का यूनिक पिन और सुरक्षित क्रिप्टोग्राफिक वन-टाइम इनवाइट टोकन तैयार होता है।
* **Instant Email Dispatch**: Gmail SMTP के जरिए सभी छात्रों को उनके नाम, रोल नंबर, और डायरेक्ट वन-क्लिक एग्जाम लिंक के साथ ईमेल भेजा जाता है।
* **Contest Scheduling**: परीक्षा की शुरुआत और समाप्ति का समय निर्धारित करना (Start Time, End Time, Publishing Switch)।
* **AI Question Studio**: किसी भी टॉपिक (जैसे `Dynamic Programming`, `SQL`, `Arrays`) पर तुरंत 3 से 10 सवाल जनरेट करना।
* **Audit & Export Reports**: परीक्षा के बाद छात्रों के स्कोर, पास किए गए टेस्ट केस, और चीटिंग वॉयलेशन की संख्या के साथ मल्टी-कॉलम एक्सेल रिपोर्ट डाउनलोड करना।

### 2. Student Verification & Gateways
* **Magic Link Login**: ईमेल में आए लिंक पर क्लिक करते ही छात्र स्वतः वेरीफाई हो जाता है।
* **Manual PIN Gateway**: छात्र अपना रोल नंबर और 6-डिजिट पिन डालकर भी सुरक्षित रूप से लॉगिन कर सकता है।
* **Safe Exam Browser (SEB) Detection**: सिस्टम चेक करता है कि छात्र सामान्य ब्राउज़र में है या SEB में। अगर SEB में नहीं है, तो डाउनलोड लिंक और ऑटो-लॉन्च बटन देता है।

### 3. AI Computer Vision Proctoring Engine
* **Face Missing Alert**: छात्र यदि कैमरे के सामने से हटता है या सिर झुकाकर टेबल के नीचे देखता है, तो तुरंत लॉग बनता है।
* **Looking Away / Gaze Detection**: छात्र यदि स्क्रीन के अलावा दाएं, बाएं, ऊपर या नीचे देखता है, तो पुतली (Iris center) और नाक के एंगल (Yaw & Pitch) से यह तुरंत पहचान लेता है।
* **Multiple Faces Detected**: यदि कैमरे में छात्र के अलावा कोई दूसरा व्यक्ति आता है, तो तुरंत गंभीर वॉयलेशन फ्लैग होता है।
* **Live Webcam Overlay**: छात्र को स्क्रीन के कोने में अपना लाइव कैमरा फीड दिखता रहता है ताकि वह सतर्क रहे।

### 4. Lockdown & Browser Security
* **Forced Fullscreen Mode**: परीक्षा केवल फुलस्क्रीन में ही चलती है। फुलस्क्रीन से बाहर आते ही स्क्रीन पर "Fullscreen Required" का ब्लैकआउट गार्ड आ जाता है।
* **Tab Switch & Window Blur Tracking**: छात्र दूसरा टैब खोले या किसी दूसरे सॉफ्टवेयर पर क्लिक करे, तो तुरंत `TAB_SWITCH` और `WINDOW_BLUR` इवेंट रिकॉर्ड हो जाता है।
* **Key-Combination Blocker**:
  - `F12` (Developer Tools)
  - `Ctrl + Shift + I`, `Ctrl + Shift + J`, `Ctrl + Shift + C` (Inspect Element)
  - `Ctrl + U` (View Page Source)
  - `Ctrl + S`, `Ctrl + P` (Save/Print)
  - `Alt + Tab` (Window Switch)
  - `Escape` (Fullscreen Exit Prevention)
  - Right-click (Context Menu) पूर्णतया डिसेबल्ड।
* **Beacon Keepalive Logging**: यदि छात्र पेज बंद करने या रीलोड करने की कोशिश करे, तो ब्राउज़र बैकग्राउंड बीकन (`navigator.sendBeacon`) के जरिए सर्वर को तुरंत सूचना देता है।

### 5. Monaco Coding Assessment Arena
* **Problem Statement Pane**: समस्या का विवरण, इनपुट फॉर्मेट, आउटपुट फॉर्मेट, कंस्ट्रेंट्स, और विजिबल सैंपल्स।
* **Language Switcher**: Python, C++, Java में तुरंत स्विच करने की सुविधा (भाषा बदलते ही उसका बॉयलरप्लेट कोड लोड होता है)।
* **Auto-Save Drafts**: छात्र जो भी कोड टाइप करता है, वह बैकएंड में ड्राफ्ट के रूप में स्वतः सेव होता रहता है, ताकि इंटरनेट जाने पर भी कोड लॉस न हो।
* **Run Samples (Test Run)**: छात्र केवल विजिबल सैंपल्स पर कोड चलाकर अपना आउटपुट और एरर्स चेक कर सकता है।
* **AI Debugger Hint**: अगर छात्र का कोड कंपाइल नहीं होता या रनटाइम एरर देता है, तो "AI Debug" बटन दबाने पर Gemini AI उसे कोड सुधारने का लॉजिकल हिंट देता है।
* **Submit Code (Final Evaluation)**: सबमिट करने पर कोड 10 टेस्ट केसेस (जिसमें हिडन केसेस भी शामिल हैं) पर चेक होता है और ऑटोमेटेड स्कोरिंग होती है।
* **Timer & Auto-Submit**: परीक्षा का समय समाप्त होते ही अंतिम ड्राफ्ट कोड स्वतः सबमिट हो जाता है।

### 6. Geofence & Network Telemetry
* छात्र का पब्लिक IP एड्रेस, नेटवर्क ISP और GPS जियोलोकेशन (छात्र की अनुमति से) कैप्चर किया जाता है।
* एडमिन द्वारा निर्धारित IP सबनेट से बाहर के छात्रों पर `IP_MISMATCH` का टैग लग जाता है।

---

## 4. Internal Working Mechanism (कैसे काम करता है)

```
+-----------------------------------------------------------------------------------+
|                              EXAMGUARD AI ARCHITECTURE                            |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ ADMIN ]                                                                        |
|     │                                                                             |
|     ├── 1. Uploads Excel/CSV ────────► [ Student Import Service (Pandas) ]       |
|     │                                                │                            |
|     ├── 2. Triggers Invites ─────────► [ Email Service (Gmail SMTP TLS) ]         |
|     │                                                │                            |
|     └── 3. Generates Questions ──────► [ Google Gemini 1.5 Flash API ]           |
|                                                                                   |
|  [ STUDENT ]                                                                      |
|     │                                                                             |
|     ├── 4. Clicks Invite Link ───────► [ Fast-Path Cryptographic Token Verify ]   |
|     │                                                │                            |
|     ├── 5. Environment Check ────────► [ SEB Gate / Pre-Flight Hardware Checks ]  |
|     │                                                │                            |
|     ├── 6. Live Webcam Video Stream ─► [ MediaPipe Vision Landmarker (WASM) ]     |
|     │                                                │                            |
|     ├── 7. Lockdown Guard ───────────► [ Fullscreen + Keydown + Blur Listeners ]  |
|     │                                                │                            |
|     └── 8. Writes Code ──────────────► [ Monaco Editor -> Auto Draft Sync ]       |
|                                                      │                            |
|                                        [ Execution Engine: Piston / Local Sub ]   |
|                                                      │                            |
|                                        [ Database: SQLite / PostgreSQL Async ]    |
|                                                      │                            |
|  [ ADMIN AUDIT ] ◄──────────────────── [ Excel Report Service (OpenPyXL) ]        |
+-----------------------------------------------------------------------------------+
```

### 4.1 AI Proctoring Vision Pipeline
1. ब्राउज़र छात्र के वेबकैम से 1080p/720p वीडियो फ्रेम प्राप्त करता है।
2. Google MediaPipe WebAssembly लाइब्रेरी 478 3D लैंडमार्क्स निकालती है।
3. **Face Missing:** यदि `faceLandmarks.length === 0` है, तो `FACE_MISSING` इवेंट 4 फ्रेम बाद फायर होता है।
4. **Multiple Faces:** यदि `faceLandmarks.length > 1` है, तो तुरंत `MULTIPLE_FACES` इवेंट ट्रिगर होता है।
5. **Gaze & Head Yaw/Pitch Calculation:**
   - नाक की टिप (Landmark 1) और दोनों आँखों के सेंटर (Landmark 33 & 263) के बीच की दूरी मापी जाती है।
   - पुतलियों (Landmarks 468-477) की स्थिति आँख के कोनों के सापेक्ष कैलकुलेट की जाती है।
   - शुरुआती 18 फ्रेम्स में छात्र का न्यूट्रल (सीधा) चेहरा कैलिब्रेट होता है। इसके बाद यदि छात्र दाएं या बाएं 14% से अधिक देखता है या ऊपर-नीचे 22% से अधिक मुड़ता है, तो `LOOKING_AWAY` का लॉग बनता है।
   - बार-बार डुप्लीकेट रिक्वेस्ट रोकने के लिए 5 सेकंड का स्मार्ट कूलडाउन लगाया गया है।

### 4.2 Sandboxed Code Execution Pipeline
1. जब छात्र **Run Samples** या **Submit Code** दबाता है, तो कोड और भाषा FastAPI बैकएंड पर भेजी जाती है।
2. बैकएंड पहले Piston सैंडबॉक्स API को कॉल करता है (आइसोलेटेड लिनक्स कंटेनर)।
3. यदि नेटवर्क या टोकन की समस्या हो, तो फॉलबैक इंजन एक्टिवेट होता है:
   - एक अस्थायी डायरेक्टरी (`tempfile.mkdtemp`) बनाई जाती है।
   - कोड फाइल राइट होती है (`main.py`, `main.cpp`, या `Main.java`)।
   - C++ के लिए `g++ -O2 -std=c++17 main.cpp -o solution` रन होता है।
   - Java के लिए `javac Main.java` और `java Main` रन होता है।
   - टाइमआउट (2000ms) के साथ सबप्रोसेस रन होती है ताकि इनफिनिट लूप सर्वर क्रैश न करे।
   - टेस्ट केस का इनपुट stdin में पास किया जाता है और stdout को expected output से `_normalize_output()` के जरिए मैच किया जाता है।
   - स्कोर कैलकुलेट होकर परिणाम तुरंत छात्र के कंसोल में प्रदर्शित होता है।

---

## 5. End-to-End Workflow (पूरा वर्कफ़्लो)

### चरण 1: परीक्षा की तैयारी (Admin)
1. एडमिन `/src/pages/admin.html` खोलता है और लॉगिन करता है (`admin` / `admin123`)।
2. **Contest Schedule Tab** में जाकर परीक्षा का नाम, शुरू होने की तारीख/समय और खत्म होने का समय सेट करता है।
3. **AI Question Studio Tab** में जाकर टॉपिक (जैसे "Data Structures") और डिफिकल्टी चुनकर **Generate Questions** पर क्लिक करता है। जेमिनी AI तुरंत सवाल और टेस्ट केसेस बना देता है।

### चरण 2: छात्रों का रजिस्ट्रेशन और ईमेल इनवाइट (Admin)
1. एडमिन **Students & Bulk Invites Tab** में अपनी कॉलेज एक्सेल शीट (`students.xlsx`) ड्रैग-एंड-ड्रॉप करता है।
2. "Automatically send invite emails" चेकबॉक्स ऑन रहता है।
3. **Upload & Send Invites** दबाते ही बैकएंड सभी छात्रों को डेटाबेस में सेव करता है, उनके लिए सीक्रेट पिन जनरेट करता है और जीमेल SMTP से तुरंत सबको मेल भेज देता है।

### चरण 3: छात्र का प्रवेश (Student)
1. छात्र अपने इनबॉक्स में ईमेल खोलता है। ईमेल में उसे उसका नाम, रोल नंबर, और "Start Proctored Exam" का लिंक दिखता है।
2. लिंक पर क्लिक करते ही छात्र का टोकन स्वतः वेरीफाई हो जाता है।
3. यदि छात्र सामान्य ब्राउज़र में है, तो उसे SEB गेट दिखता है जहाँ वह SEB कॉन्फ़िग डाउनलोड कर सकता है या सीधे आगे बढ़ सकता है।

### चरण 4: सिस्टम प्री-चेक (Hardware Verification)
1. छात्र की स्क्रीन पर डायग्नोस्टिक्स पैनल आता है।
2. "Initiate Security Checks" दबाते ही:
   - वेबकैम परमिशन मांगी जाती है।
   - लोकेशन परमिशन चेक होती है।
   - फुलस्क्रीन मोड एक्टिवेट किया जाता है।
3. तीनों ग्रीन होते ही छात्र सीधे कोडिंग कंसोल में पहुंच जाता है और AI मॉनिटरिंग बैकग्राउंड में चालू हो जाती है।

### चरण 5: परीक्षा संचालन (Live Assessment)
1. बाईं तरफ समस्या का पूरा विवरण, सैंपल इनपुट/आउटपुट दिखता है।
2. बीच में Monaco Code Editor में छात्र अपना समाधान लिखता है।
3. हर 30 सेकंड में छात्र का कोड ड्राफ्ट बैकएंड में ऑटो-सेव होता रहता है।
4. छात्र "Run Samples" करके विजिबल केसेस चेक करता है।
5. यदि छात्र नकल करने के लिए टैब स्विच करता है या कोई और व्यक्ति कैमरे में आता है, तो स्क्रीन पर चेतावनी आती है और बैकएंड में घटना टाइमस्टैम्प के साथ रिकॉर्ड हो जाती है।
6. छात्र "Submit Code" पर क्लिक करता है। कोड सभी 10 टेस्ट केसेस पर टेस्ट होकर फाइनल स्कोर दर्ज कर देता है।

### चरण 6: परिणाम और ऑडिट (Post-Exam Admin)
1. परीक्षा का समय पूरा होने के बाद एडमिन **Exam Reports & History Tab** में जाता है।
2. वहाँ कुल सबमिशन, छात्रवार स्कोर, और प्रोक्टर वॉयलेशन दिखते हैं।
3. **Export Excel Report** बटन पर क्लिक करते ही संपूर्ण विस्तृत रिपोर्ट `.xlsx` फॉर्मेट में डाउनलोड हो जाती है।

---

## 6. UI & Screen Walkthrough (वेबसाइट पर क्या-क्या दिखता है)

| पेज का नाम | फाइल पाथ | क्या-क्या प्रदर्शित होता है? |
|---|---|---|
| **1. Landing Home** | `frontend/index.html` | मॉडर्न डार्क-थीम हीरो सेक्शन, प्लेटफॉर्म फीचर्स (AI Vision, SEB Lockdown, Bulk Invites, Code Sandbox), सिस्टम ऑपरेशनल स्टेटस पिल्स, स्टूडेंट और एडमिन पोर्टल के डायरेक्ट बटन्स। |
| **2. Auth Portal** | `frontend/src/pages/login.html` | स्टूडेंट लॉगिन (रोल नंबर + 6-डिजिट पिन) और एडमिन लॉगिन फॉर्म का स्विचिंग टैब। |
| **3. SEB Gate Verification** | `frontend/src/pages/student-exam.html` | सेफ एग्जाम ब्राउज़र चेकिंग गेट, Open in SEB बटन, Download `.seb` कॉन्फ़िग, Download Safe Browser `.exe`, और Standard Proctored Mode में जाने का विकल्प। |
| **4. Hardware Precheck** | `frontend/src/pages/exam.html` | 4-स्टेप डायग्नोस्टिक्स: System Readiness, Webcam Video Feed, Geolocation Access, Fullscreen Lock। |
| **5. Student Exam Workspace** | `frontend/src/pages/exam.html` | • **शीर्ष पट्टी:** लाइव सिक्योरिटी स्टेटस, IP चेकर, फुलस्क्रीन इंडिकेटर।<br>• **लेफ्ट पेन:** प्रॉब्लम स्टेटमेंट, इनपुट/आउटपुट फॉर्मेट, कंस्ट्रेंट्स, सैंपल्स।<br>• **सेंटर पेन:** Monaco Editor, लैंग्वेज सिलेक्टर (Python/C++/Java), रन और सबमिट बटन, लाइव एग्जाम क्लॉक।<br>• **राइट पेन:** एग्जीक्यूशन कंसोल, टेस्ट केस रिजल्ट्स (Passed/Failed), AI डिबगर हिंट बॉक्स।<br>• **फ्लोटिंग बॉक्स:** टॉप-राइट में छात्र का लाइव वेबकैम AI प्रिव्यू। |
| **6. Admin Command Center** | `frontend/src/pages/admin.html` | • **मेट्रिक ग्रिड:** Total Students, Invites Sent, Pending Invites, Contest Status।<br>• **Tab 1 (Students):** ड्रैग-एंड-ड्रॉप एक्सेल/CSV अपलोडर, बल्क सेंड इनवाइट्स बटन, छात्रों की लाइव लिस्ट, रोल नंबर, स्टेटस (ACCEPTED / PENDING), रीसेंड ईमेल बटन।<br>• **Tab 2 (Schedule):** कॉन्टेस्ट टाइटल, स्टार्ट टाइम, एंड टाइम पिकर, पब्लिश टॉगल।<br>• **Tab 3 (AI Studio):** टॉपिक इनपुट, डिफिकल्टी सिलेक्टर, क्वेश्चन काउंट, जेमिनाई जनरेटेड सवालों का लाइव एडिटर।<br>• **Tab 4 (Reports):** पिछली परीक्षाओं की लिस्ट, सबमिशन काउंट, एक्सेल रिपोर्ट एक्सपोर्ट बटन। |

---

## 7. Security & Anti-Cheating Matrix

| चीटिंग का तरीका | ExamGuard AI इसे कैसे रोकता और पकड़ता है? | बैकएंड लॉग इवेंट |
|---|---|---|
| **दूसरा टैब खोलना** | `visibilitychange` लिसनर से स्क्रीन ब्लर होते ही डिटेक्शन। | `TAB_SWITCH`, `VISIBILITY_HIDDEN` |
| **ब्राउज़र विंडो मिनिमाइज करना** | `window.onblur` लिसनर से तुरंत फोकस लॉस नोट होता है। | `FOCUS_LOST`, `WINDOW_BLUR` |
| **F12 दबाकर Inspect खोलना** | `keydown` इवेंट में F12, Ctrl+Shift+I/J/C ब्लॉक और प्रिवेंट होता है। | `BLOCKED_KEY` |
| **स्क्रीन से उठकर चले जाना** | MediaPipe Face Landmarker चेहरा न दिखने पर तुरंत अलर्ट देता है। | `FACE_MISSING` |
| **बगल में बैठे दोस्त से पूछना** | MediaPipe पुतली और सिर के एंगल (Yaw/Pitch) से लुकिंग अवे पकड़ता है। | `LOOKING_AWAY` |
| **कैमरे में किसी दूसरे का आना** | 2 या अधिक चेहरे डिटेक्ट होते ही सिस्टम तुरंत मार्क करता है। | `MULTIPLE_FACES` |
| **राइट क्लिक करके कॉपी-पेस्ट** | पूरे पेज पर `contextmenu` डिसेबल है और क्लिपबोर्ड मॉनिटर होता है। | `BLOCKED_KEY` |
| **अलग लोकेशन या IP से टेस्ट देना**| क्लाइंट का पब्लिक IP और सबनेट चेक होता है। | `IP_MISMATCH` |
| **समय खत्म होने पर कोड बचाना** | ऑटो-ड्राफ्ट सिंक हर 30 सेकंड में होता है और टाइमर खत्म होते ही ऑटो-सबमिट। | `AUTO_SUBMIT` |

---

## 8. Database Schema & Models

डेटाबेस में निम्नलिखित मुख्य टेबल्स हैं:

1. **`students`**: छात्र का नाम, ईमेल, रोल नंबर, हैश किया हुआ सीक्रेट पिन, इनवाइट टोकन, इनवाइट स्टेटस (`PENDING`/`ACCEPTED`), एक्सपायरी टाइम।
2. **`exam_sessions`**: छात्र की लाइव परीक्षा का सत्र, लॉगिन समय, समाप्ति समय, IP एड्रेस, नेटवर्क ISP, लोकेशन।
3. **`exam_logs`**: परीक्षा के दौरान हुई हर संदिग्ध गतिविधि (Event Type, Timestamp, Details JSON)।
4. **`coding_contests`**: परीक्षा का नाम, शुरू समय, खत्म समय, पब्लिश स्टेटस।
5. **`coding_problems`**: कोडिंग सवाल, प्रॉब्लम स्टेटमेंट, इनपुट/आउटपुट फॉर्मेट, कंस्ट्रेंट्स, स्टार्टर कोड्स (Python, C++, Java), मैक्सिमम स्कोर।
6. **`coding_test_cases`**: सवाल के 10 टेस्ट केसेस (इनपुट, एक्सपेक्टेड आउटपुट, विजिबिलिटी फ्लैग: True/False)।
7. **`code_drafts`**: छात्र द्वारा एडिटर में लिखा जा रहा रियल-टाइम कोड (ऑटो-सेव ड्राफ्ट)।
8. **`code_submissions`**: छात्र का फाइनल सबमिशन, सोर्स कोड, भाषा, पास हुए टेस्ट केसेस की संख्या, कुल स्कोर, कंपाइलर लॉग्स।

---

## 9. API Endpoints Reference

### 🔐 Auth Router (`/api/auth`)
* `POST /api/admin-login` — एडमिन प्रमाणीकरण और JWT टोकन प्राप्ति।
* `POST /api/student-login` — रोल नंबर और सीक्रेट पिन द्वारा छात्र लॉगिन।
* `POST /api/verify-invite` — ईमेल मैजिक लिंक के वन-टाइम टोकन का सत्यापन।
* `POST /api/verify-pin` — 6-अंकों के पिन का सत्यापन।

### 👥 Admin Router (`/api/admin`)
* `POST /api/import-students` — एक्सेल/CSV से छात्र इम्पोर्ट और ऑटो-इनवाइट ईमेल डिस्पैच।
* `GET /api/students` — पंजीकृत छात्रों की सूची और उनकी स्थिति।
* `POST /api/students/{id}/resend-invite` — किसी विशेष छात्र को दोबारा इनवाइट भेजना।
* `POST /api/send-invites` — सभी पेंडिंग छात्रों को इनवाइट ईमेल भेजना।
* `POST /api/generate-pins` — नए 6-डिजिट पिन जनरेट करना।
* `GET /api/export` — एक्सेल शीट रिपोर्ट (`.xlsx`) डाउनलोड करना।
* `POST /api/email-test` — Gmail SMTP क्रेडेंशियल्स की लाइव टेस्टिंग।

### 💻 Contest & Coding Router (`/api/contest`)
* `GET /api/status` — परीक्षा की वर्तमान स्थिति और टाइमर चेक करना।
* `GET /api/schedule` & `PUT /api/schedule` — परीक्षा शेड्यूल देखना और अपडेट करना।
* `PUT /api/draft` — छात्र के कोड को बैकग्राउंड में ऑटो-सेव करना।
* `POST /api/run-samples` — विजिबल सैंपल टेस्ट केसेस पर कोड टेस्ट करना।
* `POST /api/debug` — कंपाइलर एरर पर Gemini AI से स्मार्ट हिंट प्राप्त करना।
* `POST /api/auto-submit-draft` — अंतिम ड्राफ्ट को आधिकारिक सबमिशन बनाना।

### 👁️ Tracking & Telemetry Router (`/api/tracking`)
* `POST /api/tracking/events` — AI प्रिव्यू और लॉकडाउन वॉयलेशन इवेंट्स रिकॉर्ड करना।
* `GET /api/tracking/ip` — छात्र का पब्लिक IP एड्रेस पहचानना।
* `GET /api/tracking/geofence/check` — छात्र के नेटवर्क सबनेट की अनुमति जांचना।

### 🧠 Question Studio Router (`/api/questions`)
* `POST /api/questions/generate` — Google Gemini द्वारा स्वचालित कोडिंग सवाल तैयार करना।

---

## 10. Setup & Deployment Guide

### बैकएंड कैसे चलाएं (Local Machine):
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
* **API Documentation (Swagger UI):** `http://127.0.0.1:8000/docs`

### फ्रंटएंड कैसे चलाएं:
```bash
cd frontend
npm install
npm run dev
```
* **लोकल एक्सेस:** `http://localhost:5173` या सीधे `frontend/index.html` को किसी भी ब्राउज़र में खोलें।

### एनवायरनमेंट वेरिएबल्स (`backend/.env`):
```ini
APP_NAME="ExamGuard AI"
SECRET_KEY="your-super-secret-jwt-key"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="admin123"

# Gmail SMTP Email Dispatch
SMTP_HOST="smtp.gmail.com"
SMTP_PORT=587
SMTP_USER="your-email@gmail.com"
SMTP_PASSWORD="your-16-digit-app-password"
EMAIL_FROM="ExamGuard AI <your-email@gmail.com>"
SMTP_STARTTLS=true

# Google Gemini AI Key
GEMINI_API_KEY="your-gemini-api-key"
GEMINI_MODEL="gemini-flash-latest"

# Piston Sandbox (Optional)
PISTON_API_URL="https://emkc.org/api/v2/piston"
```

---

## 🏁 Conclusion

**ExamGuard AI** एक प्रोडक्शन-रेडी, स्केलेबल और आधुनिक प्लेटफॉर्म है जो शैक्षणिक संस्थानों और टेक रिक्रूटर्स को बिना किसी इंसानी दखल के निष्पक्ष, पारदर्शी और सुरक्षित ऑनलाइन कोडिंग परीक्षाएं आयोजित करने की पूरी ताकत देता है।
