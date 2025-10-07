# MATLAB Script Execution Web App

A Flask web application for uploading and executing MATLAB scripts through a web interface with organized results download.

![Dashboard](media/Screenshot%202025-10-07%20074105.png)

## Features

- 🔐 User authentication and registration
- 📁 Upload MATLAB .m files through web interface
- ⚡ Execute scripts using MATLAB Engine
- 📊 Download organized results (logs, images, data files)
- 📈 Real-time execution monitoring

![Login](media/Screenshot%202025-10-07%20074217.png) ![Upload](media/Screenshot%202025-10-07%20074316.png) ![Results](media/Screenshot%202025-10-07%20074456.png)

## How to Use

1. **Login** with default credentials or register
2. **Upload** your .m file via "Upload Script"
3. **Execute** by clicking "Run" button
4. **Download** organized ZIP with results:
   - Execution logs
   - Generated images/plots
   - Data files (MAT, CSV)
   - Scripts and reports

## 📋 Requirements

- Python 3.7+
- MATLAB R2016b+ with MATLAB Engine for Python
- Web browser

## 🔧 Tech Stack

Flask + SQLAlchemy + Bootstrap 5 + MATLAB Engine

## 🔬 RT Lab Integration

Supports RT Lab library for real-time simulation and hardware-in-the-loop testing. Upload MATLAB scripts that utilize RT Lab functions for seamless real-time execution and data collection.

---
