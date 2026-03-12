# 🛡️ Daily SOC Summary Logic App (ARM Template)

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/REPLACE_WITH_RAW_TEMPLATE_URL)

An Azure ARM template that deploys a **Logic App** and supporting **API connections** to generate a **daily Security Operations Center (SOC) summary email** using **Microsoft Sentinel data** and **Microsoft Security Copilot**.

> ⚠️ **Intended for demo, testing, and proof-of-concept use only.**

---

## 📌 Overview

This solution deploys an automated workflow that:

- Queries a **Log Analytics workspace** (typically connected to Microsoft Sentinel)
- Collects incident, severity, provider, and threat intelligence data
- Sends the results to **Microsoft Security Copilot** for analysis
- Emails an **executive-ready SOC summary** to a specified recipient

---

## 📦 Resources Deployed

| Resource | Description |
|--------|------------|
| Logic App | Orchestrates queries, analysis, and email delivery |
| Azure Monitor Logs API Connection | Executes KQL queries |
| Security Copilot API Connection | Generates narrative SOC summary |
| Office 365 Outlook API Connection | Sends summary email |

---

## 🔄 Workflow Description

1. **Recurrence Trigger**
   - Runs daily at **7:00 AM Eastern Time**

2. **Log Analytics Queries**
   - Security incidents (non-informational)
   - Incident counts by severity
   - Incident counts by provider
   - Threat intelligence ingestion statistics

3. **Security Copilot Analysis**
   - Executive-level SOC summary
   - Trend analysis
   - Recommendations and remediation guidance
   - HTML-formatted output

4. **Email Delivery**
   - Subject: *Daily SOC Summary*
   - Sent via Office 365 Outlook

---

## ✅ Prerequisites

- Azure subscription with deployment permissions
- Log Analytics workspace with Sentinel data
- Access to Microsoft Security Copilot
- Office 365 mailbox for email delivery

---

## 🚀 Deployment

### Deploy via Azure Portal

1. Open **Deploy a custom template** in the Azure Portal
2. Paste `daily_soc_summary_template.json`
3. Provide required parameters
4. Review and deploy

### Deploy via Azure CLI

```bash
az deployment group create   --resource-group <resource-group-name>   --template-file daily_soc_summary_template.json   --parameters     to_address=<email@domain.com>     log_analytics_workspace_name=<workspace-name>     log_analytics_workspace_resource_group=<workspace-rg>     log_analytics_workspace_subscription_id=<subscription-id>
```

---

## 🔑 Post-Deployment Steps

> 🚨 API connections must be authorized before the Logic App will run successfully.

Authorize the following connections in the Azure Portal:

- Azure Monitor Logs
- Microsoft Security Copilot
- Office 365 Outlook

---

## 🛠️ Customization

You may customize:

- Recurrence schedule
- KQL queries
- Security Copilot prompt
- Email formatting and recipients

---

## ⚠️ Limitations

- Manual API authorization required
- Delegated authentication only
- Not production-hardened

---

## 🔐 Security Notes

For production scenarios, consider:

- Managed Identities
- Least-privilege RBAC
- Secure handling of email content

---

## 📄 License

Provided as-is for demo and educational purposes.
