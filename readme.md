# Azure Security Tools

## Overview
This repository contains a collection of security resources created by **Security Risk Advisors** to enhance capabilities within the Azure and Microsoft ecosystem.

---

## Structure
Each project or tool is organized into its own folder, complete with a dedicated README file for detailed information.

---

## Projects
### 1. **Sentinel Case File Storage**
   - A collection of Logic Apps that:
     - Automatically creates a file storage folder for every new Sentinel incident.
     - Posts a link to the folder in the incident activity upon creation.
     - Updates the incident whenever files are added to the folder.

### 2. **Epic Ingestion Tools**
   - Tools for ingesting and parsing Epic logs into Azure Sentinel, including:
     - Ingestion time transformation rules.
     - Analytics.
     - Workbooks.

### 3. **Copilot for Security Plugin**
   - A set of plugins designed to extend the functionality of **Copilot for Security**, enabling it to:
     - Include additional datasets.
     - Analyze these datasets effectively.

### 4. **Daily SOC Summary with AI**
   - A Logic App that leverages:
     - **Azure Sentinel** and **Azure OpenAI GPT-4** to generate daily emails summarizing all activities within the SOC.

### 5. **GroundControl for Security Copilot**
   - A Logic App and Chrome plugin that:
     - Allows for direct integration of browser activities with Security Copilot.  Facilitates one click execution of threat hunting based on IOCs on a web page, execution by Security Copilot, and hunt team notification via Teams channel.

---

## Contact
For any comments or questions, please reach out to:

- **Mike Pinch**: [mike.pinch@sra.io](mailto:mike.pinch@sra.io)  
- **Website**: [Security Risk Advisors](https://sra.io)  
- **SCALR Platform**: [SCALR by SRA](https://scalr.sra.io)  

---