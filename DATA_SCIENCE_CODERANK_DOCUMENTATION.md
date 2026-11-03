# 📊 College CodeRank — Data Science & Student Coding Analytics Platform
## Complete Technical Documentation & System Architecture Report

> **Project Name:** College CodeRank (Data Science Analytics & Coding Leaderboard)  
> **Directory:** `C:\Users\piyus\OneDrive\Desktop\DATA SCIENCE\college-coderank`  
> **Category:** Data Science, Full-Stack Web Development, Multi-Platform Web Scraping & Performance Analytics  
> **Target Audience:** Universities, Engineering Colleges (Rungta College), Placement Cells & Coding Clubs  
> **Generated Date:** 2026-10-15  

---

## 📑 Table of Contents (अनुक्रमणिका)

1. [Executive Summary (प्रोजेक्ट का परिचय)](#1-executive-summary)
2. [Complete Technology Stack (कौन-कौन सी टेक्नोलॉजीज इस्तेमाल हुई हैं)](#2-complete-technology-stack)
3. [Core Features & Modules (क्या-क्या काम कर रहा है)](#3-core-features--modules)
4. [Internal Working Mechanism (कैसे काम करता है - Architecture & Logic)](#4-internal-working-mechanism)
5. [Data Science Scoring Formula (वेटेड स्कोरिंग अल्गोरिदम)](#5-data-science-scoring-formula)
6. [End-to-End Workflow (पूरा वर्कफ़्लो - Step-by-Step)](#6-end-to-end-workflow)
7. [UI & Screen Walkthrough (वेबसाइट पर क्या-क्या दिखता है)](#7-ui--screen-walkthrough)
8. [Database Schema & Data Models (डेटाबेस मॉडल)](#8-database-schema--data-models)
9. [API Endpoints Reference (बैकएंड API लिस्ट)](#9-api-endpoints-reference)
10. [Setup & Execution Guide (प्रोजेक्ट चलाने की विधि)](#10-setup--execution-guide)

---

## 1. Executive Summary

**College CodeRank** एक मॉडर्न, हाई-परफॉरमेंस **Data Science & Student Coding Performance Analytics Platform** है। इसका मुख्य उद्देश्य कॉलेज के छात्रों की अलग-अलग ग्लोबल कोडिंग प्लेटफॉर्म्स पर की गई कोडिंग एक्टिविटी (प्रॉब्लम्स सॉल्व, कॉन्टेस्ट रेटिंग, कमिट्स) को एक ही जगह ऑटोमैटिक कलेक्ट (Scrape/Sync), एग्रीगेट, और विजुअलाइज करना है।

यह प्लेटफॉर्म 5 प्रमुख प्लेटफॉर्म्स से रियल-टाइम डेटा फेच करता है:
1. **LeetCode** (Easy, Medium, Hard प्रॉब्लम्स, हाल ही में सॉल्व किए गए 50 सवाल, कॉन्टेस्ट रैंकिंग)
2. **CodeChef** (करंट रेटिंग, स्टार रेटिंग 1★-7★, डिवीजन, प्रॉब्लम्स सॉल्वड, ग्लोबल व कंट्री रैंक)
3. **GeeksforGeeks (GFG)** (कोडिंग स्कोर, सॉल्वड प्रॉब्लम्स, कॉलेज/इंस्टिट्यूट रैंक)
4. **HackerRank** (कुल पॉइंट्स, बैजेस, सॉल्व किए गए चैलेंजेस)
5. **GitHub** (पब्लिक रिपॉजिटरीज, फॉलोअर्स, कमिट्स और ऑटो-सिंक वेबहुक्स)

यह डेटा साइंस एनालिटिक्स, ब्रांच-वाइज (Data Science, CSE, IT, ECE), ईयर-वाइज (1st, 2nd, 3rd, 4th Year) और सेक्शन-वाइज ग्रुपिंग करके फैकल्टी और प्लेसमेंट सेल्स को छात्रों की वास्तविक तकनीकी क्षमता का 360-डिग्री व्यू प्रदान करता है।

---

## 2. Complete Technology Stack

### 2.1 Frontend (क्लाइंट साइड)
* **React 18.3+**: कंपोनेंट-बेस्ड मॉडर्न यूजर इंटरफेस।
* **Vite 6.0**: सुपर-फास्ट नेक्स्ट-जेनरेशन बंडलर और डेवलपमेंट सर्वर।
* **Tailwind CSS v4.0**: मॉडर्न रेड-थीम (College Brand Red `#dc2626` / Glassmorphism), डार्क मोड, रिस्पॉन्सिव यूटिलिटी क्लासेस।
* **Lucide React Icons**: एनालिटिक्स, ट्रॉफी, गिटहब, कोडशेफ, और लीडरबोर्ड के लिए कस्टमाइज्ड मॉडर्न आइकन्स।
* **React Router DOM v7**: सिंगल पेज एप्लीकेशन (SPA) रूटिंग (Home, Leaderboard, Profile, Admin Dashboard, Login, Register)।
* **Axios**: बैकएंड REST APIs से सिक्योर डेटा कम्युनिकेशन।

### 2.2 Backend (सर्वर साइड)
* **Node.js (ES Modules)**: एसिंक्रोनस, इवेंट-ड्रिवन जावास्क्रिप्ट रनटाइम।
* **Express.js (v4.21)**: रोबस्ट REST API आर्किटेक्चर।
* **Mongoose (v8.9) & MongoDB**: NoSQL डॉक्यूमेंट डेटाबेस, कॉलेज स्टूडेंट्स, डिपार्टमेंट्स और लीडरबोर्ड कैश स्टोर करने के लिए।
* **Server-Sent Events (SSE)**: बिना पेज रीफ्रेश किए रियल-टाइम लाइव डेटा ब्रॉडकास्टिंग (`/api/realtime/events`)।
* **Helmet & CORS**: HTTP हेडर सिक्योरिटी और क्रॉस-ओरिजिन रिसोर्स शेयरिंग।
* **Express-Rate-Limit**: स्पैम और API ओवरलोड रोकने के लिए रिक्वेस्ट रेट लिमिटिंग।
* **JSON Web Token (JWT) & BcryptJS**: सिक्योर ऑथेंटिकेशन और पासवर्ड क्रिप्टोग्राफिक हैशिंग।
* **Multer & CSV-Parse**: कॉलेज की एक्सेल और CSV फाइल्स को प्रोसेस करने वाला मल्टीपार्ट इंजन।
* **ExcelJS (v4.4)**: मल्टी-शीट, स्टाइल्ड एक्सेल वर्कबुक्स (`.xlsx`) ऑटोमेटेड जनरेट और एक्सपोर्ट करने के लिए।
* **Node-Cron**: ऑटोमेटेड बैकग्राउंड ETL शेड्यूलर (हर 5 मिनट में लीटकोड रिफ्रेश और मध्यरात्रि में फुल सिंक)।

### 2.3 Data Extraction & Scraping Engine (डेटा पाइपलाइन्स)
* **LeetCode GraphQL API**: छात्र के यूजरनेम से एक्सेप्टेड सॉल्यूशंस, डिफिकल्टी ब्रेकडाउन और रीसेंट 50 सबमिशन फेच करना।
* **GitHub REST API & Webhooks**: पब्लिक रिपॉजिटरीज, फॉलोअर्स और गिट पुश इवेंट्स को रियल-टाइम कैच करना।
* **CodeChef Scraper / API**: यूजर प्रोफाइल से करंट रेटिंग, स्टार्स, हाईएस्ट रेटिंग और सॉल्वड प्रॉब्लम्स एक्सट्रेक्ट करना।
* **GeeksforGeeks Scraper / API**: कोडिंग स्कोर, कुल सॉल्व किए गए प्रॉब्लम्स और इंस्टीट्यूट रैंक एक्सट्रेक्ट करना।
* **HackerRank Profile Fetcher**: बैजेस और टोटल स्कोर पॉइंट्स को नॉर्मलाइज करना।

---

## 3. Core Features & Modules (क्या-क्या काम कर रहा है)

### 1. Multi-Platform Automated Scraping & Synchronization
* छात्र को सिर्फ अपना यूजरनेम (LeetCode, GitHub, HackerRank, CodeChef, GFG) प्रोफाइल में जोड़ना होता है।
* सिस्टम बैकग्राउंड में स्वतः जाकर सभी प्लेटफॉर्म्स से आधिकारिक डेटा स्क्रैप/फेच करता है।
* एक क्लिक "Sync Now" बटन से छात्र या एडमिन तुरंत फ्रेश डेटा अपडेट कर सकते हैं।

### 2. Data Science KPIs & Statistical Analytics Dashboard
* **Performance KPIs**: एवरेज क्लास स्कोर, कुल प्रॉब्लम्स सॉल्वड, एवरेज गिटहब रिपॉजिटरीज, टॉप कोडर मेट्रिक्स।
* **Overall Distribution Chart**: प्लेटफॉर्म-वाइज (LeetCode vs CodeChef vs GFG vs HackerRank vs GitHub) छात्रों का कंपैरेटिव परफॉरमेंस।
* **LeetCode Stacked Bar Chart**: छात्रों का Easy, Medium, और Hard प्रॉब्लम्स का विजुअल डिफिकल्टी ब्रेकडाउन।
* **Departmental & Year Breakdown**: Data Science, CSE, IT, ECE के बीच औसत स्कोर तुलना और 1st से 4th ईयर का प्रोग्रेशन चार्ट।
* **Platform Deep Dive**: अलग-अलग प्लेटफॉर्म्स (जैसे केवल CodeChef या केवल LeetCode) के टॉप 5 टॉपर्स का अलग चार्ट।

### 3. Dynamic College Leaderboard
* **Multi-Dimensional Filters**: ब्रांच फिल्टर (Data Science, CSE, IT, आदि), सेक्शन फिल्टर (A, B, C), ईयर फिल्टर (1, 2, 3, 4)।
* **Instant Search**: छात्र के नाम, रोल नंबर, या प्लेटफॉर्म यूजरनेम से तुरंत सर्च।
* **Custom Limit Chips**: टॉप 20, 50, 100 या कोई भी कस्टम नंबर डालकर टॉप रैंकर्स देखने की सुविधा।
* **Platform Badges & Direct Links**: छात्र के प्रोफाइल कार्ड पर क्लिक करके सीधे उसके LeetCode या GitHub प्रोफाइल पर जाने की सुविधा।

### 4. Real-Time Push Engine (Server-Sent Events & Webhooks)
* **SSE Live Stream (`/api/realtime/events`)**: जैसे ही किसी छात्र का कोड सबमिट होता है या स्कोर बदलता है, सभी कनेक्टेड एडमिन और छात्रों की स्क्रीन पर बिना रीफ्रेश किए नया रैंक अपडेट हो जाता है।
* **GitHub Push Webhook (`POST /api/webhooks/github`)**: छात्र जब भी अपने गिटहब पर कोड पुश करता है, वेबहुक स्वतः ट्रिगर होकर उसका कैंपस स्कोर री-कैलकुलेट कर देता है।

### 5. Excel Data Ingestion & Export Pipelines
* **Bulk Roster Import**: एडमिन कॉलेज की स्प्रेडशीट (`.xlsx`, `.csv`) अपलोड करता है। सिस्टम नाम, ईमेल, ब्रांच, सेक्शन, ईयर और यूजरनेम्स स्वतः डेटाबेस में मैच व अपडेट करता है।
* **Leaderboard Excel Export**: करेंटली फिल्टर्ड लीडरबोर्ड को प्रोफेशनल फॉरमैटेड `.xlsx` में डाउनलोड करना।
* **Full Roster Export**: कॉलेज के सभी छात्रों का सम्पूर्ण डेटा एक क्लिक में डाउनलोड।
* **Student Dossier Export**: किसी विशेष छात्र का पूरा प्रोफाइल और उसके द्वारा हाल ही में सॉल्व किए गए लीटकोड सवालों की लिस्ट एक्सेल में एक्सपोर्ट।

### 6. Admin Department & Section Manager
* नई ब्रांच जोड़ना (जैसे `Data Science`, `Artificial Intelligence`, `Cyber Security`)।
* हर ब्रांच के अंदर सेक्शन्स (A, B, C) को मैनेज या डिलीट करना।
* किसी भी छात्र का डेटा रिफ्रेश या रिमूव करना।

---

## 4. Internal Working Mechanism (कैसे काम करता है)

```
+---------------------------------------------------------------------------------------------+
|                          COLLEGE CODERANK DATA SCIENCE ARCHITECTURE                         |
+---------------------------------------------------------------------------------------------+
|                                                                                             |
|   [ External Platforms ]                                                                    |
|   ├── LeetCode (GraphQL API)    ──┐                                                         |
|   ├── CodeChef (Scraper/HTML)   ──┼─► [ ETL Sync Engine / Node-Cron / Manual Trigger ]      |
|   ├── GeeksforGeeks (API/Dump)  ──┤                         │                               |
|   ├── HackerRank (REST API)     ──┤                         ▼                               |
|   └── GitHub (API & Webhooks)   ──┘       [ Data Cleaning & Normalization ]                 |
|                                                             │                               |
|                                                             ▼                               |
|                                           [ Weighted Score Calculator Engine ]              |
|                                                             │                               |
|                                                             ▼                               |
|                                           [ MongoDB (Students & LeaderboardCache) ]         |
|                                                             │                               |
|                                       ┌─────────────────────┴─────────────────────┐         |
|                                       ▼                                           ▼         |
|                         [ SSE Real-Time Broadcaster ]              [ ExcelJS Export Engine] |
|                                       │                                           │         |
|                                       ▼                                           ▼         |
|                        [ React 18 + Tailwind v4 UI ]                   [ Formatted .xlsx ]  |
|                        • Performance KPIs                          • Leaderboard Export     |
|                        • Stacked Bar Charts                        • Full Roster Dump       |
|                        • Interactive Rankings Table                • Student Dossier        |
+---------------------------------------------------------------------------------------------+
```

### 4.1 ETL Data Pipeline (Extract, Transform, Load)
1. **Extract**: बैकएंड का सिंक इंजन छात्र के प्रोफाइल हैंडल से डेटा मंगवाता है। LeetCode के लिए GraphQL क्वेरी भेजी जाती है; CodeChef और GFG के लिए DOM/JSON पार्सिंग की जाती है।
2. **Transform**: अलग-अलग प्लेटफॉर्म्स के अलग-अलग फॉर्मेट्स को एक कॉमन स्कीमा (`stats.leetcode`, `stats.codechef`, आदि) में ढाला जाता है। यदि कोई प्लेटफॉर्म अमान्य यूजरनेम लौटाए, तो ग्रेसफुल फॉलबैक लागू होता है।
3. **Load**: डेटा मोंगोडीबी में `students` कलेक्शन में स्टोर होता है और स्कोर स्वतः री-कैलकुलेट होता है।

### 4.2 Real-Time SSE Broadcasting
जब कोई छात्र सिंक होता है या गिटहब वेबहुक आता है:
- बैकएंड `broadcastLeaderboardUpdate()` को कॉल करता है।
- जितने भी यूज़र्स वेबसाइट पर होते हैं, उनका खुला हुआ `EventSource` कनेक्शन तुरंत पिंग प्राप्त करता है।
- फ्रंटएंड का React स्टेट बिना पेज रीलोड किए तुरंत अपडेटेड डेटा री-रेंडर कर देता है।

---

## 5. Data Science Scoring Formula (वेटेड स्कोरिंग अल्गोरिदम)

छात्रों की वास्तविक कोडिंग दक्षता मापने के लिए एक डेटा-साइंस आधारित वेटेड फॉर्मूला लागू किया गया है:

Score = Easy + (3 * Medium) + (5 * Hard) + (2 * Repos) + floor(HR Points / 10) + CodeChefScore + GFGScore

### कम्पोनेंट्स का विस्तृत विवरण:
1. **LeetCode Contribution:**
   - Easy Problem: **1 Point**
   - Medium Problem: **3 Points** (क्योंकि इसमें डेटा स्ट्रक्चर्स और अल्गोरिदम की गहरी समझ चाहिए)
   - Hard Problem: **5 Points** (जटिल डायनामिक प्रोग्रामिंग / ग्राफ समस्याएं)
2. **GitHub Contribution:**
   - Public Repository: **2 Points** प्रति एक्टिव रिपॉजिटरी (प्रैक्टिकल प्रोजेक्ट बिल्डिंग क्षमता)।
3. **HackerRank Contribution:**
   - HackerRank Points का 1/10 (स्केल्ड नॉर्मलाइजेशन)।
4. **CodeChef Contribution:**
   - 2 Points प्रति सॉल्वड प्रॉब्लम।
   - **Rating Tier Bonus:** यदि रेटिंग 1000 से ऊपर है, तो `floor((Rating - 1000) / 50)` का अतिरिक्त बोनस।
5. **GeeksforGeeks Contribution:**
   - कोडिंग स्कोर का 1/2 + कुल सॉल्व किए गए प्रॉब्लम्स।

---

## 6. End-to-End Workflow (पूरा वर्कफ़्लो)

### चरण 1: सिस्टम सेटअप और रोस्टर इम्पोर्ट (Admin)
1. एडमिन `/login` पर जाकर क्रेडेंशियल्स दर्ज करता है।
2. **Admin Dashboard** में कॉलेज की एक्सेल फाइल (`students_roster.xlsx`) अपलोड करता है।
3. सिस्टम छात्रों के नाम, ईमेल, ब्रांच (जैसे Data Science), सेक्शन और प्रोफाइल हैंडल्स स्वतः डेटाबेस में सेव कर लेता है।

### चरण 2: स्वचालित डेटा फेचिंग (Automated Ingestion)
1. बैकएंड का क्रॉन शेड्यूलर या मैनुअल सिंक बटन एक्टिवेट होता है।
2. हर छात्र के LeetCode, GitHub, HackerRank, CodeChef और GFG अकाउंट्स से फ्रेश डेटा फेच होता है।
3. वेटेड फॉर्मूला से प्रत्येक छात्र का स्कोर निकलता है और कॉलेज स्तर पर रैंक 1, 2, 3... तय होती है।

### चरण 3: छात्र का स्वयं रजिस्ट्रेशन व प्रोफाइल संपादन (Student)
1. छात्र `/register` या `/profile` में जाकर अपनी जानकारी और कोडिंग यूजरनेम्स जोड़ता है।
2. "Sync My Stats" पर क्लिक करते ही उसका स्कोर तुरंत अपडेट हो जाता है।
3. छात्र अपने प्रोफाइल में हाल ही में सॉल्व किए गए लीटकोड सवालों की सूची और अपनी कॉलेज रैंक देख सकता है।

### चरण 4: लाइव लीडरबोर्ड और डेटा विजुअलाइजेशन (Faculty & Students)
1. होमपेज `/` पर जाते ही रेड-थीम कॉलेज बैनर, परफॉरमेंस KPIs और चार्ट्स दिखते हैं।
2. यूजर **Branch Filter** में जाकर "Data Science" चुनता है — तुरंत केवल Data Science ब्रांच के छात्रों की रैंकिंग और चार्ट्स सामने आ जाते हैं।
3. **Limit Chips** (20, 50, 100) दबाकर टॉप क्रीम छात्र देखे जा सकते हैं।

### चरण 5: रिपोर्ट डाउनलोड और प्लेसमेंट ऑडिट (Export)
1. प्लेसमेंट हेड या शिक्षक "Export Leaderboard (.xlsx)" बटन दबाते हैं।
2. ExcelJS इंजन तुरंत सभी छात्रों के रोल नंबर, नाम, ब्रांच, लीटकोड स्कोर, गिटहब रिपोज़, और फाइनल मार्क्स के साथ एक फॉर्मेटेड एक्सेल शीट तैयार करके डाउनलोड करा देता है।

---

## 7. UI & Screen Walkthrough (वेबसाइट पर क्या-क्या दिखता है)

| स्क्रीन / कंपोनेंट | फाइल पाथ | क्या-क्या प्रदर्शित होता है? |
|---|---|---|
| **1. Header & Banner** | `Navbar.jsx`, `StudentAnalyticsDashboard.jsx` | कॉलेज ब्रांडिंग लोगो, कॉलेज फोटो, लाइव सिंक स्टेटस (Green Radio Dot), नेविगेशन लिंक्स (Leaderboard, Profile, Admin, Login/Register)। |
| **2. Performance KPIs** | `PerformanceKPIs.jsx` | • Total Active Coders<br>• Class Average Score<br>• Total LeetCode Problems Solved<br>• Highest Campus Scorer & Top GitHub Builder। |
| **3. Analytics Charts Tab** | `StudentAnalyticsDashboard.jsx` | • **Overall Tab:** सभी प्लेटफॉर्म्स का कंबाइंड परफॉरमेंस बार चार्ट।<br>• **LeetCode Tab:** Stacked Bar Chart (Easy = Green, Medium = Yellow, Hard = Red)।<br>• **CodeChef Tab:** स्टार रेटिंग और सॉल्वड प्रॉब्लम्स बार्स।<br>• **Branches Tab:** Data Science vs CSE vs IT vs ECE की औसत स्कोर तुलना। |
| **4. Interactive Filters Bar** | `FiltersBar.jsx` | ब्रांच ड्रॉपडाउन, सेक्शन ड्रॉपडाउन, ईयर 1-4 ड्रॉपडाउन, सर्च बार, और क्विक लिमिट चिप्स (20, 50, 100, All)। |
| **5. Interactive Rankings Table** | `InteractiveRankingsTable.jsx` | रैंक 1, 2, 3 के लिए गोल्ड/सिल्वर/ब्रॉन्ज बैजेस, छात्र का नाम, रोल नंबर, ब्रांच-सेक्शन, प्लेटफॉर्म-वाइज स्कोर्स, और कुल वेटेड स्कोर। |
| **6. Student Profile & Dossier** | `Profile.jsx`, `RecentSolvedProblems.jsx` | छात्र का विस्तृत प्रोफाइल कार्ड, 5 प्लेटफॉर्म्स के लाइव स्टैट्स, और हाल ही में एक्सेप्ट किए गए 50 लीटकोड प्रश्नों की लिस्ट (डिफिकल्टी टैग्स के साथ)। |
| **7. Admin Dashboard** | `AdminDashboard.jsx` | बल्क एक्सेल अपलोडर, डिपार्टमेंट/सेक्शन मैनेजमेंट, छात्रों की डायरेक्ट सिंकिंग और कम्प्लीट रोस्टर एक्सपोर्ट। |

---

## 8. Database Schema & Data Models

### Student Model (`backend/src/models/Student.js`)
* `name` (String, Required)
* `email` (String, Unique, Required)
* `password` (Hashed Bcrypt String)
* `studentId` / `rollNo` (String, Optional/Unique)
* `branch` (String, e.g. "Data Science", "CSE", "IT")
* `section` (String, e.g. "A", "B")
* `year` (Number, 1 to 4)
* `leetcodeUsername`, `githubUsername`, `hackerrankUsername`, `codechefUsername`, `geeksforgeeksUsername`
* `stats`:
  - `leetcode`: `{ easy, medium, hard, total, recentProblems: [] }`
  - `github`: `{ publicRepos, followers }`
  - `hackerrank`: `{ solved, points, badges }`
  - `codechef`: `{ rating, stars, division, problemsSolved, globalRank, countryRank }`
  - `geeksforgeeks`: `{ score, problemsSolved, instituteRank }`
* `score` (Number, Indexed)
* `lastSyncedAt` (Date)

---

## 9. API Endpoints Reference

### 🔐 Authentication (`/api/auth`)
* `POST /api/auth/register` — नए छात्र का रजिस्ट्रेशन।
* `POST /api/auth/login` — छात्र एवं एडमिन लॉगिन (JWT टोकन)।
* `GET /api/auth/me` — वर्तमान में लॉग-इन यूजर का प्रोफाइल।

### 🏆 Leaderboard & Analytics (`/api/leaderboard`)
* `GET /api/leaderboard?branch=&section=&year=&search=&limit=` — फिल्टर्ड लीडरबोर्ड फेच करना।
* `GET /api/leaderboard/export` — एक्सेल स्प्रेडशीट (`.xlsx`) एक्सपोर्ट।

### 👨‍🎓 Student Endpoints (`/api/students`)
* `GET /api/students/me` — छात्र का खुद का डेटा।
* `PATCH /api/students/me` — प्रोफाइल या प्लेटफॉर्म यूजरनेम अपडेट करना।
* `POST /api/students/me/sync` — छात्र के स्टैट्स को रियल-टाइम स्क्रैप/सिंक करना।
* `GET /api/students/:id/export` — किसी विशेष छात्र का विस्तृत डोजियर एक्सेल में एक्सपोर्ट।

### ⚙️ Admin Endpoints (`/api/admin`)
* `GET /api/admin/overview` — कॉलेज के कुल स्टैट्स और डिपार्टमेंट्स।
* `POST /api/admin/departments` — नई ब्रांच जोड़ना।
* `DELETE /api/admin/departments/:branch/sections/:section` — सेक्शन हटाना।
* `POST /api/admin/students/import` — बल्क एक्सेल/CSV रोस्टर अपलोड।
* `GET /api/admin/students/export` — पूरे कॉलेज का मास्टर डेटाबेस एक्सेल में डाउनलोड।
* `POST /api/students/:id/leetcode/sync` — एडमिन द्वारा किसी भी छात्र का डेटा फोर्स-सिंक करना।

### ⚡ Real-Time & Webhooks
* `GET /api/realtime/events` — Server-Sent Events (SSE) लाइव स्ट्रीम कनेक्शन।
* `POST /api/webhooks/github` — गिटहब रिपॉजिटरी पुश वेबहुक लिसनर।
* `POST /api/webhooks/ping` — इंस्टेंट सिंक पिंग एंडपॉइंट।

---

## 10. Setup & Execution Guide

### 1. बैकएंड रन करें:
```powershell
cd "C:\Users\piyus\OneDrive\Desktop\DATA SCIENCE\college-coderank\backend"
npm install
npm run dev
```
* बैकएंड सर्वर `http://localhost:5000` पर एक्टिवेट होगा।

### 2. फ्रंटएंड रन करें:
```powershell
cd "C:\Users\piyus\OneDrive\Desktop\DATA SCIENCE\college-coderank\frontend"
npm install
npm run dev
```
* फ्रंटएंड एप्लिकेशन `http://localhost:5173` पर लाइव होगा।

---

## 🏁 Conclusion

**College CodeRank** कॉलेज के **Data Science**, कंप्यूटर साइंस और आईटी विभागों के लिए एक कम्प्लीट, ऑटोमेटेड और डेटा-ड्रिवन सॉल्यूशन है। यह फैकल्टी को पारदर्शी एनालिटिक्स देता है और छात्रों के बीच एक स्वस्थ प्रतिस्पर्धी कोडिंग माहौल का निर्माण करता है।
